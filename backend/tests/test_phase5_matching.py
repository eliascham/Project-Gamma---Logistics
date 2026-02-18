"""Tests for Phase 5 3-way matching engine — pure matcher functions."""

import pytest

from app.matching_engine.matchers import (
    MATCH_TOLERANCES,
    FieldMatch,
    LineItemMatch,
    MatchResult,
    MatchStatus,
    compute_three_way_match,
    match_description,
    match_line_items,
    match_numeric,
    match_party_name,
)


class TestMatchNumeric:
    """Tests for numeric matching with tolerance."""

    def test_exact_match(self):
        matched, conf = match_numeric(1000.0, 1000.0)
        assert matched is True
        assert conf == 1.0

    def test_within_pct_tolerance(self):
        # 1% diff, within 5% tolerance
        matched, conf = match_numeric(1000.0, 1010.0, tolerance_pct=0.05)
        assert matched is True
        assert conf > 0.9

    def test_outside_pct_tolerance(self):
        # 10% diff, outside 5% tolerance
        matched, conf = match_numeric(1000.0, 1100.0, tolerance_pct=0.05)
        assert matched is False
        assert conf == 0.0

    def test_within_abs_tolerance(self):
        # $0.005 diff, within $0.01 tolerance
        matched, conf = match_numeric(10.0, 10.005, tolerance_pct=0.001, tolerance_abs=0.01)
        assert matched is True

    def test_none_values(self):
        matched, _ = match_numeric(None, 100.0)
        assert matched is False

        matched, _ = match_numeric(100.0, None)
        assert matched is False

    def test_zero_values(self):
        matched, conf = match_numeric(0.0, 0.0)
        assert matched is True
        assert conf == 1.0

    def test_one_zero(self):
        matched, _ = match_numeric(0.0, 100.0)
        assert matched is False


class TestMatchPartyName:
    """Tests for fuzzy party name matching."""

    def test_exact_match(self):
        matched, conf = match_party_name("Acme Corp", "Acme Corp")
        assert matched is True
        assert conf == 1.0

    def test_case_insensitive(self):
        matched, _ = match_party_name("ACME CORP", "acme corp")
        assert matched is True

    def test_suffix_normalization(self):
        matched, _ = match_party_name("Acme Corp.", "Acme Corporation")
        assert matched is True

    def test_llc_vs_no_suffix(self):
        matched, _ = match_party_name("Acme LLC", "Acme")
        assert matched is True

    def test_containment(self):
        matched, conf = match_party_name("Acme", "Acme International Trading")
        assert matched is True
        assert conf == 0.85

    def test_no_match(self):
        matched, _ = match_party_name("Acme Corp", "Beta Industries")
        assert matched is False

    def test_none_values(self):
        matched, _ = match_party_name(None, "Acme")
        assert matched is False


class TestMatchDescription:
    """Tests for description word-overlap matching."""

    def test_identical(self):
        matched, conf = match_description("Electronic Components", "Electronic Components")
        assert matched is True
        assert conf == 1.0

    def test_high_overlap(self):
        matched, conf = match_description(
            "Electronic Components Type A",
            "Electronic Components Type B",
        )
        assert matched is True
        assert conf >= 0.5

    def test_low_overlap(self):
        matched, _ = match_description("Ocean Freight", "Electronic Components")
        assert matched is False

    def test_none_values(self):
        matched, _ = match_description(None, "test")
        assert matched is False


