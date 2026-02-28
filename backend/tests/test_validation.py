"""
Tests for the deterministic validation layer (A2) and confidence scoring (A1).
"""

import pytest

from app.schemas.extraction import DocumentType
from app.schemas.validation import IssueSeverity, ValidationResult
from app.validator.confidence import (
    blend_confidences,
    compute_agreement_confidence,
    compute_overall_confidence,
)
from app.validator.service import ValidationService
from app.validator.validators import (
    validate_amounts,
    validate_currency,
    validate_dates,
    validate_line_item_math,
    validate_reference_numbers,
    validate_required_fields,
    validate_totals,
)


# ─── Fixtures ───────────────────────────────────────────────────


@pytest.fixture
def valid_freight_invoice():
    return {
        "invoice_number": "INV-2024-001",
        "invoice_date": "2024-11-15",
        "vendor_name": "Maersk Line",
        "shipper_name": "ACME Corp",
        "consignee_name": "Global Imports LLC",
        "origin": "Shanghai",
        "destination": "Los Angeles",
        "currency": "USD",
        "line_items": [
            {"description": "Ocean Freight", "quantity": 2, "unit": "container", "unit_price": 3500.00, "total": 7000.00},
            {"description": "BAF Surcharge", "quantity": 2, "unit": "container", "unit_price": 250.00, "total": 500.00},
        ],
        "subtotal": 7500.00,
        "tax_amount": 0,
        "total_amount": 7500.00,
    }


@pytest.fixture
def invalid_freight_invoice():
    """Invoice with multiple validation issues."""
    return {
        "invoice_number": "",  # empty required
        "invoice_date": "2030-01-01",  # future
        "vendor_name": None,  # null required
        "currency": "FAKE",
        "line_items": [
            {"description": "Ocean Freight", "quantity": 2, "unit": "TEU", "unit_price": 3500, "total": 8000},  # math wrong
        ],
        "subtotal": 8000,
        "tax_amount": 0,
        "total_amount": 9999,  # doesn't match subtotal
    }


# ─── validate_required_fields ───────────────────────────────────


class TestRequiredFields:
    def test_valid_invoice_passes(self, valid_freight_invoice):
        issues = validate_required_fields(valid_freight_invoice, DocumentType.FREIGHT_INVOICE)
        assert len(issues) == 0

    def test_missing_required_fields(self):
        extraction = {"invoice_number": None, "vendor_name": "", "total_amount": 100}
        issues = validate_required_fields(extraction, DocumentType.FREIGHT_INVOICE)
        required_issues = [i for i in issues if i.rule == "missing_required"]
        assert len(required_issues) == 2  # invoice_number null, vendor_name empty
        assert all(i.severity == IssueSeverity.ERROR for i in required_issues)
        # Also gets empty_line_items warning since no line_items key
        assert len(issues) == 3

    def test_empty_line_items_warning(self):
        extraction = {"invoice_number": "INV-1", "vendor_name": "Test", "total_amount": 100, "line_items": []}
        issues = validate_required_fields(extraction, DocumentType.FREIGHT_INVOICE)
        warnings = [i for i in issues if i.rule == "empty_line_items"]
        assert len(warnings) == 1
        assert warnings[0].severity == IssueSeverity.WARNING

    def test_bol_only_requires_bol_number(self):
        extraction = {"bol_number": "MAEU12345678"}
        issues = validate_required_fields(extraction, DocumentType.BILL_OF_LADING)
        assert len(issues) == 0


# ─── validate_line_item_math ────────────────────────────────────


class TestLineItemMath:
    def test_correct_math(self, valid_freight_invoice):
        issues = validate_line_item_math(valid_freight_invoice, DocumentType.FREIGHT_INVOICE)
        assert len(issues) == 0

    def test_wrong_line_total(self):
        extraction = {
            "line_items": [
                {"description": "Freight", "quantity": 3, "unit": "TEU", "unit_price": 1000, "total": 5000}
            ]
        }
        issues = validate_line_item_math(extraction, DocumentType.FREIGHT_INVOICE)
        assert len(issues) == 1
        assert issues[0].rule == "line_item_math"
        assert "3000.00" in issues[0].expected

    def test_rounding_tolerance(self):
        extraction = {
            "line_items": [
                {"description": "Freight", "quantity": 3, "unit": "TEU", "unit_price": 33.33, "total": 99.99}
            ]
        }
        issues = validate_line_item_math(extraction, DocumentType.FREIGHT_INVOICE)
        assert len(issues) == 0  # 99.99 ≈ 99.99, within tolerance

    def test_skips_non_priced_doc_types(self):
        extraction = {"line_items": [{"description": "X", "quantity": 1, "unit": "EA", "unit_price": 10, "total": 999}]}
        issues = validate_line_item_math(extraction, DocumentType.BILL_OF_LADING)
        assert len(issues) == 0  # BOL doesn't have priced line items


# ─── validate_totals ────────────────────────────────────────────


