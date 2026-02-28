"""Tests for invoice-to-shipment reconciliation (A3)."""

import pytest

from app.reconciliation_engine.invoice_reconciler import (
    CandidateStatus,
    reconcile_invoice,
    score_invoice_against_shipment,
)


# ─── Fixtures ───────────────────────────────────────────────────


@pytest.fixture
def sample_invoice():
    return {
        "invoice_number": "INV-2024-001",
        "invoice_date": "2024-11-15",
        "vendor_name": "Maersk Line",
        "po_number": "PO-5500",
        "total_amount": 7500.00,
        "currency": "USD",
    }


@pytest.fixture
def matching_shipment():
    return {
        "id": "ship-001",
        "reference_number": "SHP-001",
        "po_number": "PO-5500",
        "carrier": "Maersk Line LLC",
        "amount": 7500.00,
        "ship_date": "2024-11-12",
    }


@pytest.fixture
def partial_match_shipment():
    return {
        "id": "ship-002",
        "reference_number": "SHP-002",
        "po_number": "PO-5500",
        "carrier": "Maersk Line",
        "amount": 8200.00,  # Different amount
        "ship_date": "2024-11-14",
    }


@pytest.fixture
def no_match_shipment():
    return {
        "id": "ship-003",
        "reference_number": "SHP-003",
        "po_number": "PO-9999",
        "carrier": "CMA CGM",
        "amount": 12000.00,
        "ship_date": "2024-06-01",
    }


# ─── score_invoice_against_shipment ─────────────────────────────


class TestScoreInvoiceAgainstShipment:
    def test_perfect_match(self, sample_invoice, matching_shipment):
        score, reasons, diffs = score_invoice_against_shipment(
            sample_invoice, matching_shipment
        )
        assert score >= 0.85
        assert len(reasons) >= 3  # PO, vendor, amount
        assert any("PO match" in r for r in reasons)
        assert any("Vendor match" in r for r in reasons)
        assert any("Amount match" in r for r in reasons)

    def test_partial_match(self, sample_invoice, partial_match_shipment):
        score, reasons, diffs = score_invoice_against_shipment(
            sample_invoice, partial_match_shipment
        )
        # PO matches, vendor matches, but amount differs
        assert 0.3 < score < 0.85
        assert any("PO match" in r for r in reasons)
        # Amount should be a diff
        amount_diffs = [d for d in diffs if d.field == "total_amount"]
        assert len(amount_diffs) == 1
        assert not amount_diffs[0].matched

    def test_no_match(self, sample_invoice, no_match_shipment):
        score, reasons, diffs = score_invoice_against_shipment(
            sample_invoice, no_match_shipment
        )
        assert score < 0.40

    def test_empty_invoice(self):
        score, reasons, diffs = score_invoice_against_shipment({}, {})
        assert score == 0.0
        assert len(reasons) == 0

    def test_vendor_fuzzy_match(self):
        invoice = {"vendor_name": "Maersk Line"}
        shipment = {"carrier": "Maersk Line LLC"}
        score, reasons, diffs = score_invoice_against_shipment(invoice, shipment)
        assert any("Vendor match" in r for r in reasons)

    def test_amount_within_tolerance(self):
        invoice = {"total_amount": 10000}
        shipment = {"amount": 10300}  # 3% diff
        score, reasons, diffs = score_invoice_against_shipment(
            invoice, shipment, amount_tolerance_pct=0.05
        )
        amt_diffs = [d for d in diffs if d.field == "total_amount"]
        assert len(amt_diffs) == 1
        assert amt_diffs[0].matched

    def test_amount_exceeds_tolerance(self):
        invoice = {"total_amount": 10000}
        shipment = {"amount": 12000}  # 20% diff
        score, reasons, diffs = score_invoice_against_shipment(
            invoice, shipment, amount_tolerance_pct=0.05
        )
        amt_diffs = [d for d in diffs if d.field == "total_amount"]
        assert len(amt_diffs) == 1
        assert not amt_diffs[0].matched

    def test_date_within_window(self):
        invoice = {"invoice_date": "2024-11-15"}
        shipment = {"ship_date": "2024-11-13"}
        score, reasons, diffs = score_invoice_against_shipment(
            invoice, shipment, date_tolerance_days=7
        )
        assert any("Date match" in r for r in reasons)

    def test_date_outside_window(self):
        invoice = {"invoice_date": "2024-11-15"}
        shipment = {"ship_date": "2024-06-01"}
        score, reasons, diffs = score_invoice_against_shipment(
            invoice, shipment, date_tolerance_days=7
        )
        date_diffs = [d for d in diffs if d.field == "date"]
        assert len(date_diffs) == 1
        assert not date_diffs[0].matched

    def test_seller_as_party_dict(self):
        invoice = {"seller": {"name": "Global Shipping Co"}}
        shipment = {"carrier": "Global Shipping"}
        score, reasons, diffs = score_invoice_against_shipment(invoice, shipment)
        assert any("Vendor match" in r for r in reasons)


