"""Pydantic schemas for MCP server status."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class McpStatusResponse(BaseModel):
    status: str = "available"
    tools: list[str] = Field(default_factory=list)
    mock_data_seeded: bool = False
    total_mock_records: int = 0
    total_budgets: int = 0


class McpMockDataStatsResponse(BaseModel):
    total_records: int = 0
    by_source: dict[str, int] = Field(default_factory=dict)
    by_record_type: dict[str, int] = Field(default_factory=dict)
    total_budgets: int = 0


class MockRecordResponse(BaseModel):
    id: uuid.UUID
    data_source: str
    record_type: str | None = None
    reference_number: str | None = None
    data: dict | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class MockRecordListResponse(BaseModel):
    items: list[MockRecordResponse]
    total: int
    page: int
    per_page: int


class ProjectBudgetResponse(BaseModel):
    id: uuid.UUID
    project_code: str
    project_name: str | None = None
    budget_amount: float
    spent_amount: float = 0
    currency: str = "USD"
    fiscal_year: int | None = None
    cost_center: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
