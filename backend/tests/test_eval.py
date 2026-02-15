"""Tests for the eval metrics engine."""

import pytest

from app.eval.metrics import (
    ExtractionScore,
    FieldScore,
    compute_extraction_score,
    compute_field_accuracy,
    compute_line_item_score,
)


class TestFieldAccuracy:
    def test_exact_string_match(self):
        score = compute_field_accuracy(
            {"vendor_name": "Acme Freight LLC"},
            {"vendor_name": "Acme Freight LLC"},
            "vendor_name",
        )
        assert score.match is True
        assert score.score == 1.0

    def test_case_insensitive_match(self):
        score = compute_field_accuracy(
            {"vendor_name": "ACME FREIGHT LLC"},
            {"vendor_name": "acme freight llc"},
            "vendor_name",
        )
        assert score.match is True

    def test_string_mismatch(self):
        score = compute_field_accuracy(
            {"vendor_name": "Acme Freight"},
            {"vendor_name": "Beta Shipping"},
            "vendor_name",
        )
        assert score.match is False
        assert score.score == 0.0

    def test_numeric_exact_match(self):
        score = compute_field_accuracy(
            {"total_amount": 5000.0},
            {"total_amount": 5000.0},
            "total_amount",
        )
        assert score.match is True

    def test_numeric_within_tolerance(self):
        score = compute_field_accuracy(
            {"total_amount": 5000.0},
            {"total_amount": 5000.005},
            "total_amount",
        )
        assert score.match is True

    def test_numeric_outside_tolerance(self):
        score = compute_field_accuracy(
            {"total_amount": 5000.0},
            {"total_amount": 5001.0},
            "total_amount",
        )
        assert score.match is False

    def test_both_null(self):
        score = compute_field_accuracy(
            {"notes": None},
            {"notes": None},
            "notes",
        )
        assert score.match is True
        assert score.score == 1.0

    def test_expected_null_actual_present(self):
        score = compute_field_accuracy(
            {"notes": None},
            {"notes": "Some note"},
            "notes",
        )
        assert score.match is False

    def test_date_field_match(self):
        score = compute_field_accuracy(
            {"invoice_date": "2024-12-01"},
            {"invoice_date": "2024-12-01"},
            "invoice_date",
        )
        assert score.match is True

    def test_date_field_mismatch(self):
        score = compute_field_accuracy(
            {"invoice_date": "2024-12-01"},
            {"invoice_date": "2024-12-02"},
            "invoice_date",
        )
        assert score.match is False

    def test_missing_field(self):
        score = compute_field_accuracy(
            {"vendor_name": "Acme"},
            {},
            "vendor_name",
        )
        assert score.match is False


class TestLineItemScore:
    def test_perfect_match(self):
        expected = [
            {"description": "Ocean Freight", "total": 5000.0},
            {"description": "Port Handling", "total": 300.0},
        ]
        actual = [
            {"description": "Ocean Freight", "total": 5000.0},
            {"description": "Port Handling", "total": 300.0},
        ]
        score = compute_line_item_score(expected, actual)
        assert score == 1.0

    def test_different_order(self):
        expected = [
            {"description": "Ocean Freight", "total": 5000.0},
            {"description": "Port Handling", "total": 300.0},
        ]
        actual = [
            {"description": "Port Handling", "total": 300.0},
            {"description": "Ocean Freight", "total": 5000.0},
        ]
        score = compute_line_item_score(expected, actual)
        assert score == 1.0

    def test_wrong_amount(self):
        expected = [{"description": "Ocean Freight", "total": 5000.0}]
        actual = [{"description": "Ocean Freight", "total": 6000.0}]
        score = compute_line_item_score(expected, actual)
        # Description matches but amount doesn't — partial score
        assert 0 < score < 1.0

    def test_missing_item(self):
        expected = [
            {"description": "Ocean Freight", "total": 5000.0},
            {"description": "Port Handling", "total": 300.0},
        ]
        actual = [{"description": "Ocean Freight", "total": 5000.0}]
        score = compute_line_item_score(expected, actual)
        assert 0 < score < 1.0

    def test_extra_item(self):
        expected = [{"description": "Ocean Freight", "total": 5000.0}]
        actual = [
            {"description": "Ocean Freight", "total": 5000.0},
            {"description": "Extra Fee", "total": 100.0},
        ]
        score = compute_line_item_score(expected, actual)
        assert 0 < score < 1.0

    def test_both_empty(self):
        assert compute_line_item_score([], []) == 1.0

    def test_expected_empty(self):
        assert compute_line_item_score([], [{"description": "x", "total": 1}]) == 0.0


class TestExtractionScore:
    def test_perfect_extraction(self):
        expected = {
            "invoice_number": "FI-001",
            "vendor_name": "Acme",
            "total_amount": 5000.0,
            "line_items": [{"description": "Freight", "total": 5000.0}],
        }
        score = compute_extraction_score(
            expected, expected,
            scalar_fields=["invoice_number", "vendor_name", "total_amount"],
            line_items_field="line_items",
        )
        assert score.overall_accuracy == 1.0
        assert score.fields_matched == 3
        assert score.fields_total == 3

    def test_partial_extraction(self):
        expected = {
            "invoice_number": "FI-001",
            "vendor_name": "Acme",
            "total_amount": 5000.0,
        }
        actual = {
            "invoice_number": "FI-001",
            "vendor_name": "Wrong Vendor",
            "total_amount": 5000.0,
        }
        score = compute_extraction_score(
            expected, actual,
            scalar_fields=["invoice_number", "vendor_name", "total_amount"],
            line_items_field=None,
        )
        assert score.fields_matched == 2
        assert score.fields_total == 3
        assert 0.5 < score.overall_accuracy < 1.0

    def test_score_to_dict(self):
        score = ExtractionScore(
            field_scores=[
                FieldScore(field_name="test", match=True, score=1.0),
            ],
            overall_accuracy=0.95,
            fields_matched=1,
            fields_total=1,
        )
        d = score.to_dict()
        assert "overall_accuracy" in d
        assert "field_scores" in d
        assert d["overall_accuracy"] == 0.95

    def test_no_line_items(self):
        """BOL-style extraction without line items."""
        expected = {"bol_number": "BOL-001", "carrier_name": "Maersk"}
        actual = {"bol_number": "BOL-001", "carrier_name": "Maersk"}
        score = compute_extraction_score(
            expected, actual,
            scalar_fields=["bol_number", "carrier_name"],
            line_items_field=None,
        )
        assert score.overall_accuracy == 1.0
