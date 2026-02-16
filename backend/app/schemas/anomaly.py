"""Pydantic schemas for anomaly detection."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AnomalyFlagResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID | None = None
    allocation_id: uuid.UUID | None = None
    anomaly_type: str
    severity: str
    title: str
    description: str | None = None
    details: dict | None = None
    is_resolved: bool = False
    resolved_by: str | None = None
    resolved_at: datetime | None = None
    resolution_notes: str | None = None
    review_item_id: uuid.UUID | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class AnomalyFlagListResponse(BaseModel):
    anomalies: list[AnomalyFlagResponse]
    total: int
    page: int
    per_page: int


class AnomalyResolutionRequest(BaseModel):
    resolved_by: str = "user"
    resolution_notes: str | None = None


class AnomalyScanRequest(BaseModel):
    document_id: uuid.UUID | None = None


class AnomalyStatsResponse(BaseModel):
    total: int = 0
    unresolved: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)


class AnomalyAuditSummaryResponse(BaseModel):
    summary: str
    total_anomalies: int = 0
    total_spend: float = 0.0
    model_used: str | None = None
    generated_at: datetime
