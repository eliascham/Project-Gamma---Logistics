"""
Per-field confidence scoring for extractions.

Two signals blended together:
1. Agreement-based: compare Pass 1 (raw) vs Pass 2 (refined) extraction.
   Fields that match get higher confidence; corrected fields get lower.
2. Claude-reported: if the review pass returns field_confidences, blend them in.

Final = weighted blend of both signals.
"""

from __future__ import annotations


def _flatten_dict(d: dict, prefix: str = "") -> dict[str, object]:
    """Flatten a nested dict into dot-path keys.

    Lists are skipped (we score top-level and nested dict fields, not list items).
    """
    flat: dict[str, object] = {}
    for key, value in d.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(_flatten_dict(value, full_key))
        elif isinstance(value, list):
            # For lists, just store length as a proxy for comparison
            flat[full_key] = f"__list_len_{len(value)}__"
        else:
            flat[full_key] = value
    return flat


def compute_agreement_confidence(
    raw_extraction: dict,
    refined_extraction: dict,
) -> dict[str, float]:
    """Compute per-field confidence from Pass 1 vs Pass 2 agreement.

    Scoring rules:
    - Both null → 0.9 (both passes agree field is absent)
    - Both match → 0.95 (strong agreement)
    - Pass 1 null, Pass 2 has value → 0.7 (review found something missed)
    - Pass 1 has value, Pass 2 null → 0.5 (review removed it — suspicious)
    - Values differ → 0.65 (correction made — less certain)

    Returns:
        Dict mapping dot-path field names to confidence scores (0.0 - 1.0).
    """
    raw_flat = _flatten_dict(raw_extraction)
    refined_flat = _flatten_dict(refined_extraction)

    # Union of all fields from both passes
    all_fields = set(raw_flat.keys()) | set(refined_flat.keys())

    confidences: dict[str, float] = {}
    for field in all_fields:
        raw_val = raw_flat.get(field)
        ref_val = refined_flat.get(field)

        if raw_val is None and ref_val is None:
            confidences[field] = 0.9
        elif raw_val == ref_val:
            confidences[field] = 0.95
        elif raw_val is None and ref_val is not None:
            confidences[field] = 0.7
        elif raw_val is not None and ref_val is None:
            confidences[field] = 0.5
        else:
            # Values differ — correction was made
            confidences[field] = 0.65

    return confidences


def blend_confidences(
    agreement_scores: dict[str, float],
    claude_scores: dict[str, float] | None = None,
    agreement_weight: float = 0.4,
    claude_weight: float = 0.6,
) -> dict[str, float]:
    """Blend agreement-based and Claude-reported confidence scores.

    If Claude scores are not available, returns agreement scores as-is.

    Args:
        agreement_scores: From compute_agreement_confidence().
        claude_scores: From Claude's review pass (optional).
        agreement_weight: Weight for agreement signal (default 0.4).
        claude_weight: Weight for Claude signal (default 0.6).

    Returns:
        Blended confidence scores per field.
    """
    if claude_scores is None:
        return agreement_scores

    # Merge: for fields in both, blend; for fields in one only, use available
    all_fields = set(agreement_scores.keys()) | set(claude_scores.keys())
    blended: dict[str, float] = {}

    for field in all_fields:
        agree = agreement_scores.get(field)
        claude = claude_scores.get(field)

        if agree is not None and claude is not None:
            blended[field] = (agreement_weight * agree) + (claude_weight * claude)
        elif agree is not None:
            blended[field] = agree
        elif claude is not None:
            blended[field] = claude

    return blended


def compute_overall_confidence(field_confidences: dict[str, float]) -> float:
    """Compute a single overall confidence score from per-field scores.

    Uses the mean of all field scores, but weighted down if any field
    is below 0.6 (low-confidence fields drag down the overall score).
    """
    if not field_confidences:
        return 0.0

    scores = list(field_confidences.values())
    mean = sum(scores) / len(scores)

    # Count low-confidence fields
    low_conf_count = sum(1 for s in scores if s < 0.6)
    if low_conf_count > 0:
        # Penalty: reduce mean by 5% per low-confidence field (capped)
        penalty = min(low_conf_count * 0.05, 0.3)
        mean = max(mean - penalty, 0.1)

    return round(mean, 4)
