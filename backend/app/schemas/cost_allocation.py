"""Pydantic schemas for cost allocation API requests and responses."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class AllocationLineItemResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    line_item_index: int
    description: str
    amount: float
    project_code: str | None
    cost_center: str | None
    gl_account: str | None
    confidence: float | None
    reasoning: str | None
    status: str  # auto_approved | needs_review | manually_overridden
    override_project_code: str | None = None
    override_cost_center: str | None = None
    override_gl_account: str | None = None


class CostAllocationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    document_id: UUID | None
    status: str
    line_items: list[AllocationLineItemResponse] = []
    total_amount: float | None
    currency: str = "USD"
    allocated_by_model: str | None
    processing_time_ms: int | None
    created_at: datetime


class AllocationOverrideRequest(BaseModel):
    project_code: str | None = Field(None, max_length=50)
    cost_center: str | None = Field(None, max_length=50)
    gl_account: str | None = Field(None, max_length=50)


class AllocationApprovalRequest(BaseModel):
    action: Literal["approve", "reject"]


class AllocationRuleResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    rule_name: str
    description: str | None
    match_pattern: str
    project_code: str
    cost_center: str
    gl_account: str
    priority: int
    is_active: bool