class TestTotals:
    def test_valid_totals(self, valid_freight_invoice):
        issues = validate_totals(valid_freight_invoice, DocumentType.FREIGHT_INVOICE)
        assert len(issues) == 0

    def test_line_sum_mismatch(self):
        extraction = {
            "line_items": [
                {"description": "A", "quantity": 1, "unit": "EA", "unit_price": 100, "total": 100},
            ],
            "subtotal": 500,  # Doesn't match line sum (100)
            "tax_amount": 0,
            "total_amount": 500,
        }
        issues = validate_totals(extraction, DocumentType.FREIGHT_INVOICE)
        mismatch = [i for i in issues if i.rule == "totals_mismatch"]
        assert len(mismatch) == 1

    def test_subtotal_plus_tax_mismatch(self):
        extraction = {
            "line_items": [],
            "subtotal": 1000,
            "tax_amount": 100,
            "total_amount": 5000,  # Should be 1100
        }
        issues = validate_totals(extraction, DocumentType.FREIGHT_INVOICE)
        computation = [i for i in issues if i.rule == "total_computation"]
        assert len(computation) == 1
        assert computation[0].severity == IssueSeverity.ERROR

    def test_commercial_invoice_includes_freight_insurance(self):
        extraction = {
            "line_items": [{"description": "Goods", "quantity": 1, "unit": "lot", "unit_price": 1000, "total": 1000}],
            "subtotal": 1000,
            "tax_amount": 0,
            "freight_charges": 200,
            "insurance_charges": 50,
            "discount_amount": 0,
            "total_amount": 1250,
        }
        issues = validate_totals(extraction, DocumentType.COMMERCIAL_INVOICE)
        computation = [i for i in issues if i.rule == "total_computation"]
        assert len(computation) == 0  # 1000 + 0 + 200 + 50 - 0 = 1250


# ─── validate_dates ─────────────────────────────────────────────


class TestDates:
    def test_valid_date(self, valid_freight_invoice):
        issues = validate_dates(valid_freight_invoice, DocumentType.FREIGHT_INVOICE)
        assert len(issues) == 0

    def test_future_invoice_date(self):
        extraction = {"invoice_date": "2030-06-01"}
        issues = validate_dates(extraction, DocumentType.FREIGHT_INVOICE)
        future = [i for i in issues if i.rule == "future_date"]
        assert len(future) == 1

    def test_ancient_date(self):
        extraction = {"invoice_date": "1995-01-01"}
        issues = validate_dates(extraction, DocumentType.FREIGHT_INVOICE)
        ancient = [i for i in issues if i.rule == "ancient_date"]
        assert len(ancient) == 1

    def test_invalid_date_format(self):
        extraction = {"invoice_date": "not-a-date"}
        issues = validate_dates(extraction, DocumentType.FREIGHT_INVOICE)
        format_errors = [i for i in issues if i.rule == "invalid_date_format"]
        assert len(format_errors) == 1

    def test_null_date_ok(self):
        extraction = {"invoice_date": None}
        issues = validate_dates(extraction, DocumentType.FREIGHT_INVOICE)
        assert len(issues) == 0


# ─── validate_currency ──────────────────────────────────────────


class TestCurrency:
    def test_valid_currency(self):
        extraction = {"currency": "USD"}
        issues = validate_currency(extraction, DocumentType.FREIGHT_INVOICE)
        assert len(issues) == 0

    def test_invalid_currency(self):
        extraction = {"currency": "FAKE"}
        issues = validate_currency(extraction, DocumentType.FREIGHT_INVOICE)
        assert len(issues) == 1
        assert issues[0].rule == "unknown_currency"

    def test_no_currency_ok(self):
        extraction = {}
        issues = validate_currency(extraction, DocumentType.FREIGHT_INVOICE)
        assert len(issues) == 0


# ─── validate_amounts ───────────────────────────────────────────


class TestAmounts:
    def test_valid_amounts(self, valid_freight_invoice):
        issues = validate_amounts(valid_freight_invoice, DocumentType.FREIGHT_INVOICE)
        assert len(issues) == 0

    def test_negative_amount(self):
        extraction = {"total_amount": -500}
        issues = validate_amounts(extraction, DocumentType.FREIGHT_INVOICE)
        negatives = [i for i in issues if i.rule == "negative_amount"]
        assert len(negatives) == 1

    def test_negative_allowed_for_credit_note(self):
        extraction = {"total_amount": -500}
        issues = validate_amounts(extraction, DocumentType.DEBIT_CREDIT_NOTE)
        negatives = [i for i in issues if i.rule == "negative_amount"]
        assert len(negatives) == 0

    def test_extreme_amount(self):
        extraction = {"total_amount": 500_000_000}
        issues = validate_amounts(extraction, DocumentType.FREIGHT_INVOICE)
        extreme = [i for i in issues if i.rule == "extreme_amount"]
        assert len(extreme) == 1


# ─── validate_reference_numbers ─────────────────────────────────


