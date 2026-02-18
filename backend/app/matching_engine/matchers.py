"""Pure matching functions for 3-way PO-BOL-Invoice matching — no DB or Claude dependency."""

import enum
from dataclasses import dataclass, field


class MatchStatus(str, enum.Enum):
    FULL_MATCH = "full_match"
    PARTIAL_MATCH = "partial_match"
    MISMATCH = "mismatch"
    INCOMPLETE = "incomplete"


# Configurable tolerance thresholds
MATCH_TOLERANCES = {
    "quantity_pct": 0.05,       # 5% quantity variance
    "quantity_abs": 1,          # or 1 unit absolute
    "unit_price_pct": 0.03,     # 3% price variance
    "unit_price_abs": 0.01,     # or $0.01 absolute
    "total_amount_pct": 0.05,   # 5% total variance
    "total_amount_abs": 100,    # or $100 absolute (whichever is greater)
}


@dataclass
class FieldMatch:
    """Result of matching a single field."""

    field_name: str
    matched: bool
    confidence: float
    po_value: str | float | None = None
    bol_value: str | float | None = None
    invoice_value: str | float | None = None
    note: str | None = None


@dataclass
class LineItemMatch:
    """Result of matching line items across documents."""

    po_index: int | None = None
    invoice_index: int | None = None
    description_match: float = 0.0
    quantity_match: float = 0.0
    unit_price_match: float = 0.0
    overall: float = 0.0
    notes: list[str] = field(default_factory=list)


@dataclass
class MatchResult:
    """Complete 3-way match result."""

    status: MatchStatus
    overall_confidence: float
    field_matches: list[FieldMatch] = field(default_factory=list)
    line_item_matches: list[LineItemMatch] = field(default_factory=list)
    missing_documents: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def match_numeric(
    value_a: float | None,
    value_b: float | None,
    tolerance_pct: float = 0.05,
    tolerance_abs: float = 0.0,
) -> tuple[bool, float]:
    """Match two numeric values within tolerance.

    Returns (is_match, confidence).
    Uses the more permissive of percentage or absolute tolerance.
    """
    if value_a is None or value_b is None:
        return False, 0.0

    if value_a == 0 and value_b == 0:
        return True, 1.0

    if value_a == 0 or value_b == 0:
        return False, 0.0

    diff = abs(value_a - value_b)
    max_val = max(abs(value_a), abs(value_b))
    diff_pct = diff / max_val

    # Match if within either tolerance
    within_pct = diff_pct <= tolerance_pct
    within_abs = diff <= tolerance_abs if tolerance_abs > 0 else False

    if within_pct or within_abs:
        # Confidence based on how close the match is
        if diff == 0:
            return True, 1.0
        ratio = min(diff_pct / tolerance_pct, 1.0) if tolerance_pct > 0 else 0.0
        confidence = 1.0 - ratio * 0.2
        return True, round(confidence, 3)

    return False, 0.0


def match_party_name(name_a: str | None, name_b: str | None) -> tuple[bool, float]:
    """Fuzzy match two party/company names.

    Normalizes by lowercasing, stripping common suffixes (LLC, Inc, Co, Ltd, etc.),
    and comparing.
    """
    if not name_a or not name_b:
        return False, 0.0

    def normalize(name: str) -> str:
        n = name.lower().strip()
        for suffix in [" llc", " inc", " inc.", " co", " co.", " ltd", " ltd.",
                       " corp", " corp.", " corporation", " company",
                       " limited", " gmbh", " sa", " s.a."]:
            if n.endswith(suffix):
                n = n[: -len(suffix)].strip()
        # Remove punctuation
        n = n.replace(",", "").replace(".", "").replace("-", " ")
        return " ".join(n.split())

    norm_a = normalize(name_a)
    norm_b = normalize(name_b)

    if not norm_a or not norm_b:
        return False, 0.0

    if norm_a == norm_b:
        return True, 1.0

    # Check if one contains the other
    if norm_a in norm_b or norm_b in norm_a:
        return True, 0.85

    return False, 0.0


def match_description(desc_a: str | None, desc_b: str | None) -> tuple[bool, float]:
    """Simple word-overlap matching for item descriptions.

    Uses Jaccard similarity on word tokens.
    """
    if not desc_a or not desc_b:
        return False, 0.0

    words_a = set(desc_a.lower().split())
    words_b = set(desc_b.lower().split())

    if not words_a or not words_b:
        return False, 0.0

    intersection = words_a & words_b
    union = words_a | words_b

    jaccard = len(intersection) / len(union)

    if jaccard >= 0.5:
        return True, round(jaccard, 3)

    return False, round(jaccard, 3)


