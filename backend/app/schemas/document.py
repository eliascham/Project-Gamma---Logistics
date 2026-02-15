from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.document import DocumentStatus
from app.schemas.extraction import DocumentType


class DocumentUploadResponse(BaseModel):
    id: UUID
    filename: str
    original_filename: str
    file_type: str
    file_size: int
    status: DocumentStatus
    uploaded_at: datetime


class DocumentDetail(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    filename: str
    original_filename: str
    file_type: str
    mime_type: str
    file_size: int
    status: DocumentStatus
    document_type: DocumentType | None = None
    page_count: int | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    documents: list[DocumentDetail]
    total: int
    page: int
    per_page: int