class TestReferenceNumbers:
    def test_valid_awb(self):
        extraction = {"awb_number": "180-12345675"}
        issues = validate_reference_numbers(extraction, DocumentType.AIR_WAYBILL)
        assert len(issues) == 0

    def test_invalid_awb_length(self):
        extraction = {"awb_number": "12345"}
        issues = validate_reference_numbers(extraction, DocumentType.AIR_WAYBILL)
        assert len(issues) == 1
        assert issues[0].rule == "awb_format"

    def test_valid_entry_number(self):
        extraction = {"entry_number": "12345678901"}
        issues = validate_reference_numbers(extraction, DocumentType.CUSTOMS_ENTRY)
        assert len(issues) == 0


# ─── ValidationService (aggregate) ──────────────────────────────


class TestValidationService:
    def test_valid_invoice_passes(self, valid_freight_invoice):
        result = ValidationService.validate(valid_freight_invoice, DocumentType.FREIGHT_INVOICE)
        assert result.passed is True
        assert result.error_count == 0

    def test_invalid_invoice_fails(self, invalid_freight_invoice):
        result = ValidationService.validate(invalid_freight_invoice, DocumentType.FREIGHT_INVOICE)
        assert result.passed is False
        assert result.error_count > 0
        assert result.warning_count > 0
        # Should have: missing required (2), line_item_math (1), total_computation (1),
        # future_date (1), unknown_currency (1)
        assert len(result.issues) >= 4

    def test_returns_validation_result_type(self, valid_freight_invoice):
        result = ValidationService.validate(valid_freight_invoice, DocumentType.FREIGHT_INVOICE)
        assert isinstance(result, ValidationResult)


# ─── Confidence Scoring (A1) ────────────────────────────────────


class TestAgreementConfidence:
    def test_identical_extractions(self):
        raw = {"invoice_number": "INV-001", "total_amount": 1000}
        refined = {"invoice_number": "INV-001", "total_amount": 1000}
        scores = compute_agreement_confidence(raw, refined)
        assert scores["invoice_number"] == 0.95
        assert scores["total_amount"] == 0.95

    def test_corrected_field(self):
        raw = {"invoice_number": "INV-001", "total_amount": 999}
        refined = {"invoice_number": "INV-001", "total_amount": 1000}
        scores = compute_agreement_confidence(raw, refined)
        assert scores["invoice_number"] == 0.95
        assert scores["total_amount"] == 0.65  # Changed

    def test_field_added_in_review(self):
        raw = {"invoice_number": "INV-001"}
        refined = {"invoice_number": "INV-001", "vendor_name": "Maersk"}
        scores = compute_agreement_confidence(raw, refined)
        assert scores["vendor_name"] == 0.7  # Found in Pass 2 only

    def test_field_removed_in_review(self):
        raw = {"invoice_number": "INV-001", "notes": "test"}
        refined = {"invoice_number": "INV-001", "notes": None}
        scores = compute_agreement_confidence(raw, refined)
        assert scores["notes"] == 0.5  # value→null is lowest confidence

    def test_both_null(self):
        raw = {"notes": None}
        refined = {"notes": None}
        scores = compute_agreement_confidence(raw, refined)
        assert scores["notes"] == 0.9


class TestBlendConfidences:
    def test_blend_with_claude_scores(self):
        agreement = {"invoice_number": 0.95, "total_amount": 0.65}
        claude = {"invoice_number": 0.99, "total_amount": 0.8}
        blended = blend_confidences(agreement, claude)
        # 0.4 * 0.95 + 0.6 * 0.99 = 0.38 + 0.594 = 0.974
        assert abs(blended["invoice_number"] - 0.974) < 0.001
        # 0.4 * 0.65 + 0.6 * 0.8 = 0.26 + 0.48 = 0.74
        assert abs(blended["total_amount"] - 0.74) < 0.001

    def test_blend_without_claude_scores(self):
        agreement = {"invoice_number": 0.95}
        blended = blend_confidences(agreement, None)
        assert blended == agreement

    def test_blend_with_partial_overlap(self):
        agreement = {"invoice_number": 0.95, "notes": 0.9}
        claude = {"invoice_number": 0.99, "vendor_name": 0.85}
        blended = blend_confidences(agreement, claude)
        assert "invoice_number" in blended  # Blended
        assert "notes" in blended  # Agreement only
        assert "vendor_name" in blended  # Claude only
        assert blended["notes"] == 0.9
        assert blended["vendor_name"] == 0.85


class TestOverallConfidence:
    def test_high_confidence(self):
        scores = {"a": 0.95, "b": 0.95, "c": 0.9}
        overall = compute_overall_confidence(scores)
        assert overall > 0.9

    def test_low_confidence_penalty(self):
        scores = {"a": 0.95, "b": 0.4, "c": 0.9}
        overall = compute_overall_confidence(scores)
        # Mean would be 0.75, but penalty for b < 0.6
        assert overall < 0.75

    def test_empty_scores(self):
        assert compute_overall_confidence({}) == 0.0
