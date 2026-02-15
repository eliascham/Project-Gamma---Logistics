"""
Extraction accuracy metrics.

Compares Claude extraction outputs against ground truth at the field level.
Supports:
- Exact string matching (normalized)
- Numeric matching with tolerance (±0.01)
- Date format normalization
- Line item matching (order-independent, by description similarity)
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import date

logger = logging.getLogger("gamma.eval.metrics")

# Numeric tolerance for amounts (handles floating point)
NUMERIC_TOLERANCE = 0.01


@dataclass
class FieldScore:
    """Accuracy score for a single field."""

    field_name: str
    expected: str | None = None
    actual: str | None = None
    match: bool = False
    score: float = 0.0  # 0.0 or 1.0 for exact, 0.0-1.0 for partial


@dataclass
class ExtractionScore:
    """Overall extraction accuracy score."""

    field_scores: list[FieldScore] = field(default_factory=list)
    line_item_score: float = 0.0
    overall_accuracy: float = 0.0
    fields_matched: int = 0
    fields_total: int = 0

    def to_dict(self) -> dict:
        return {
            "overall_accuracy": round(self.overall_accuracy, 4),
            "fields_matched": self.fields_matched,
            "fields_total": self.fields_total,
            "line_item_score": round(self.line_item_score, 4),
            "field_scores": {
                fs.field_name: {
                    "match": fs.match,
                    "score": round(fs.score, 4),
                    "expected": fs.expected,
                    "actual": fs.actual,
                }
                for fs in self.field_scores
            },
        }


def _normalize_string(value: str | None) -> str:
    """Normalize a string for comparison (lowercase, strip whitespace, collapse spaces, strip punctuation)."""
    if value is None:
        return ""
    s = str(value).strip().lower()
    # Remove commas and periods that are just formatting (e.g., "Dallas, TX" vs "Dallas TX")
    s = re.sub(r"[,.]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _normalize_date(value) -> str:
    """Normalize a date to YYYY-MM-DD string."""
    if value is None:
        return ""
    if isinstance(value, date):
        return value.isoformat()
    s = str(value).strip()
    # Already ISO format
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    return s


def _compare_numeric(expected, actual, tolerance: float = NUMERIC_TOLERANCE) -> bool:
    """Compare two numeric values with tolerance."""
    try:
        e = float(expected) if expected is not None else None
        a = float(actual) if actual is not None else None
    except (ValueError, TypeError):
        return False

    if e is None and a is None:
        return True
    if e is None or a is None:
        return False
    return abs(e - a) <= tolerance


def _compare_strings(expected, actual) -> bool:
    """Compare two values as normalized strings."""
    return _normalize_string(expected) == _normalize_string(actual)


def compute_field_accuracy(
    expected: dict, actual: dict, field_name: str
) -> FieldScore:
    """Compare a single field between expected and actual extraction."""
    e_val = expected.get(field_name)
    a_val = actual.get(field_name)

    e_str = str(e_val) if e_val is not None else None
    a_str = str(a_val) if a_val is not None else None

    # Both null = match
    if e_val is None and a_val is None:
        return FieldScore(field_name=field_name, expected=e_str, actual=a_str, match=True, score=1.0)

    # One null, other not = no match
    if e_val is None or a_val is None:
        return FieldScore(field_name=field_name, expected=e_str, actual=a_str, match=False, score=0.0)

    # Numeric fields
    if isinstance(e_val, (int, float)) or isinstance(a_val, (int, float)):
        is_match = _compare_numeric(e_val, a_val)
        return FieldScore(
            field_name=field_name, expected=e_str, actual=a_str,
            match=is_match, score=1.0 if is_match else 0.0,
        )

    # Date fields (contains "date" in name)
    if "date" in field_name.lower():
        e_date = _normalize_date(e_val)
        a_date = _normalize_date(a_val)
        is_match = e_date == a_date
        return FieldScore(
            field_name=field_name, expected=e_date, actual=a_date,
            match=is_match, score=1.0 if is_match else 0.0,
        )

    # String comparison
    is_match = _compare_strings(e_val, a_val)
    return FieldScore(
        field_name=field_name, expected=e_str, actual=a_str,
        match=is_match, score=1.0 if is_match else 0.0,
    )


def compute_line_item_score(expected_items: list[dict], actual_items: list[dict]) -> float:
    """Score line item extraction accuracy (order-independent matching).

    Matches items by description similarity, then checks amounts.
    Returns a score from 0.0 to 1.0.
    """
    if not expected_items and not actual_items:
        return 1.0
    if not expected_items or not actual_items:
        return 0.0

    matched = 0
    used_actual = set()

    for exp_item in expected_items:
        exp_desc = _normalize_string(exp_item.get("description", ""))
        best_match_idx = None
        best_match_score = 0.0

        for i, act_item in enumerate(actual_items):
            if i in used_actual:
                continue

            act_desc = _normalize_string(act_item.get("description", ""))

            # Simple substring match scoring
            if exp_desc == act_desc:
                desc_score = 1.0
            elif exp_desc in act_desc or act_desc in exp_desc:
                desc_score = 0.8
            else:
                # Word overlap
                exp_words = set(exp_desc.split())
                act_words = set(act_desc.split())
                if exp_words and act_words:
                    overlap = len(exp_words & act_words) / max(len(exp_words), len(act_words))
                    desc_score = overlap * 0.6
                else:
                    desc_score = 0.0

            if desc_score > best_match_score:
                best_match_score = desc_score
                best_match_idx = i

        if best_match_idx is not None and best_match_score >= 0.5:
            used_actual.add(best_match_idx)
            act_item = actual_items[best_match_idx]

            # Score the matched item: description match + total match
            total_match = _compare_numeric(
                exp_item.get("total"), act_item.get("total")
            )
            item_score = (best_match_score + (1.0 if total_match else 0.0)) / 2.0
            matched += item_score

    # Penalize for extra items in actual
    precision = matched / len(actual_items) if actual_items else 0
    recall = matched / len(expected_items) if expected_items else 0

    if precision + recall == 0:
        return 0.0
    return 2 * (precision * recall) / (precision + recall)  # F1


def compute_extraction_score(
    expected: dict,
    actual: dict,
    scalar_fields: list[str],
    line_items_field: str | None = "line_items",
) -> ExtractionScore:
    """Compute overall extraction accuracy.

    Args:
        expected: Ground truth extraction dict.
        actual: Claude extraction output dict.
        scalar_fields: List of field names to compare (excluding line items).
        line_items_field: Field name for line items (None to skip).

    Returns:
        ExtractionScore with field-level and overall accuracy.
    """
    field_scores = []

    for field_name in scalar_fields:
        score = compute_field_accuracy(expected, actual, field_name)
        field_scores.append(score)

    # Line items
    line_item_score = 0.0
    if line_items_field:
        exp_items = expected.get(line_items_field, [])
        act_items = actual.get(line_items_field, [])
        if isinstance(exp_items, list) and isinstance(act_items, list):
            line_item_score = compute_line_item_score(exp_items, act_items)

    # Overall accuracy
    fields_matched = sum(1 for fs in field_scores if fs.match)
    fields_total = len(field_scores)

    # Weight: scalar fields contribute 70%, line items 30%
    if fields_total > 0:
        scalar_accuracy = fields_matched / fields_total
        if line_items_field:
            overall = scalar_accuracy * 0.7 + line_item_score * 0.3
        else:
            overall = scalar_accuracy
    else:
        overall = line_item_score

    return ExtractionScore(
        field_scores=field_scores,
        line_item_score=line_item_score,
        overall_accuracy=overall,
        fields_matched=fields_matched,
        fields_total=fields_total,
    )
