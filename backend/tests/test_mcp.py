"""Tests for MockDataGenerator determinism and MCPDataLayer queries."""

import pytest
from unittest.mock import MagicMock

from app.mcp_server.mock_data import MockDataGenerator


class TestMockDataGenerator:
    """Tests for MockDataGenerator determinism and data quality."""

    def test_deterministic_generation(self):
        """Same seed should produce identical data."""
        gen1 = MockDataGenerator(seed=42)
        gen2 = MockDataGenerator(seed=42)

        shipments1 = gen1._generate_shipments()
        shipments2 = gen2._generate_shipments()

        assert len(shipments1) == len(shipments2)
        assert shipments1[0]["reference_number"] == shipments2[0]["reference_number"]
        assert shipments1[0]["amount"] == shipments2[0]["amount"]

    def test_different_seeds_different_data(self):
        """Different seeds should produce different data."""
        gen1 = MockDataGenerator(seed=42)
        gen2 = MockDataGenerator(seed=99)

        shipments1 = gen1._generate_shipments()
        shipments2 = gen2._generate_shipments()

        # Amounts should differ (extremely unlikely to match with different seeds)
        assert shipments1[0]["amount"] != shipments2[0]["amount"]

    def test_shipment_count(self):
        """Should generate ~500 shipments."""
        gen = MockDataGenerator(seed=42)
        shipments = gen._generate_shipments()
        assert len(shipments) == 500

    def test_shipment_structure(self):
        """Each shipment should have required fields."""
        gen = MockDataGenerator(seed=42)
        shipments = gen._generate_shipments()
        s = shipments[0]

        required_fields = [
            "reference_number", "bol_number", "invoice_number",
            "carrier", "origin", "destination", "ship_date", "eta",
            "amount", "currency", "containers", "weight_kg", "status",
            "project_code", "cost_center",
        ]
        for field in required_fields:
            assert field in s, f"Missing field: {field}"

    def test_shipment_reference_format(self):
        """Reference numbers should follow expected format."""
        gen = MockDataGenerator(seed=42)
        shipments = gen._generate_shipments()

        for s in shipments[:10]:
            assert s["reference_number"].startswith("SHP-2025-")
            assert s["bol_number"].startswith("BOL-")

    def test_inventory_generation(self):
        """Should generate inventory records across warehouses."""
        gen = MockDataGenerator(seed=42)
        inventory = gen._generate_inventory()

        assert len(inventory) > 0
        # Should have records for multiple warehouses
        warehouses = set(i["warehouse_code"] for i in inventory)
        assert len(warehouses) >= 2

    def test_inventory_structure(self):
        """Each inventory item should have required fields."""
        gen = MockDataGenerator(seed=42)
        inventory = gen._generate_inventory()
        inv = inventory[0]

        required_fields = [
            "sku", "warehouse_code", "warehouse_name",
            "quantity_on_hand", "unit_cost",
        ]
        for field in required_fields:
            assert field in inv, f"Missing field: {field}"

    def test_purchase_order_count(self):
        """Should generate ~200 purchase orders."""
        gen = MockDataGenerator(seed=42)
        pos = gen._generate_purchase_orders()
        assert len(pos) == 200

    def test_purchase_order_structure(self):
        """Each PO should have required fields and line items."""
        gen = MockDataGenerator(seed=42)
        pos = gen._generate_purchase_orders()
        po = pos[0]

        assert "po_number" in po
        assert po["po_number"].startswith("PO-2025-")
        assert "lines" in po
        assert len(po["lines"]) >= 1
        assert "total_amount" in po

    def test_gl_entries(self):
        """Should generate GL entries for half the shipments."""
        gen = MockDataGenerator(seed=42)
        shipments = gen._generate_shipments()
        gl_entries = gen._generate_gl_entries(shipments)

        assert len(gl_entries) == 250  # half of 500
        gl = gl_entries[0]
        assert "gl_account" in gl
        assert "amount" in gl
        assert "reference_number" in gl

    @pytest.mark.asyncio
    async def test_seed_all_idempotent(self, db_session):
        """Seeding twice should not duplicate data."""
        gen = MockDataGenerator(seed=42)

        result1 = await gen.seed_all(db_session)
        assert result1["mock_records"] > 0

        result2 = await gen.seed_all(db_session)
        assert result2["message"] == "Already seeded"
