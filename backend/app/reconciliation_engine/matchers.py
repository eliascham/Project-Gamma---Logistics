"""Pure matching functions for reconciliation — no DB or Claude dependency."""

from datetime import datetime


def match_by_reference(
    ref_a: str | None,
    ref_b: str | None,
) -> tuple[bool, float]:
    """Match two records by reference number (exact match).

    Returns (is_match, confidence).
    """
    if not ref_a or not ref_b:
        return False, 0.0

    if ref_a.strip().lower() == ref_b.strip().lower():
        return True, 1.0

    return False, 0.0


def match_by_amount(
    amount_a: float | None,
    amount_b: float | None,
    tolerance_pct: float = 0.02,
) -> tuple[bool, float]:
    """Match by amount with tolerance (default 2%).

    Returns (is_match, confidence).
    """
    if amount_a is None or amount_b is None:
        return False, 0.0

    if amount_a == 0 and amount_b == 0:
        return True, 1.0

    if amount_a == 0 or amount_b == 0:
        return False, 0.0

    diff_pct = abs(amount_a - amount_b) / max(abs(amount_a), abs(amount_b))

    if diff_pct <= tolerance_pct:
        confidence = 1.0 - (diff_pct / tolerance_pct) * 0.2
        return True, round(confidence, 3)

    return False, 0.0


def match_by_date(
    date_a: str | None,
    date_b: str | None,
    tolerance_days: int = 3,
) -> tuple[bool, float]:
    """Match by date with tolerance (default 3 days).

    Dates should be ISO format strings.
    Returns (is_match, confidence).
    """
    if not date_a or not date_b:
        return False, 0.0

    try:
        dt_a = datetime.fromisoformat(date_a.replace("Z", "+00:00"))
        dt_b = datetime.fromisoformat(date_b.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return False, 0.0

    diff_days = abs((dt_a - dt_b).days)

    if diff_days <= tolerance_days:
        confidence = 1.0 - (diff_days / tolerance_days) * 0.3
        return True, round(confidence, 3)

    return False, 0.0


def compute_composite_confidence(
    ref_match: float,
    amount_match: float,
    date_match: float,
) -> float:
    """Compute composite match confidence from individual match scores.

    Weights: reference=0.5, amount=0.3, date=0.2
    """
    return round(ref_match * 0.5 + amount_match * 0.3 + date_match * 0.2, 3)
