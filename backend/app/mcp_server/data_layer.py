"""MCPDataLayer — queries mock_logistics_data and project_budgets tables.

Owns its own async engine since MCP runs as a separate process, not inside FastAPI.
In production, swap for real TMS/WMS/ERP connectors (same interface).
"""

import json
from sqlalchemy import select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings


class MCPDataLayer:
    """Data access layer for MCP server queries."""

    def __init__(self, database_url: str | None = None):
        url = database_url or settings.database_url
        self.engine = create_async_engine(url, echo=False)
        self.session_factory = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False,
        )

    async def query_freight_lanes(
        self,
        origin: str | None = None,
        destination: str | None = None,
        carrier: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Query freight shipment data by lane, carrier, etc."""
        async with self.session_factory() as session:
            query = sa_text("""
                SELECT data FROM mock_logistics_data
                WHERE data_source = 'tms' AND record_type = 'shipment'
                ORDER BY created_at DESC
                LIMIT :limit
            """)
            result = await session.execute(query, {"limit": limit * 3})
            rows = result.all()

        shipments = []
        for row in rows:
            data = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            if origin and origin.lower() not in data.get("origin", "").lower():
                continue
            if destination and destination.lower() not in data.get("destination", "").lower():
                continue
            if carrier and carrier.lower() not in data.get("carrier", "").lower():
                continue
            shipments.append(data)
            if len(shipments) >= limit:
                break

        return shipments

    async def get_warehouse_inventory(
        self,
        warehouse_code: str | None = None,
        sku: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Query warehouse inventory levels."""
        async with self.session_factory() as session:
            query = sa_text("""
                SELECT data FROM mock_logistics_data
                WHERE data_source = 'wms' AND record_type = 'inventory'
                ORDER BY created_at DESC
                LIMIT :limit
            """)
            result = await session.execute(query, {"limit": limit * 3})
            rows = result.all()

        items = []
        for row in rows:
            data = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            if warehouse_code and data.get("warehouse_code") != warehouse_code:
                continue
            if sku and sku.lower() not in data.get("sku", "").lower():
                continue
            items.append(data)
            if len(items) >= limit:
                break

        return items

    async def lookup_project_budget(
        self,
        project_code: str | None = None,
    ) -> list[dict]:
        """Look up project budget information."""
        async with self.session_factory() as session:
            if project_code:
                query = sa_text("""
                    SELECT project_code, project_name, budget_amount, spent_amount,
                           currency, fiscal_year, cost_center
                    FROM project_budgets WHERE project_code = :code
                """)
                result = await session.execute(query, {"code": project_code})
            else:
                query = sa_text("SELECT project_code, project_name, budget_amount, spent_amount, currency, fiscal_year, cost_center FROM project_budgets")
                result = await session.execute(query)

            rows = result.all()

        budgets = []
        for row in rows:
            budgets.append({
                "project_code": row[0],
                "project_name": row[1],
                "budget_amount": row[2],
                "spent_amount": row[3],
                "remaining": round(row[2] - row[3], 2),
                "utilization_pct": round((row[3] / row[2]) * 100, 1) if row[2] > 0 else 0,
                "currency": row[4],
                "fiscal_year": row[5],
                "cost_center": row[6],
            })

        return budgets

    async def search_purchase_orders(
        self,
        po_number: str | None = None,
        vendor: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Search purchase orders."""
        async with self.session_factory() as session:
            query = sa_text("""
                SELECT data FROM mock_logistics_data
                WHERE data_source = 'erp' AND record_type = 'purchase_order'
                ORDER BY created_at DESC
                LIMIT :limit
            """)
            result = await session.execute(query, {"limit": limit * 3})
            rows = result.all()

        orders = []
        for row in rows:
            data = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            if po_number and po_number.lower() not in data.get("po_number", "").lower():
                continue
            if vendor and vendor.lower() not in data.get("vendor", "").lower():
                continue
            if status and data.get("status") != status:
                continue
            orders.append(data)
            if len(orders) >= limit:
                break

        return orders

    async def close(self):
        await self.engine.dispose()
