"""Pydantic schemas for reconciliation engine."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ReconciliationRecordResponse(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    source: str
    record_type: str | None = None
    reference_number: str | None = None
    record_data: dict | None = None
    match_status: str | None = None
    matched_with_id: uuid.UUID | None = None
    match_confidence: float | None = None
    match_reasoning: str | None = None
    mismatch_details: dict | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ReconciliationRunResponse(BaseModel):
    id: uuid.UUID
    name: str | None = None
    description: str | None = None
    status: str | None = None
    total_records: int | None = None
    matched_count: int | None = None
    mismatch_count: int | None = None
    match_rate: float | None = None
    run_by: str | None = None
    model_used: str | None = None
    processing_time_ms: int | None = None
    summary: dict | None = None
    records: list[ReconciliationRecordResponse] = Field(default_factory=list)
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ReconciliationRunListResponse(BaseModel):
    runs: list[ReconciliationRunResponse]
    total: int
    page: int
    per_page: int


class ReconciliationTriggerRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    run_by: str = "user"


class ReconciliationStatsResponse(BaseModel):
    total_runs: int = 0
    total_records: int = 0
    avg_match_rate: float | None = None
    last_run_at: datetime | None = None
