"""MockDataGenerator — deterministic, reproducible mock logistics data.

Generates ~500 freight shipments, ~50 SKUs, ~200 POs, GL entries, and
5 project budgets for MCP server and reconciliation testing.
"""

import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mock_data import MockLogisticsData, ProjectBudget
from app.models.reconciliation import RecordSource

# ── Reference data ──

CARRIERS = [
    "Maersk Line", "MSC", "CMA CGM", "COSCO", "Hapag-Lloyd",
    "ONE", "Evergreen", "Yang Ming",
]

LANES = [
    ("Shanghai", "Los Angeles"), ("Rotterdam", "New York"), ("Shenzhen", "Long Beach"),
    ("Singapore", "Savannah"), ("Busan", "Seattle"), ("Hamburg", "Charleston"),
    ("Kaohsiung", "Oakland"), ("Yokohama", "Tacoma"), ("Antwerp", "Houston"),
    ("Mumbai", "Newark"),
]

WAREHOUSES = [
    {"code": "WH-LAX", "name": "Los Angeles DC", "city": "Los Angeles"},
    {"code": "WH-CHI", "name": "Chicago DC", "city": "Chicago"},
    {"code": "WH-NYC", "name": "New York DC", "city": "New York"},
]

SKUS = [
    "ELEC-001", "ELEC-002", "ELEC-003", "ELEC-004", "ELEC-005",
    "FURN-001", "FURN-002", "FURN-003", "FURN-004", "FURN-005",
    "FOOD-001", "FOOD-002", "FOOD-003", "FOOD-004", "FOOD-005",
    "TEXT-001", "TEXT-002", "TEXT-003", "TEXT-004", "TEXT-005",
    "AUTO-001", "AUTO-002", "AUTO-003", "AUTO-004", "AUTO-005",
    "CHEM-001", "CHEM-002", "CHEM-003", "CHEM-004", "CHEM-005",
    "PHAR-001", "PHAR-002", "PHAR-003", "PHAR-004", "PHAR-005",
    "MACH-001", "MACH-002", "MACH-003", "MACH-004", "MACH-005",
    "PACK-001", "PACK-002", "PACK-003", "PACK-004", "PACK-005",
    "MISC-001", "MISC-002", "MISC-003", "MISC-004", "MISC-005",
]

PROJECT_BUDGETS = [
    {"code": "INTL-FREIGHT-001", "name": "International Freight Q1", "budget": 500000, "center": "CC-INTL"},
    {"code": "DOM-TRANS-003", "name": "Domestic Transportation", "budget": 200000, "center": "CC-DOM"},
    {"code": "WH-OPS-004", "name": "Warehouse Operations", "budget": 350000, "center": "CC-WH"},
    {"code": "CUST-BROKER-002", "name": "Customs & Brokerage", "budget": 150000, "center": "CC-CUST"},
    {"code": "SPEC-PROJ-005", "name": "Special Projects", "budget": 100000, "center": "CC-SPEC"},
]

GL_ACCOUNTS = {
    "ocean_freight": "5010-OCEFRGT",
    "customs_duty": "5020-CUSTDTY",
    "drayage": "5030-DRAYAGE",
    "warehousing": "5040-WHOUSE",
    "insurance": "5050-INSRNCE",
    "documentation": "5060-DOCFEE",
}


