"""Tests for demo data seeder."""

import uuid

import pytest

from app.demo.seeder import (
    DEMO_INVOICES,
    DEMO_SHIPMENTS,
    DemoDataSeeder,
    get_demo_invoice_ids,
    get_demo_scenarios,
)
from app.models.document import Document, DocumentStatus


class TestDemoData:
    """Tests for static demo data definitions."""

    def test_five_demo_invoices(self):
        assert len(DEMO_INVOICES) == 5

    def test_invoices_have_required_fields(self):
        for inv in DEMO_INVOICES:
            assert "id" in inv
            assert "filename" in inv
            assert "vendor_name" in inv
            assert "invoice_number" in inv
            assert "total_amount" in inv
            assert "po_number" in inv
            assert "line_items" in inv
            assert "scenario" in inv
            assert len(inv["line_items"]) >= 2

    def test_invoice_ids_are_valid_uuids(self):
        for inv in DEMO_INVOICES:
            uid = uuid.UUID(inv["id"])
            assert uid.version == 4

    def test_six_demo_shipments(self):
        """6 shipments: one per invoice + one extra for close_candidates."""
        assert len(DEMO_SHIPMENTS) == 6

    def test_shipments_have_required_fields(self):
        for ship in DEMO_SHIPMENTS:
            assert "reference_number" in ship
            assert "po_number" in ship
            assert "carrier" in ship
            assert "amount" in ship
            assert "origin" in ship
            assert "destination" in ship

    def test_scenarios_are_unique(self):
        scenarios = [inv["scenario"] for inv in DEMO_INVOICES]
        assert len(set(scenarios)) == len(scenarios)

    def test_perfect_match_po_aligns(self):
        """Invoice 1 and Shipment 1 share PO-2025-0001."""
        inv = DEMO_INVOICES[0]
        ship = DEMO_SHIPMENTS[0]
        assert inv["po_number"] == ship["po_number"]
        assert inv["total_amount"] == ship["amount"]

    def test_amount_mismatch_differs(self):
        """Invoice 2 and Shipment 2 share PO but different amounts."""
        inv = DEMO_INVOICES[1]
        ship = DEMO_SHIPMENTS[1]
        assert inv["po_number"] == ship["po_number"]
        assert inv["total_amount"] != ship["amount"]

    def test_no_match_different_po(self):
        """Invoice 3 PO doesn't match Shipment 3."""
        inv = DEMO_INVOICES[2]
        ship = DEMO_SHIPMENTS[2]
        assert inv["po_number"] != ship["po_number"]

    def test_close_candidates_two_shipments(self):
        """Invoice 5 has two candidate shipments with same PO."""
        inv = DEMO_INVOICES[4]
        matching = [s for s in DEMO_SHIPMENTS if s["po_number"] == inv["po_number"]]
        assert len(matching) == 2

    def test_line_items_sum_to_total(self):
        """Each invoice's line items should sum to total_amount."""
        for inv in DEMO_INVOICES:
            line_sum = sum(li["amount"] for li in inv["line_items"])
            assert abs(line_sum - inv["total_amount"]) < 0.01, (
                f"{inv['filename']}: line sum {line_sum} != total {inv['total_amount']}"
            )


class TestGetDemoHelpers:
    """Tests for helper functions."""

    def test_get_demo_invoice_ids(self):
        ids = get_demo_invoice_ids()
        assert len(ids) == 5
        for doc_id in ids:
            uuid.UUID(doc_id)  # Should not raise

    def test_get_demo_scenarios(self):
        scenarios = get_demo_scenarios()
        assert len(scenarios) == 5
        for s in scenarios:
            assert "document_id" in s
            assert "filename" in s
            assert "scenario" in s
            assert "description" in s
            assert len(s["description"]) > 20  # Not just a placeholder


class TestDemoDataSeeder:
    """Tests for DemoDataSeeder.seed()."""

    @pytest.mark.asyncio
    async def test_seed_creates_documents(self, db_session):
        seeder = DemoDataSeeder()
        result = await seeder.seed(db_session)

        assert result["documents"] == 5
        assert result["shipments"] == 6
        assert "message" in result

    @pytest.mark.asyncio
    async def test_seed_is_idempotent(self, db_session):
        """Second seed call should be a no-op."""
        seeder = DemoDataSeeder()
        result1 = await seeder.seed(db_session)
        assert result1["documents"] == 5

        result2 = await seeder.seed(db_session)
        assert result2["documents"] == 5
        assert "already seeded" in result2["message"].lower()

    @pytest.mark.asyncio
    async def test_documents_have_correct_status(self, db_session):
        seeder = DemoDataSeeder()
        await seeder.seed(db_session)

        from sqlalchemy import select
        result = await db_session.execute(
            select(Document).where(Document.document_type == "freight_invoice")
        )
        docs = list(result.scalars().all())
        assert len(docs) >= 5
        for doc in docs:
            assert doc.status == DocumentStatus.EXTRACTED
            assert doc.file_type == "csv"

    @pytest.mark.asyncio
    async def test_seed_returns_scenarios(self, db_session):
        seeder = DemoDataSeeder()
        result = await seeder.seed(db_session)

        assert "scenarios" in result
        assert len(result["scenarios"]) == 5
        assert "perfect_match" in result["scenarios"]
        assert "amount_mismatch" in result["scenarios"]
        assert "no_match" in result["scenarios"]
        assert "high_value_review" in result["scenarios"]
        assert "close_candidates" in result["scenarios"]
