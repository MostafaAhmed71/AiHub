from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: str
    filename: str
    content_type: Optional[str] = None
    file_size: Optional[int] = None
    uploaded_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
    chunk_count: int = 0


class DocumentUploadResponse(BaseModel):
    document: DocumentOut
    message: str = "Document ingested successfully"


class QueryRequest(BaseModel):
    project_id: str = Field(..., min_length=1, description="Must match LiteLLM Team alias")
    question: str = Field(..., min_length=1)
    metadata_filters: dict[str, Any] = Field(
        default_factory=dict,
        description="Mandatory-style filters applied before similarity search (e.g. stage, grade)",
    )
    top_k: Optional[int] = Field(default=None, ge=1, le=20)
    model: Optional[str] = None


class SourceChunk(BaseModel):
    chunk_id: UUID
    document_id: UUID
    filename: Optional[str] = None
    content: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    model: str
    project_id: str


class PromptCreate(BaseModel):
    category: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    variables: list[str] = Field(default_factory=list)
    project_id: Optional[str] = None


class PromptUpdate(BaseModel):
    category: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    variables: Optional[list[str]] = None
    project_id: Optional[str] = None


class PromptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category: str
    title: str
    content: str
    variables: list[Any] = Field(default_factory=list)
    project_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PromptRenderRequest(BaseModel):
    variables: dict[str, str] = Field(default_factory=dict)


class PromptRenderResponse(BaseModel):
    prompt_id: UUID
    rendered: str


class HealthResponse(BaseModel):
    status: str
    service: str = "rag-service"