class MockDataGenerator:
    """Deterministic mock data generator for logistics operations."""

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.base_date = datetime(2025, 10, 1, tzinfo=timezone.utc)

    async def seed_all(self, db: AsyncSession) -> dict:
        """Seed all mock data into the database. Returns counts."""
        # Check if already seeded
        existing = (await db.execute(select(func.count(MockLogisticsData.id)))).scalar_one()
        if existing > 0:
            return {"mock_records": existing, "budgets": 0, "message": "Already seeded"}

        shipments = self._generate_shipments()
        inventory = self._generate_inventory()
        purchase_orders = self._generate_purchase_orders()
        gl_entries = self._generate_gl_entries(shipments)

        counts = {"tms": 0, "wms": 0, "erp": 0}

        # Insert shipments (TMS records)
        for s in shipments:
            db.add(MockLogisticsData(
                id=uuid.uuid4(),
                data_source=RecordSource.TMS,
                record_type="shipment",
                reference_number=s["reference_number"],
                data=s,
            ))
            counts["tms"] += 1

        # Insert inventory (WMS records)
        for inv in inventory:
            db.add(MockLogisticsData(
                id=uuid.uuid4(),
                data_source=RecordSource.WMS,
                record_type="inventory",
                reference_number=inv["sku"],
                data=inv,
            ))
            counts["wms"] += 1

        # Insert purchase orders (ERP records)
        for po in purchase_orders:
            db.add(MockLogisticsData(
                id=uuid.uuid4(),
                data_source=RecordSource.ERP,
                record_type="purchase_order",
                reference_number=po["po_number"],
                data=po,
            ))
            counts["erp"] += 1

        # Insert GL entries (ERP records)
        for gl in gl_entries:
            db.add(MockLogisticsData(
                id=uuid.uuid4(),
                data_source=RecordSource.ERP,
                record_type="gl_entry",
                reference_number=gl["reference_number"],
                data=gl,
            ))
            counts["erp"] += 1

        # Insert project budgets
        budget_count = 0
        for pb in PROJECT_BUDGETS:
            spent = self.rng.uniform(0.3, 0.95) * pb["budget"]
            db.add(ProjectBudget(
                id=uuid.uuid4(),
                project_code=pb["code"],
                project_name=pb["name"],
                budget_amount=pb["budget"],
                spent_amount=round(spent, 2),
                currency="USD",
                fiscal_year=2025,
                cost_center=pb["center"],
            ))
            budget_count += 1

        await db.flush()

        total = sum(counts.values())
        return {"mock_records": total, "budgets": budget_count, **counts}

    def _generate_shipments(self) -> list[dict]:
        """Generate ~500 freight shipments."""
        shipments = []
        for i in range(500):
            origin, dest = self.rng.choice(LANES)
            carrier = self.rng.choice(CARRIERS)
            ship_date = self.base_date + timedelta(days=self.rng.randint(0, 120))
            eta = ship_date + timedelta(days=self.rng.randint(14, 45))
            amount = round(self.rng.uniform(500, 75000), 2)
            containers = self.rng.randint(1, 10)
            weight_kg = self.rng.randint(1000, 25000) * containers

            ref = f"SHP-{2025}-{i+1:05d}"
            bol = f"BOL-{self.rng.randint(100000, 999999)}"
            invoice = f"INV-{carrier[:3].upper()}-{self.rng.randint(10000, 99999)}"

            project = self.rng.choice(PROJECT_BUDGETS)

            shipments.append({
                "reference_number": ref,
                "bol_number": bol,
                "invoice_number": invoice,
                "carrier": carrier,
                "origin": origin,
                "destination": dest,
                "ship_date": ship_date.isoformat(),
                "eta": eta.isoformat(),
                "amount": amount,
                "currency": "USD",
                "containers": containers,
                "weight_kg": weight_kg,
                "status": self.rng.choice(["in_transit", "delivered", "pending", "customs_hold"]),
                "project_code": project["code"],
                "cost_center": project["center"],
            })
        return shipments

    def _generate_inventory(self) -> list[dict]:
        """Generate inventory records across 3 warehouses for 50 SKUs."""
        inventory = []
        for sku in SKUS:
            for wh in WAREHOUSES:
                qty = self.rng.randint(0, 5000)
                if qty == 0 and self.rng.random() > 0.3:
                    continue
                inventory.append({
                    "sku": sku,
                    "warehouse_code": wh["code"],
                    "warehouse_name": wh["name"],
                    "city": wh["city"],
                    "quantity_on_hand": qty,
                    "quantity_reserved": self.rng.randint(0, min(qty, 500)),
                    "unit_cost": round(self.rng.uniform(5, 500), 2),
                    "last_received": (self.base_date + timedelta(days=self.rng.randint(-30, 30))).isoformat(),
                    "reorder_point": self.rng.randint(100, 1000),
                })
        return inventory

    def _generate_purchase_orders(self) -> list[dict]:
        """Generate ~200 purchase orders."""
        purchase_orders = []
        for i in range(200):
            po_date = self.base_date + timedelta(days=self.rng.randint(-30, 90))
            num_lines = self.rng.randint(1, 8)
            lines = []
            total = 0
            for j in range(num_lines):
                sku = self.rng.choice(SKUS)
                qty = self.rng.randint(10, 500)
                unit_price = round(self.rng.uniform(10, 1000), 2)
                line_total = round(qty * unit_price, 2)
                total += line_total
                lines.append({
                    "line": j + 1,
                    "sku": sku,
                    "quantity": qty,
                    "unit_price": unit_price,
                    "total": line_total,
                })

            purchase_orders.append({
                "po_number": f"PO-{2025}-{i+1:04d}",
                "vendor": self.rng.choice(CARRIERS),
                "po_date": po_date.isoformat(),
                "total_amount": round(total, 2),
                "currency": "USD",
                "status": self.rng.choice(["open", "partially_received", "received", "closed"]),
                "lines": lines,
                "project_code": self.rng.choice(PROJECT_BUDGETS)["code"],
            })
        return purchase_orders

    def _generate_gl_entries(self, shipments: list[dict]) -> list[dict]:
        """Generate GL entries corresponding to shipments."""
        gl_entries = []
        for s in shipments[:250]:  # GL entries for half the shipments
            charge_type = self.rng.choice(list(GL_ACCOUNTS.keys()))
            gl_entries.append({
                "reference_number": s["reference_number"],
                "invoice_number": s["invoice_number"],
                "gl_account": GL_ACCOUNTS[charge_type],
                "charge_type": charge_type,
                "amount": s["amount"],
                "currency": s["currency"],
                "posting_date": s["ship_date"],
                "project_code": s["project_code"],
                "cost_center": s["cost_center"],
                "description": f"{charge_type.replace('_', ' ').title()} - {s['carrier']} {s['origin']}→{s['destination']}",
            })
        return gl_entries