def match_line_items(
    po_items: list[dict],
    invoice_items: list[dict],
    tolerances: dict | None = None,
) -> list[LineItemMatch]:
    """Match PO line items against invoice line items.

    Uses description similarity to pair items, then compares quantity and price.
    """
    tol = tolerances or MATCH_TOLERANCES
    results: list[LineItemMatch] = []

    # Simple greedy matching: for each PO item, find the best invoice item match
    used_invoice_indices: set[int] = set()

    for po_idx, po_item in enumerate(po_items):
        best_inv_idx = None
        best_desc_score = 0.0

        for inv_idx, inv_item in enumerate(invoice_items):
            if inv_idx in used_invoice_indices:
                continue

            _, desc_score = match_description(
                po_item.get("description"), inv_item.get("description")
            )
            if desc_score > best_desc_score:
                best_desc_score = desc_score
                best_inv_idx = inv_idx

        if best_inv_idx is not None and best_desc_score >= 0.3:
            used_invoice_indices.add(best_inv_idx)
            inv_item = invoice_items[best_inv_idx]

            _, qty_score = match_numeric(
                po_item.get("quantity"),
                inv_item.get("quantity"),
                tol["quantity_pct"],
                tol["quantity_abs"],
            )
            _, price_score = match_numeric(
                po_item.get("unit_price"),
                inv_item.get("unit_price"),
                tol["unit_price_pct"],
                tol["unit_price_abs"],
            )

            overall = best_desc_score * 0.3 + qty_score * 0.4 + price_score * 0.3

            notes = []
            if qty_score == 0:
                notes.append(
                    f"Quantity mismatch: PO={po_item.get('quantity')} vs Invoice={inv_item.get('quantity')}"
                )
            if price_score == 0:
                notes.append(
                    f"Price mismatch: PO={po_item.get('unit_price')} vs Invoice={inv_item.get('unit_price')}"
                )

            results.append(LineItemMatch(
                po_index=po_idx,
                invoice_index=best_inv_idx,
                description_match=best_desc_score,
                quantity_match=qty_score,
                unit_price_match=price_score,
                overall=round(overall, 3),
                notes=notes,
            ))
        else:
            results.append(LineItemMatch(
                po_index=po_idx,
                invoice_index=None,
                description_match=best_desc_score,
                overall=0.0,
                notes=[f"No matching invoice line item found for PO item {po_idx}"],
            ))

    return results


def compute_three_way_match(
    po_data: dict | None,
    bol_data: dict | None,
    invoice_data: dict | None,
    tolerances: dict | None = None,
) -> MatchResult:
    """Compute a 3-way match across PO, BOL/Packing List, and Invoice.

    Args:
        po_data: Purchase order extraction dict (or None if missing).
        bol_data: Bill of Lading or Packing List extraction dict (or None).
        invoice_data: Commercial invoice extraction dict (or None).
        tolerances: Override default tolerance thresholds.

    Returns:
        MatchResult with per-field scores and overall status.
    """
    tol = tolerances or MATCH_TOLERANCES
    field_matches: list[FieldMatch] = []
    line_item_matches: list[LineItemMatch] = []
    missing: list[str] = []
    notes: list[str] = []

    if po_data is None:
        missing.append("purchase_order")
    if bol_data is None:
        missing.append("bill_of_lading_or_packing_list")
    if invoice_data is None:
        missing.append("commercial_invoice")

    if len(missing) >= 2:
        return MatchResult(
            status=MatchStatus.INCOMPLETE,
            overall_confidence=0.0,
            missing_documents=missing,
            notes=["At least 2 of 3 documents are required for matching"],
        )

    # --- Party matching (PO supplier vs Invoice seller) ---
    if po_data and invoice_data:
        po_supplier = _get_party_name(po_data, "supplier")
        inv_seller = _get_party_name(invoice_data, "seller")
        matched, conf = match_party_name(po_supplier, inv_seller)
        field_matches.append(FieldMatch(
            field_name="party_name",
            matched=matched,
            confidence=conf,
            po_value=po_supplier,
            invoice_value=inv_seller,
        ))

    # --- Total amount matching (PO vs Invoice) ---
    if po_data and invoice_data:
        po_total = po_data.get("total_amount")
        inv_total = invoice_data.get("total_amount")
        matched, conf = match_numeric(
            po_total, inv_total,
            tol["total_amount_pct"],
            tol["total_amount_abs"],
        )
        field_matches.append(FieldMatch(
            field_name="total_amount",
            matched=matched,
            confidence=conf,
            po_value=po_total,
            invoice_value=inv_total,
        ))

    # --- Line item matching (PO vs Invoice) ---
    if po_data and invoice_data:
        po_items = po_data.get("line_items", [])
        inv_items = invoice_data.get("line_items", [])
        if po_items and inv_items:
            line_item_matches = match_line_items(po_items, inv_items, tol)

    # --- Weight matching (BOL/Packing vs BOL cross-check) ---
    if bol_data:
        bol_weight = bol_data.get("gross_weight") or bol_data.get("total_gross_weight")
        if bol_weight and invoice_data:
            # No direct weight on invoice, but we note it's available from BOL
            notes.append(f"BOL gross weight: {bol_weight} {bol_data.get('weight_unit', '')}")

    # --- Compute overall status ---
    all_confidences = [fm.confidence for fm in field_matches if fm.matched]
    li_confidences = [lm.overall for lm in line_item_matches if lm.overall > 0]
    all_scores = all_confidences + li_confidences

    if missing:
        status = MatchStatus.INCOMPLETE
        overall = sum(all_scores) / max(len(all_scores), 1)
    elif not all_scores:
        status = MatchStatus.MISMATCH
        overall = 0.0
    else:
        overall = sum(all_scores) / len(all_scores)
        mismatched_fields = [fm for fm in field_matches if not fm.matched]
        mismatched_lines = [lm for lm in line_item_matches if lm.overall < 0.5]

        if not mismatched_fields and not mismatched_lines and overall >= 0.8:
            status = MatchStatus.FULL_MATCH
        elif overall >= 0.5:
            status = MatchStatus.PARTIAL_MATCH
        else:
            status = MatchStatus.MISMATCH

    return MatchResult(
        status=status,
        overall_confidence=round(overall, 3),
        field_matches=field_matches,
        line_item_matches=line_item_matches,
        missing_documents=missing,
        notes=notes,
    )


def _get_party_name(data: dict, field: str) -> str | None:
    """Extract a party name from extraction data (handles dict or string)."""
    party = data.get(field)
    if isinstance(party, dict):
        return party.get("name")
    if isinstance(party, str):
        return party
    return None
