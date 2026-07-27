"""RAG document ingest / list / delete / query endpoints."""

from __future__ import annotations

import json
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.session import get_db
from app.models.schemas import (
    DocumentOut,
    DocumentUploadResponse,
    QueryRequest,
    QueryResponse,
)
from app.services.litellm_client import LiteLLMClient
from app.services.rag import RagService

router = APIRouter(prefix="/rag", tags=["rag"])


def get_rag_service(settings: Settings = Depends(get_settings)) -> RagService:
    return RagService(settings, LiteLLMClient(settings))


def _to_document_out(doc, chunk_count: Optional[int] = None) -> DocumentOut:
    count = chunk_count if chunk_count is not None else len(doc.chunks or [])
    return DocumentOut(
        id=doc.id,
        project_id=doc.project_id,
        filename=doc.filename,
        content_type=doc.content_type,
        file_size=doc.file_size,
        uploaded_at=doc.uploaded_at,
        metadata=doc.metadata_ or {},
        chunk_count=count,
    )


@router.post("/documents", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    project_id: str = Form(..., description="LiteLLM Team alias, e.g. school"),
    metadata: str = Form("{}", description="JSON metadata filters (stage, grade, ...)"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    rag: RagService = Depends(get_rag_service),
):
    try:
        meta = json.loads(metadata) if metadata else {}
        if not isinstance(meta, dict):
            raise ValueError("metadata must be a JSON object")
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid metadata JSON: {exc}") from exc

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        document, chunk_count = await rag.ingest(
            db,
            project_id=project_id,
            filename=file.filename or "upload.bin",
            data=data,
            content_type=file.content_type,
            metadata=meta,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Ingestion failed: {exc}") from exc

    return DocumentUploadResponse(document=_to_document_out(document, chunk_count=chunk_count))


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(
    project_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    rag: RagService = Depends(get_rag_service),
):
    docs = await rag.list_documents(db, project_id=project_id)
    return [_to_document_out(d) for d in docs]


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    rag: RagService = Depends(get_rag_service),
):
    ok = await rag.delete_document(db, document_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Document not found")
    return None


@router.post("/query", response_model=QueryResponse)
async def query_rag(
    body: QueryRequest,
    db: AsyncSession = Depends(get_db),
    rag: RagService = Depends(get_rag_service),
):
    try:
        return await rag.query(
            db,
            project_id=body.project_id,
            question=body.question,
            metadata_filters=body.metadata_filters,
            top_k=body.top_k,
            model=body.model,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Query failed: {exc}") from exc
