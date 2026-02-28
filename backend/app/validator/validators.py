"""
Pure deterministic validation functions for extraction output.

Each validator takes an extraction dict + document type and returns
a list of ValidationIssues. No DB, no Claude, no side effects.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from app.schemas.extraction import DocumentType
from app.schemas.validation import IssueSeverity, ValidationIssue

# ISO 4217 currency codes (common subset for logistics)
_VALID_CURRENCIES = {
    "USD", "EUR", "GBP", "CAD", "AUD", "JPY", "CNY", "HKD", "SGD", "KRW",
    "INR", "MXN", "BRL", "CHF", "SEK", "NOK", "DKK", "NZD", "ZAR", "AED",
    "SAR", "THB", "TWD", "MYR", "PHP", "IDR", "VND", "PKR", "BDT", "EGP",
    "TRY", "PLN", "CZK", "HUF", "RON", "BGN", "HRK", "RUB", "UAH", "CLP",
    "COP", "PEN", "ARS",
}

# Document types that have line_items with qty * unit_price = total
_DOCS_WITH_PRICED_LINE_ITEMS = {
    DocumentType.FREIGHT_INVOICE,
    DocumentType.COMMERCIAL_INVOICE,
    DocumentType.PURCHASE_ORDER,
}

# Document types that have subtotal + tax = total pattern
_DOCS_WITH_TOTALS = {
    DocumentType.FREIGHT_INVOICE,
    DocumentType.COMMERCIAL_INVOICE,
    DocumentType.PURCHASE_ORDER,
    DocumentType.DEBIT_CREDIT_NOTE,
    DocumentType.CUSTOMS_ENTRY,
}

# Required fields per document type (field must be non-null and non-empty)
_REQUIRED_FIELDS: dict[DocumentType, list[str]] = {
    DocumentType.FREIGHT_INVOICE: ["invoice_number", "vendor_name", "total_amount"],
    DocumentType.BILL_OF_LADING: ["bol_number"],
    DocumentType.COMMERCIAL_INVOICE: ["invoice_number", "total_amount"],
    DocumentType.PURCHASE_ORDER: ["po_number", "total_amount"],
    DocumentType.PACKING_LIST: [],
    DocumentType.ARRIVAL_NOTICE: [],
    DocumentType.AIR_WAYBILL: ["awb_number"],
    DocumentType.DEBIT_CREDIT_NOTE: ["note_number", "note_type", "total_amount"],
    DocumentType.CUSTOMS_ENTRY: ["entry_number"],
    DocumentType.PROOF_OF_DELIVERY: [],
    DocumentType.CERTIFICATE_OF_ORIGIN: ["country_of_origin"],
}

# Date fields per document type for sanity checking
_DATE_FIELDS: dict[DocumentType, list[str]] = {
    DocumentType.FREIGHT_INVOICE: ["invoice_date"],
    DocumentType.BILL_OF_LADING: ["issue_date"],
    DocumentType.COMMERCIAL_INVOICE: ["invoice_date"],
    DocumentType.PURCHASE_ORDER: ["po_date", "delivery_date"],
    DocumentType.PACKING_LIST: ["packing_date"],
    DocumentType.ARRIVAL_NOTICE: ["notice_date", "eta", "ata"],
    DocumentType.AIR_WAYBILL: ["issue_date", "flight_date"],
    DocumentType.DEBIT_CREDIT_NOTE: ["note_date", "original_invoice_date"],
    DocumentType.CUSTOMS_ENTRY: ["summary_date", "entry_date", "import_date"],
    DocumentType.PROOF_OF_DELIVERY: ["delivery_date"],
    DocumentType.CERTIFICATE_OF_ORIGIN: ["issue_date", "certification_date"],
}


def _safe_float(val) -> float | None:
    """Safely convert to float, returning None if not numeric."""
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _get_nested(data: dict, path: str):
    """Get a value from nested dict by dot-path."""
    parts = path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def validate_required_fields(
    extraction: dict, doc_type: DocumentType
) -> list[ValidationIssue]:
    """Check that required fields are present and non-empty."""
    issues: list[ValidationIssue] = []
    required = _REQUIRED_FIELDS.get(doc_type, [])

    for field in required:
        value = extraction.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            issues.append(ValidationIssue(
                field=field,
                severity=IssueSeverity.ERROR,
                message=f"Required field '{field}' is missing or empty",
                expected="non-null value",
                actual=str(value),
                rule="missing_required",
            ))

    # Every invoice-type doc should have at least one line item
    if doc_type in _DOCS_WITH_PRICED_LINE_ITEMS:
        line_items = extraction.get("line_items", [])
        if not line_items:
            issues.append(ValidationIssue(
                field="line_items",
                severity=IssueSeverity.WARNING,
                message="No line items found — extraction may be incomplete",
                rule="empty_line_items",
            ))

    return issues


def validate_line_item_math(
    extraction: dict, doc_type: DocumentType
) -> list[ValidationIssue]:
    """Check that qty * unit_price ≈ total for each line item."""
    issues: list[ValidationIssue] = []

    if doc_type not in _DOCS_WITH_PRICED_LINE_ITEMS:
        return issues

    line_items = extraction.get("line_items", [])
    for i, item in enumerate(line_items):
        qty = _safe_float(item.get("quantity"))
        price = _safe_float(item.get("unit_price"))
        total = _safe_float(item.get("total"))

        if qty is None or price is None or total is None:
            continue

        expected_total = qty * price
        if abs(expected_total) < 0.01 and abs(total) < 0.01:
            continue

        # Allow 1% tolerance or $0.02 absolute (rounding)
        abs_diff = abs(expected_total - total)
        rel_diff = abs_diff / max(abs(expected_total), 0.01)

        if abs_diff > 0.02 and rel_diff > 0.01:
            issues.append(ValidationIssue(
                field=f"line_items.{i}.total",
                severity=IssueSeverity.WARNING,
                message=f"Line item {i}: qty({qty}) × price({price}) = {expected_total:.2f}, but total is {total:.2f}",
                expected=f"{expected_total:.2f}",
                actual=f"{total:.2f}",
                rule="line_item_math",
            ))

    return issues


def validate_totals(
    extraction: dict, doc_type: DocumentType
) -> list[ValidationIssue]:
    """Check that line items sum ≈ subtotal, and subtotal + tax ≈ total."""
    issues: list[ValidationIssue] = []

    if doc_type not in _DOCS_WITH_TOTALS:
        return issues

    total_amount = _safe_float(extraction.get("total_amount"))
    subtotal = _safe_float(extraction.get("subtotal"))
    tax_amount = _safe_float(extraction.get("tax_amount", 0))

    if total_amount is None:
        return issues

    # Check: sum of line item totals ≈ subtotal (or total if no subtotal)
    line_items = extraction.get("line_items", [])
    if line_items:
        line_sum = sum(
            _safe_float(item.get("total")) or 0.0
            for item in line_items
        )

        compare_to = subtotal if subtotal is not None else total_amount
        if compare_to and abs(compare_to) > 0.01:
            abs_diff = abs(line_sum - compare_to)
            rel_diff = abs_diff / abs(compare_to)

            # For commercial invoices, total might include freight/insurance
            # so only warn at higher thresholds
            threshold = 0.05 if doc_type == DocumentType.COMMERCIAL_INVOICE else 0.02

            if abs_diff > 0.50 and rel_diff > threshold:
                target = "subtotal" if subtotal is not None else "total_amount"
                issues.append(ValidationIssue(
                    field=target,
                    severity=IssueSeverity.WARNING,
                    message=f"Sum of line items ({line_sum:.2f}) differs from {target} ({compare_to:.2f}) by {abs_diff:.2f}",
                    expected=f"{line_sum:.2f}",
                    actual=f"{compare_to:.2f}",
                    rule="totals_mismatch",
                ))

    # Check: subtotal + tax ≈ total
    if subtotal is not None and total_amount is not None:
        tax = tax_amount if tax_amount is not None else 0
        expected_total = subtotal + tax

        # For commercial invoices, include freight and insurance
        if doc_type == DocumentType.COMMERCIAL_INVOICE:
            freight = _safe_float(extraction.get("freight_charges", 0)) or 0
            insurance = _safe_float(extraction.get("insurance_charges", 0)) or 0
            discount = _safe_float(extraction.get("discount_amount", 0)) or 0
            expected_total = subtotal + tax + freight + insurance - discount

        abs_diff = abs(expected_total - total_amount)
        if abs_diff > 0.50 and abs(total_amount) > 0.01:
            rel_diff = abs_diff / abs(total_amount)
            if rel_diff > 0.02:
                issues.append(ValidationIssue(
                    field="total_amount",
                    severity=IssueSeverity.ERROR,
                    message=f"Computed total ({expected_total:.2f}) differs from stated total ({total_amount:.2f})",
                    expected=f"{expected_total:.2f}",
                    actual=f"{total_amount:.2f}",
                    rule="total_computation",
                ))

    return issues


def validate_dates(
    extraction: dict, doc_type: DocumentType
) -> list[ValidationIssue]:
    """Check date fields for sanity (not future, reasonable range)."""
    issues: list[ValidationIssue] = []
    today = date.today()
    # Documents from the distant past are suspicious (before 2000)
    min_date = date(2000, 1, 1)
    # Allow 30 days in the future for delivery dates, ETAs, etc.
    max_date = today + timedelta(days=30)
    # Strict future fields — these should never be in the future
    strict_past_fields = {"invoice_date", "issue_date", "note_date", "packing_date",
                          "summary_date", "entry_date", "import_date", "certification_date",
                          "po_date", "notice_date", "ata", "delivery_date",
                          "original_invoice_date"}

    date_fields = _DATE_FIELDS.get(doc_type, [])
    for field in date_fields:
        value = extraction.get(field)
        if value is None:
            continue

        # Parse date string
        parsed: date | None = None
        if isinstance(value, str):
            try:
                parsed = date.fromisoformat(value)
            except ValueError:
                issues.append(ValidationIssue(
                    field=field,
                    severity=IssueSeverity.ERROR,
                    message=f"Invalid date format: '{value}' (expected YYYY-MM-DD)",
                    actual=value,
                    rule="invalid_date_format",
                ))
                continue
        elif isinstance(value, date):
            parsed = value
        else:
            continue

        # Check too far in the future
        if field in strict_past_fields and parsed > today:
            issues.append(ValidationIssue(
                field=field,
                severity=IssueSeverity.WARNING,
                message=f"Date {parsed} is in the future",
                actual=str(parsed),
                rule="future_date",
            ))
        elif parsed > max_date:
            issues.append(ValidationIssue(
                field=field,
                severity=IssueSeverity.WARNING,
                message=f"Date {parsed} is more than 30 days in the future",
                actual=str(parsed),
                rule="far_future_date",
            ))

        # Check too old
        if parsed < min_date:
            issues.append(ValidationIssue(
                field=field,
                severity=IssueSeverity.WARNING,
                message=f"Date {parsed} is before year 2000 — possibly incorrect",
                actual=str(parsed),
                rule="ancient_date",
            ))

    return issues


def validate_currency(extraction: dict, doc_type: DocumentType) -> list[ValidationIssue]:
    """Check currency code is valid ISO 4217."""
    issues: list[ValidationIssue] = []

    currency = extraction.get("currency")
    if currency is None:
        return issues

    if not isinstance(currency, str):
        issues.append(ValidationIssue(
            field="currency",
            severity=IssueSeverity.ERROR,
            message=f"Currency must be a string, got {type(currency).__name__}",
            actual=str(currency),
            rule="invalid_currency_type",
        ))
        return issues

    currency_upper = currency.upper().strip()
    if currency_upper not in _VALID_CURRENCIES:
        issues.append(ValidationIssue(
            field="currency",
            severity=IssueSeverity.WARNING,
            message=f"Currency '{currency}' is not a recognized ISO 4217 code",
            actual=currency,
            rule="unknown_currency",
        ))

    return issues


def validate_amounts(
    extraction: dict, doc_type: DocumentType
) -> list[ValidationIssue]:
    """Check monetary amounts for sanity (negatives, unreasonable values)."""
    issues: list[ValidationIssue] = []

    # Fields that should be non-negative (unless credit/debit note)
    amount_fields = ["total_amount", "subtotal", "tax_amount", "freight_charges",
                     "insurance_charges", "total_charges", "total_entered_value",
                     "total_duty"]
    allow_negative = doc_type == DocumentType.DEBIT_CREDIT_NOTE

    for field in amount_fields:
        value = _safe_float(extraction.get(field))
        if value is None:
            continue

        if value < 0 and not allow_negative:
            issues.append(ValidationIssue(
                field=field,
                severity=IssueSeverity.WARNING,
                message=f"Amount '{field}' is negative ({value:.2f})",
                actual=f"{value:.2f}",
                rule="negative_amount",
            ))

        # Unreasonably large (> $100M) — likely a data error
        if abs(value) > 100_000_000:
            issues.append(ValidationIssue(
                field=field,
                severity=IssueSeverity.WARNING,
                message=f"Amount '{field}' ({value:,.2f}) exceeds $100M — verify correctness",
                actual=f"{value:,.2f}",
                rule="extreme_amount",
            ))

    # Check line item amounts
    line_items = extraction.get("line_items", [])
    for i, item in enumerate(line_items):
        total = _safe_float(item.get("total"))
        if total is not None and total < 0 and not allow_negative:
            issues.append(ValidationIssue(
                field=f"line_items.{i}.total",
                severity=IssueSeverity.INFO,
                message=f"Line item {i} has negative total ({total:.2f}) — may be a discount/credit",
                actual=f"{total:.2f}",
                rule="negative_line_item",
            ))

    return issues


def validate_reference_numbers(
    extraction: dict, doc_type: DocumentType
) -> list[ValidationIssue]:
    """Check reference number formats for common issues."""
    issues: list[ValidationIssue] = []

    # AWB number should be 11 digits (3-digit airline prefix + 8-digit serial)
    if doc_type == DocumentType.AIR_WAYBILL:
        awb = extraction.get("awb_number", "")
        if awb:
            digits = re.sub(r"[\s\-]", "", awb)
            if not digits.isdigit() or len(digits) != 11:
                issues.append(ValidationIssue(
                    field="awb_number",
                    severity=IssueSeverity.INFO,
                    message=f"AWB number '{awb}' doesn't match expected 11-digit IATA format",
                    expected="11 digits (e.g., 180-12345675)",
                    actual=awb,
                    rule="awb_format",
                ))

    # Customs entry number should be 11 characters
    if doc_type == DocumentType.CUSTOMS_ENTRY:
        entry = extraction.get("entry_number", "")
        if entry:
            cleaned = re.sub(r"[\s\-]", "", entry)
            if len(cleaned) != 11:
                issues.append(ValidationIssue(
                    field="entry_number",
                    severity=IssueSeverity.INFO,
                    message=f"Entry number '{entry}' doesn't match expected 11-character CBP format",
                    expected="11 characters",
                    actual=entry,
                    rule="entry_number_format",
                ))

    return issues


# --- Aggregate ---

ALL_VALIDATORS = [
    validate_required_fields,
    validate_line_item_math,
    validate_totals,
    validate_dates,
    validate_currency,
    validate_amounts,
    validate_reference_numbers,
]
