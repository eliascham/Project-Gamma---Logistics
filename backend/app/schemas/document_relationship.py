"""Pydantic schemas for document relationship API requests and responses."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentRelationshipCreate(BaseModel):
    source_document_id: UUID
    target_document_id: UUID
    relationship_type: str = Field(..., description="fulfills, invoices, supports, adjusts, certifies, clears, confirms, notifies")
    reference_field: str | None = Field(None, max_length=100)
    reference_value: str | None = Field(None, max_length=500)
    confidence: float = Field(1.0, ge=0.0, le=1.0)


class DocumentRelationshipResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    source_document_id: UUID
    target_document_id: UUID
    relationship_type: str
    reference_field: str | None
    reference_value: str | None
    confidence: float
    created_by: str
    created_at: datetime