class TestMatchLineItems:
    """Tests for line item matching between PO and Invoice."""

    def test_full_match(self):
        po_items = [
            {"description": "Widget A electronic", "quantity": 100, "unit_price": 10.0},
            {"description": "Widget B plastic", "quantity": 50, "unit_price": 20.0},
        ]
        inv_items = [
            {"description": "Widget A electronic component", "quantity": 100, "unit_price": 10.0},
            {"description": "Widget B plastic part", "quantity": 50, "unit_price": 20.0},
        ]

        results = match_line_items(po_items, inv_items)
        assert len(results) == 2
        assert results[0].po_index == 0
        assert results[0].quantity_match > 0.9
        assert results[0].unit_price_match > 0.9

    def test_quantity_mismatch(self):
        po_items = [{"description": "Widget A test", "quantity": 100, "unit_price": 10.0}]
        inv_items = [{"description": "Widget A test product", "quantity": 80, "unit_price": 10.0}]

        results = match_line_items(po_items, inv_items)
        assert len(results) == 1
        # 20% diff is outside 5% tolerance
        assert results[0].quantity_match == 0.0
        assert any("Quantity mismatch" in n for n in results[0].notes)

    def test_no_matching_item(self):
        po_items = [{"description": "Ocean freight shipping", "quantity": 1, "unit_price": 3000.0}]
        inv_items = [{"description": "Electronic components", "quantity": 100, "unit_price": 10.0}]

        results = match_line_items(po_items, inv_items)
        assert len(results) == 1
        assert results[0].invoice_index is None

    def test_empty_items(self):
        results = match_line_items([], [])
        assert results == []


class TestComputeThreeWayMatch:
    """Tests for the full 3-way match computation."""

    def test_full_match(self):
        po = {
            "supplier": {"name": "Shanghai Export Co"},
            "total_amount": 10000.0,
            "line_items": [
                {"description": "Widget A electronic", "quantity": 100, "unit_price": 100.0, "total": 10000.0}
            ],
        }
        bol = {"gross_weight": 500.0, "weight_unit": "kg"}
        invoice = {
            "seller": {"name": "Shanghai Export Co"},
            "total_amount": 10000.0,
            "line_items": [
                {"description": "Widget A electronic component", "quantity": 100, "unit_price": 100.0, "total": 10000.0}
            ],
        }

        result = compute_three_way_match(po, bol, invoice)
        assert result.status == MatchStatus.FULL_MATCH
        assert result.overall_confidence >= 0.8

    def test_partial_match(self):
        po = {
            "supplier": {"name": "Shanghai Export Co"},
            "total_amount": 10000.0,
            "line_items": [
                {"description": "Widget A", "quantity": 100, "unit_price": 100.0}
            ],
        }
        invoice = {
            "seller": {"name": "Shanghai Export Co"},
            "total_amount": 9500.0,  # 5% off
            "line_items": [
                {"description": "Widget A product", "quantity": 95, "unit_price": 100.0}
            ],
        }

        result = compute_three_way_match(po, None, invoice)
        # Missing BOL means incomplete
        assert result.status == MatchStatus.INCOMPLETE
        assert "bill_of_lading_or_packing_list" in result.missing_documents

    def test_mismatch(self):
        po = {
            "supplier": {"name": "Company A"},
            "total_amount": 10000.0,
            "line_items": [],
        }
        invoice = {
            "seller": {"name": "Company Z"},  # Different company
            "total_amount": 5000.0,  # 50% off
            "line_items": [],
        }

        result = compute_three_way_match(po, {}, invoice)
        assert result.status == MatchStatus.MISMATCH

    def test_incomplete_missing_two(self):
        result = compute_three_way_match(None, None, {"total_amount": 100})
        assert result.status == MatchStatus.INCOMPLETE
        assert len(result.missing_documents) >= 2

    def test_all_none(self):
        result = compute_three_way_match(None, None, None)
        assert result.status == MatchStatus.INCOMPLETE
        assert result.overall_confidence == 0.0

    def test_party_name_matching(self):
        po = {
            "supplier": {"name": "Acme Trading LLC"},
            "total_amount": 1000.0,
            "line_items": [],
        }
        invoice = {
            "seller": {"name": "Acme Trading"},
            "total_amount": 1000.0,
            "line_items": [],
        }

        result = compute_three_way_match(po, {}, invoice)
        party_match = next((fm for fm in result.field_matches if fm.field_name == "party_name"), None)
        assert party_match is not None
        assert party_match.matched is True
