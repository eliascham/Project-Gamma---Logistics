"""Pydantic schemas for MCP server status."""

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
