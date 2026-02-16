"""Pydantic schemas for audit events and reports."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AuditEventResponse(BaseModel):
    id: uuid.UUID
    event_type: str | None = None
    event_data: dict | None = None
    entity_type: str | None = None
    entity_id: uuid.UUID | None = None
    action: str | None = None
    actor: str | None = None
    actor_type: str | None = None
    previous_state: dict | None = None
    new_state: dict | None = None
    rationale: str | None = None
    model_used: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class AuditEventListResponse(BaseModel):
    events: list[AuditEventResponse]
    total: int
    page: int
    per_page: int


class AuditReportRequest(BaseModel):
    start_date: datetime | None = None
    end_date: datetime | None = None
    entity_type: str | None = None
    include_summary: bool = True


class AuditReportResponse(BaseModel):
    report: str
    event_count: int
    start_date: datetime | None = None
    end_date: datetime | None = None
    model_used: str | None = None
    generated_at: datetime


class AuditStatsResponse(BaseModel):
    total_events: int = 0
    events_by_type: dict[str, int] = Field(default_factory=dict)
    events_by_actor_type: dict[str, int] = Field(default_factory=dict)
    recent_events: list[AuditEventResponse] = Field(default_factory=list)
