"""ReviewTriggers — pure functions to determine if items need HITL review.

No DB or service dependencies, easy to unit test.
"""


def should_review_allocation(
    total_amount: float | None,
    min_confidence: float | None,
    *,
    confidence_threshold: float = 0.85,
    auto_approve_dollar_threshold: float = 1000.0,
    high_risk_dollar_threshold: float = 10000.0,
) -> tuple[bool, str]:
    """Determine if a cost allocation should be sent for HITL review.

    Returns (needs_review, reason).
    """
    if min_confidence is not None and min_confidence < confidence_threshold:
        return True, f"Low confidence ({min_confidence:.2f} < {confidence_threshold})"

    if total_amount is not None and total_amount >= high_risk_dollar_threshold:
        return True, f"High-value allocation (${total_amount:,.2f} >= ${high_risk_dollar_threshold:,.2f})"

    return False, "Auto-approved"


def should_review_anomaly(
    severity: str,
    anomaly_type: str,
) -> tuple[bool, str]:
    """Determine if an anomaly should be sent for HITL review.

    All anomalies with severity >= medium go to review.
    """
    if severity in ("high", "critical"):
        return True, f"High-severity anomaly: {anomaly_type}"

    if severity == "medium":
        return True, f"Medium-severity anomaly: {anomaly_type}"

    # Low severity — informational only
    return False, "Low-severity, informational only"


def should_review_reconciliation(
    match_confidence: float | None,
    mismatch_count: int,
    total_records: int,
) -> tuple[bool, str]:
    """Determine if a reconciliation run should be sent for HITL review.

    Review if match rate is below 90% or there are any mismatches.
    """
    if mismatch_count > 0:
        return True, f"{mismatch_count} mismatched records found"

    if total_records > 0:
        match_rate = (total_records - mismatch_count) / total_records
        if match_rate < 0.9:
            return True, f"Low match rate ({match_rate:.1%})"

    return False, "All records matched"
