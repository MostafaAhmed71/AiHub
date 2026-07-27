"""RAG ingest + query orchestration."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import Select, delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.models.entities import RagChunk, RagDocument
from app.models.schemas import QueryResponse, SourceChunk
from app.services.chunking import chunk_text, extract_text
from app.services.litellm_client import LiteLLMClient

SYSTEM_PROMPT = """You are a careful assistant answering ONLY from the provided context documents.
Rules:
- Use only the context below. If the answer is not in the context, say you do not know.
- Do not invent facts, numbers, or citations.
- Prefer concise, accurate answers in the same language as the user question.
- When helpful, mention which source filename supported the answer.
"""


class RagService:
    def __init__(self, settings: Settings, llm: LiteLLMClient):
        self.settings = settings
        self.llm = llm
        Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)

    async def ingest(
        self,
        db: AsyncSession,
        *,
        project_id: str,
        filename: str,
        data: bytes,
        content_type: Optional[str],
        metadata: dict[str, Any],
    ) -> tuple[RagDocument, int]:
        text_content = extract_text(filename, data)
        chunks = chunk_text(
            text_content,
            chunk_size=self.settings.chunk_size,
            overlap=self.settings.chunk_overlap,
        )
        if not chunks:
            raise ValueError("No extractable text found in the uploaded file")

        # Persist raw file for audit / reprocessing
        doc_id = uuid.uuid4()
        safe_name = f"{doc_id}_{Path(filename).name}"
        dest = Path(self.settings.upload_dir) / safe_name
        dest.write_bytes(data)

        document = RagDocument(
            id=doc_id,
            project_id=project_id,
            filename=filename,
            content_type=content_type,
            file_size=len(data),
            metadata_=metadata,
        )
        db.add(document)
        await db.flush()

        embeddings = await self.llm.embed(chunks)
        if len(embeddings) != len(chunks):
            raise RuntimeError("Embedding count mismatch from LiteLLM")

        for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            db.add(
                RagChunk(
                    document_id=document.id,
                    content=chunk,
                    chunk_index=idx,
                    embedding=emb,
                    metadata_={**metadata, "project_id": project_id, "filename": filename},
                )
            )

        await db.flush()
        return document, len(chunks)

    async def list_documents(
        self,
        db: AsyncSession,
        project_id: Optional[str] = None,
    ) -> list[RagDocument]:
        stmt: Select = select(RagDocument).options(selectinload(RagDocument.chunks)).order_by(
            RagDocument.uploaded_at.desc()
        )
        if project_id:
            stmt = stmt.where(RagDocument.project_id == project_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def delete_document(self, db: AsyncSession, document_id: uuid.UUID) -> bool:
        result = await db.execute(select(RagDocument).where(RagDocument.id == document_id))
        doc = result.scalar_one_or_none()
        if not doc:
            return False
        await db.execute(delete(RagChunk).where(RagChunk.document_id == document_id))
        await db.delete(doc)
        await db.flush()
        return True

    async def query(
        self,
        db: AsyncSession,
        *,
        project_id: str,
        question: str,
        metadata_filters: dict[str, Any],
        top_k: Optional[int] = None,
        model: Optional[str] = None,
    ) -> QueryResponse:
        k = top_k or self.settings.top_k
        query_embedding = (await self.llm.embed([question]))[0]

        # Mandatory project scope + optional metadata JSON containment filter
        filters_sql = "d.project_id = :project_id"
        params: dict[str, Any] = {
            "project_id": project_id,
            "embedding": str(query_embedding),
            "top_k": k,
        }

        if metadata_filters:
            # Apply filters against document metadata (authoritative project context)
            filters_sql += " AND d.metadata @> CAST(:meta_filters AS jsonb)"
            params["meta_filters"] = json.dumps(metadata_filters)

        sql = text(
            f"""
            SELECT
                c.id AS chunk_id,
                c.document_id,
                c.content,
                c.metadata AS chunk_metadata,
                d.filename,
                d.metadata AS doc_metadata,
                1 - (c.embedding <=> CAST(:embedding AS vector)) AS score
            FROM rag_chunks c
            JOIN rag_documents d ON d.id = c.document_id
            WHERE {filters_sql}
              AND c.embedding IS NOT NULL
            ORDER BY c.embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
            """
        )

        result = await db.execute(sql, params)
        rows = result.mappings().all()

        sources: list[SourceChunk] = []
        context_blocks: list[str] = []
        for row in rows:
            meta = dict(row["chunk_metadata"] or {})
            sources.append(
                SourceChunk(
                    chunk_id=row["chunk_id"],
                    document_id=row["document_id"],
                    filename=row["filename"],
                    content=row["content"],
                    score=float(row["score"] or 0.0),
                    metadata=meta,
                )
            )
            context_blocks.append(f"[Source: {row['filename']}]\n{row['content']}")

        if not context_blocks:
            return QueryResponse(
                answer="I could not find relevant documents for this project/filters. Please upload documents or adjust metadata filters.",
                sources=[],
                model=model or self.settings.chat_model,
                project_id=project_id,
            )

        context = "\n\n---\n\n".join(context_blocks)
        user_message = (
            f"Context documents:\n{context}\n\n"
            f"User question: {question}\n\n"
            "Answer strictly from the context."
        )

        answer = await self.llm.chat(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            model=model,
        )

        return QueryResponse(
            answer=answer,
            sources=sources,
            model=model or self.settings.chat_model,
            project_id=project_id,
        )