# ─── reconcile_invoice ──────────────────────────────────────────


class TestReconcileInvoice:
    def test_single_strong_match(
        self, sample_invoice, matching_shipment, no_match_shipment
    ):
        result = reconcile_invoice(
            sample_invoice,
            [matching_shipment, no_match_shipment],
        )
        assert result.has_match
        assert result.best_match is not None
        assert result.best_match.shipment_id == "ship-001"
        assert result.auto_match is True
        assert result.invoice_number == "INV-2024-001"

    def test_multiple_candidates(
        self, sample_invoice, matching_shipment, partial_match_shipment
    ):
        result = reconcile_invoice(
            sample_invoice,
            [matching_shipment, partial_match_shipment],
        )
        assert result.candidate_count >= 2
        # Best match should be ship-001
        assert result.best_match.shipment_id == "ship-001"
        # Should be ordered by score
        scores = [c.match_score for c in result.candidates]
        assert scores == sorted(scores, reverse=True)

    def test_no_matches(self, sample_invoice, no_match_shipment):
        result = reconcile_invoice(
            sample_invoice,
            [no_match_shipment],
            min_score=0.50,
        )
        assert result.candidate_count == 0
        assert result.best_match is None
        assert result.auto_match is False
        assert len(result.exceptions) > 0

    def test_empty_shipments(self, sample_invoice):
        result = reconcile_invoice(sample_invoice, [])
        assert result.candidate_count == 0
        assert result.best_match is None
        assert "No matching shipments" in result.exceptions[0]

    def test_top_n_limit(self, sample_invoice):
        # Create 10 shipments with varying scores
        shipments = [
            {
                "id": f"ship-{i}",
                "reference_number": f"SHP-{i}",
                "po_number": "PO-5500" if i < 5 else "PO-9999",
                "carrier": "Maersk Line" if i < 3 else "Other",
                "amount": 7500 + (i * 100),
                "ship_date": f"2024-11-{10 + i}",
            }
            for i in range(10)
        ]
        result = reconcile_invoice(sample_invoice, shipments, top_n=3)
        assert result.candidate_count <= 3

    def test_candidate_statuses(
        self, sample_invoice, matching_shipment, partial_match_shipment, no_match_shipment
    ):
        result = reconcile_invoice(
            sample_invoice,
            [matching_shipment, partial_match_shipment, no_match_shipment],
            min_score=0.0,
        )
        statuses = {c.shipment_id: c.status for c in result.candidates}
        # Strong match should be STRONG_MATCH or LIKELY_MATCH
        assert statuses.get("ship-001") in (
            CandidateStatus.STRONG_MATCH,
            CandidateStatus.LIKELY_MATCH,
        )

    def test_auto_match_disabled_when_close_scores(self, sample_invoice):
        # Two shipments with very similar scores
        shipments = [
            {
                "id": "ship-a",
                "reference_number": "SHP-A",
                "po_number": "PO-5500",
                "carrier": "Maersk Line",
                "amount": 7500,
                "ship_date": "2024-11-14",
            },
            {
                "id": "ship-b",
                "reference_number": "SHP-B",
                "po_number": "PO-5500",
                "carrier": "Maersk Line",
                "amount": 7500,
                "ship_date": "2024-11-15",
            },
        ]
        result = reconcile_invoice(sample_invoice, shipments)
        # Both have similar scores — should NOT auto-match
        if result.candidate_count > 1:
            gap = (
                result.candidates[0].match_score
                - result.candidates[1].match_score
            )
            if gap <= 0.15:
                assert result.auto_match is False

    def test_result_has_diffs(
        self, sample_invoice, partial_match_shipment
    ):
        result = reconcile_invoice(
            sample_invoice,
            [partial_match_shipment],
        )
        assert result.candidate_count >= 1
        candidate = result.candidates[0]
        assert len(candidate.diffs) > 0
        assert candidate.has_diffs  # Amount diff

    def test_invoice_metadata(self, sample_invoice, matching_shipment):
        result = reconcile_invoice(
            sample_invoice,
            [matching_shipment],
        )
        assert result.invoice_number == "INV-2024-001"
        assert result.invoice_vendor == "Maersk Line"
        assert result.invoice_total == 7500.00
