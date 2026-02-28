"""Tests for MockDataGenerator determinism, MCPDataLayer queries, and MCP server tools."""

import pytest
from unittest.mock import MagicMock

from app.mcp_server.mock_data import MockDataGenerator
from app.mcp_server.server import TOOLS, _reconciliation_result_to_dict
from app.reconciliation_engine.invoice_reconciler import (
    CandidateStatus,
    InvoiceReconciliationResult,
    MatchDiff,
    ReconciliationCandidate,
    reconcile_invoice,
)


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


# ─── MCP Server Tool Definitions ──────────────────────────────


class TestMCPToolDefinitions:
    """Tests for tool definitions in the MCP server."""

    def test_total_tool_count(self):
        """Should have 9 tools total (4 original + 5 new)."""
        assert len(TOOLS) == 9

    def test_original_tools_present(self):
        names = {t.name for t in TOOLS}
        assert "query_freight_lanes" in names
        assert "get_warehouse_inventory" in names
        assert "lookup_project_budget" in names
        assert "search_purchase_orders" in names

    def test_new_tools_present(self):
        names = {t.name for t in TOOLS}
        assert "get_document_details" in names
        assert "get_extraction_result" in names
        assert "search_shipments" in names
        assert "reconcile_invoice" in names
        assert "list_review_queue" in names

    def test_required_fields_on_document_tools(self):
        doc_tool = next(t for t in TOOLS if t.name == "get_document_details")
        assert "document_id" in doc_tool.inputSchema["required"]

        ext_tool = next(t for t in TOOLS if t.name == "get_extraction_result")
        assert "document_id" in ext_tool.inputSchema["required"]

    def test_all_tools_have_descriptions(self):
        for tool in TOOLS:
            assert tool.description, f"Tool {tool.name} has no description"
            assert len(tool.description) > 20

    def test_all_tools_have_input_schemas(self):
        for tool in TOOLS:
            assert tool.inputSchema is not None
            assert tool.inputSchema["type"] == "object"
            assert "properties" in tool.inputSchema


# ─── Reconciliation Result Serialization ──────────────────────


class TestReconciliationResultSerialization:
    """Tests for _reconciliation_result_to_dict serialization."""

    def test_empty_result(self):
        result = InvoiceReconciliationResult(
            invoice_number="INV-001",
            invoice_vendor="Test Vendor",
            invoice_total=1000.0,
            candidates=[],
            best_match=None,
            auto_match=False,
            exceptions=["No matching shipments found for invoice INV-001"],
        )
        d = _reconciliation_result_to_dict(result)
        assert d["invoice_number"] == "INV-001"
        assert d["candidate_count"] == 0
        assert d["candidates"] == []
        assert d["best_match"] is None
        assert d["auto_match"] is False
        assert d["has_match"] is False
        assert len(d["exceptions"]) == 1

    def test_result_with_candidates(self):
        candidate = ReconciliationCandidate(
            shipment_id="ship-001",
            shipment_ref="SHP-001",
            match_score=0.92,
            status=CandidateStatus.STRONG_MATCH,
            match_reasons=["PO match: PO-5500", "Vendor match"],
            diffs=[
                MatchDiff(
                    field="po_number",
                    invoice_value="PO-5500",
                    shipment_value="PO-5500",
                    matched=True,
                    confidence=1.0,
                    note="PO number exact match",
                ),
                MatchDiff(
                    field="total_amount",
                    invoice_value=7500.0,
                    shipment_value=7800.0,
                    matched=False,
                    confidence=0.6,
                    note="Amounts differ (diff: $300.00)",
                ),
            ],
            shipment_data={"id": "ship-001"},
        )
        result = InvoiceReconciliationResult(
            invoice_number="INV-001",
            invoice_vendor="Maersk",
            invoice_total=7500.0,
            candidates=[candidate],
            best_match=candidate,
            auto_match=True,
        )
        d = _reconciliation_result_to_dict(result)

        assert d["candidate_count"] == 1
        assert d["auto_match"] is True
        assert d["has_match"] is True
        assert d["best_match"]["shipment_id"] == "ship-001"
        assert d["best_match"]["status"] == "strong_match"

        c = d["candidates"][0]
        assert c["match_score"] == 0.92
        assert c["status"] == "strong_match"
        assert len(c["diffs"]) == 2
        assert c["has_diffs"] is True  # One diff is not matched
        assert "PO match: PO-5500" in c["match_reasons"]

    def test_diffs_are_serializable(self):
        """Diffs should be plain dicts (JSON serializable)."""
        candidate = ReconciliationCandidate(
            shipment_id="ship-001",
            shipment_ref="SHP-001",
            match_score=0.5,
            status=CandidateStatus.POSSIBLE_MATCH,
            diffs=[
                MatchDiff("field1", "a", "b", False, 0.3, "note1"),
            ],
        )
        result = InvoiceReconciliationResult(
            invoice_number="INV-001",
            invoice_vendor=None,
            invoice_total=None,
            candidates=[candidate],
            best_match=None,
            auto_match=False,
        )
        d = _reconciliation_result_to_dict(result)
        diff = d["candidates"][0]["diffs"][0]
        assert isinstance(diff, dict)
        assert diff["field"] == "field1"
        assert diff["matched"] is False

    def test_reconcile_via_reconciler_and_serialize(self):
        """End-to-end: reconcile_invoice + serialize."""
        invoice = {
            "invoice_number": "INV-001",
            "vendor_name": "Maersk Line",
            "po_number": "PO-5500",
            "total_amount": 7500.0,
            "invoice_date": "2024-11-15",
        }
        shipments = [
            {
                "id": "ship-001",
                "reference_number": "SHP-001",
                "po_number": "PO-5500",
                "carrier": "Maersk Line LLC",
                "amount": 7500.0,
                "ship_date": "2024-11-12",
            },
        ]
        result = reconcile_invoice(invoice, shipments)
        d = _reconciliation_result_to_dict(result)

        assert d["invoice_number"] == "INV-001"
        assert d["has_match"] is True
        assert d["candidate_count"] >= 1
        assert d["candidates"][0]["shipment_id"] == "ship-001"
