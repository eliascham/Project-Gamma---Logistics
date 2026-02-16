"""Pydantic schemas for HITL review queue."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ReviewItemResponse(BaseModel):
    id: uuid.UUID
    status: str
    item_type: str | None = None
    entity_id: uuid.UUID | None = None
    entity_type: str | None = None
    title: str | None = None
    description: str | None = None
    severity: str | None = None
    assigned_to: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_notes: str | None = None
    auto_approve_eligible: bool = False
    dollar_amount: float | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ReviewItemListResponse(BaseModel):
    items: list[ReviewItemResponse]
    total: int
    page: int
    per_page: int


class ReviewActionRequest(BaseModel):
    action: str = Field(..., description="approve, reject, or escalate")
    notes: str | None = None
    reviewed_by: str = "user"


class ReviewQueueStats(BaseModel):
    total: int = 0
    pending_review: int = 0
    approved: int = 0
    rejected: int = 0
    escalated: int = 0
    auto_approved: int = 0
