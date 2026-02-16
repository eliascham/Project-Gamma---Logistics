"""MCP server status endpoints — status, seed mock data, stats."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.mock_data import MockLogisticsData, ProjectBudget
from app.models.reconciliation import RecordSource
from app.schemas.mcp import McpMockDataStatsResponse, McpStatusResponse

router = APIRouter()


@router.get("/status", response_model=McpStatusResponse)
async def get_status(
    db: AsyncSession = Depends(get_db),
) -> McpStatusResponse:
    """Get MCP server status and available tools."""
    total_mock = (await db.execute(select(func.count(MockLogisticsData.id)))).scalar_one()
    total_budgets = (await db.execute(select(func.count(ProjectBudget.id)))).scalar_one()

    return McpStatusResponse(
        status="available",
        tools=[
            "query_freight_lanes",
            "get_warehouse_inventory",
            "lookup_project_budget",
            "search_purchase_orders",
        ],
        mock_data_seeded=total_mock > 0,
        total_mock_records=total_mock,
        total_budgets=total_budgets,
    )


@router.post("/seed")
async def seed_mock_data(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Seed mock logistics data for MCP server."""
    from app.mcp_server.mock_data import MockDataGenerator
    gen = MockDataGenerator(seed=42)
    counts = await gen.seed_all(db)
    return {"message": "Mock data seeded for MCP server", **counts}


@router.get("/stats", response_model=McpMockDataStatsResponse)
async def get_mock_data_stats(
    db: AsyncSession = Depends(get_db),
) -> McpMockDataStatsResponse:
    """Get mock data statistics."""
    total = (await db.execute(select(func.count(MockLogisticsData.id)))).scalar_one()
    total_budgets = (await db.execute(select(func.count(ProjectBudget.id)))).scalar_one()

    by_source_rows = (await db.execute(
        select(MockLogisticsData.data_source, func.count(MockLogisticsData.id))
        .group_by(MockLogisticsData.data_source)
    )).all()
    by_source = {
        (r[0].value if isinstance(r[0], RecordSource) else r[0]): r[1]
        for r in by_source_rows
    }

    by_type_rows = (await db.execute(
        select(MockLogisticsData.record_type, func.count(MockLogisticsData.id))
        .group_by(MockLogisticsData.record_type)
    )).all()
    by_type = {(r[0] or "unknown"): r[1] for r in by_type_rows}

    return McpMockDataStatsResponse(
        total_records=total,
        by_source=by_source,
        by_record_type=by_type,
        total_budgets=total_budgets,
    )
