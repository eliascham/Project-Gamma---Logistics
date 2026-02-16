"""Pure anomaly detection functions — no DB or Claude dependency, easy to unit test."""

from datetime import datetime, timedelta


def detect_duplicate(
    invoice_number: str,
    vendor: str,
    existing_invoices: list[dict],
    window_days: int = 90,
) -> dict | None:
    """Detect duplicate invoices (same invoice# + vendor within window).

    Args:
        invoice_number: The invoice number to check
        vendor: The vendor name
        existing_invoices: List of dicts with keys: invoice_number, vendor, date, document_id
        window_days: Number of days to look back

    Returns:
        Dict with duplicate details if found, None otherwise.
    """
    for inv in existing_invoices:
        if (
            inv.get("invoice_number") == invoice_number
            and inv.get("vendor", "").lower() == vendor.lower()
        ):
            return {
                "duplicate_of_document_id": inv.get("document_id"),
                "original_date": inv.get("date"),
                "invoice_number": invoice_number,
                "vendor": vendor,
            }
    return None


def detect_budget_overrun(
    project_code: str,
    new_amount: float,
    budget_amount: float,
    spent_amount: float,
    threshold: float = 0.1,
) -> dict | None:
    """Detect if adding new_amount would exceed budget by more than threshold.

    Args:
        project_code: Project code
        new_amount: Amount being allocated
        budget_amount: Total budget
        spent_amount: Already spent
        threshold: Overrun threshold (0.1 = 10% over budget)

    Returns:
        Dict with overrun details if triggered, None otherwise.
    """
    if budget_amount <= 0:
        return None

    projected_total = spent_amount + new_amount
    overrun_pct = (projected_total - budget_amount) / budget_amount

    if overrun_pct > threshold:
        return {
            "project_code": project_code,
            "budget_amount": budget_amount,
            "spent_amount": spent_amount,
            "new_amount": new_amount,
            "projected_total": round(projected_total, 2),
            "overrun_pct": round(overrun_pct * 100, 1),
        }
    return None


def detect_low_confidence_items(
    line_items: list[dict],
    confidence_threshold: float = 0.85,
) -> list[dict]:
    """Detect line items with confidence below threshold.

    Args:
        line_items: List of dicts with keys: description, amount, confidence, index
        confidence_threshold: Minimum acceptable confidence

    Returns:
        List of flagged items with details.
    """
    flagged = []
    for item in line_items:
        conf = item.get("confidence", 1.0)
        if conf < confidence_threshold:
            flagged.append({
                "line_item_index": item.get("index", 0),
                "description": item.get("description", ""),
                "amount": item.get("amount", 0),
                "confidence": conf,
                "gap": round(confidence_threshold - conf, 3),
            })
    return flagged


def detect_unusual_amount(
    amount: float,
    historical_amounts: list[float],
    std_multiplier: float = 3.0,
) -> dict | None:
    """Detect amounts that are statistical outliers vs historical data.

    Uses simple mean ± (std_multiplier × std_dev) check.

    Returns:
        Dict with outlier details if triggered, None otherwise.
    """
    if len(historical_amounts) < 5:
        return None

    mean = sum(historical_amounts) / len(historical_amounts)
    variance = sum((x - mean) ** 2 for x in historical_amounts) / len(historical_amounts)
    std_dev = variance ** 0.5

    if std_dev == 0:
        return None

    z_score = abs(amount - mean) / std_dev

    if z_score > std_multiplier:
        return {
            "amount": amount,
            "mean": round(mean, 2),
            "std_dev": round(std_dev, 2),
            "z_score": round(z_score, 2),
            "historical_count": len(historical_amounts),
        }
    return None
