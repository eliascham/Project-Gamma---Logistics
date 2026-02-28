"""
Invoice-to-Shipment Reconciler — matches an extracted invoice against a pool
of shipment records, returning ranked candidates with scores.

This is the vertical-slice reconciliation described in the Notion spec:
  Invoice extraction → fuzzy match against shipments → ranked candidates

Uses pure functions from matching_engine and reconciliation_engine matchers.
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass, field

from app.matching_engine.matchers import match_numeric, match_party_name
from app.reconciliation_engine.matchers import match_by_date, match_by_reference

logger = logging.getLogger("gamma.invoice_reconciler")


class CandidateStatus(str, enum.Enum):
    STRONG_MATCH = "strong_match"     # score >= 0.85
    LIKELY_MATCH = "likely_match"     # 0.65 <= score < 0.85
    POSSIBLE_MATCH = "possible_match" # 0.40 <= score < 0.65
    WEAK_MATCH = "weak_match"         # score < 0.40


@dataclass
class MatchDiff:
    """Difference between invoice and shipment for a specific field."""
    field: str
    invoice_value: str | float | None
    shipment_value: str | float | None
    matched: bool
    confidence: float
    note: str = ""


@dataclass
class ReconciliationCandidate:
    """A shipment that could match the invoice, with scoring details."""
    shipment_id: str
    shipment_ref: str
    match_score: float
    status: CandidateStatus
    match_reasons: list[str] = field(default_factory=list)
    diffs: list[MatchDiff] = field(default_factory=list)
    shipment_data: dict = field(default_factory=dict)

    @property
    def has_diffs(self) -> bool:
        return any(not d.matched for d in self.diffs)


@dataclass
class InvoiceReconciliationResult:
    """Full result of reconciling an invoice against shipments."""
    invoice_number: str
    invoice_vendor: str | None
    invoice_total: float | None
    candidates: list[ReconciliationCandidate]
    best_match: ReconciliationCandidate | None
    auto_match: bool  # True if single strong match — can auto-approve
    exceptions: list[str] = field(default_factory=list)

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)

    @property
    def has_match(self) -> bool:
        return self.best_match is not None


# --- Scoring weights ---
WEIGHTS = {
    "po_number": 0.30,     # PO exact match (highest signal)
    "vendor_name": 0.25,   # Fuzzy vendor match
    "total_amount": 0.25,  # Amount within tolerance
    "date": 0.15,          # Date window match
    "reference": 0.05,     # Invoice reference match (on shipment side)
}


def _classify_candidate(score: float) -> CandidateStatus:
    if score >= 0.85:
        return CandidateStatus.STRONG_MATCH
    elif score >= 0.65:
        return CandidateStatus.LIKELY_MATCH
    elif score >= 0.40:
        return CandidateStatus.POSSIBLE_MATCH
    else:
        return CandidateStatus.WEAK_MATCH


def score_invoice_against_shipment(
    invoice: dict,
    shipment: dict,
    amount_tolerance_pct: float = 0.05,
    amount_tolerance_abs: float = 100.0,
    date_tolerance_days: int = 7,
) -> tuple[float, list[str], list[MatchDiff]]:
    """Score how well an invoice matches a single shipment.

    Args:
        invoice: Extraction dict from the invoice.
        shipment: Shipment record dict (from mock_logistics_data or real TMS).
        amount_tolerance_pct: Percentage tolerance for amount matching.
        amount_tolerance_abs: Absolute tolerance for amount matching.
        date_tolerance_days: Date window tolerance.

    Returns:
        Tuple of (score, reasons, diffs).
    """
    score = 0.0
    reasons: list[str] = []
    diffs: list[MatchDiff] = []
    weights_used = 0.0

    # 1. PO Number exact match
    invoice_po = (
        invoice.get("po_number")
        or invoice.get("order_number")
        or invoice.get("reference_number")
    )
    shipment_po = shipment.get("po_number") or shipment.get("purchase_order")
    if invoice_po and shipment_po:
        ref_matched, ref_conf = match_by_reference(invoice_po, shipment_po)
        score += WEIGHTS["po_number"] * ref_conf
        weights_used += WEIGHTS["po_number"]
        diffs.append(MatchDiff(
            field="po_number", invoice_value=invoice_po,
            shipment_value=shipment_po, matched=ref_matched,
            confidence=ref_conf,
            note="PO number exact match" if ref_matched else "PO numbers differ",
        ))
        if ref_matched:
            reasons.append(f"PO match: {invoice_po}")
    elif invoice_po or shipment_po:
        diffs.append(MatchDiff(
            field="po_number", invoice_value=invoice_po,
            shipment_value=shipment_po, matched=False, confidence=0.0,
            note="PO number present on only one side",
        ))

    # 2. Vendor/carrier name fuzzy match
    invoice_vendor = (
        invoice.get("vendor_name")
        or _get_party_name(invoice, "seller")
        or _get_party_name(invoice, "carrier")
    )
    shipment_vendor = (
        shipment.get("carrier")
        or shipment.get("vendor")
        or shipment.get("carrier_name")
    )
    if invoice_vendor and shipment_vendor:
        name_matched, name_conf = match_party_name(invoice_vendor, shipment_vendor)
        score += WEIGHTS["vendor_name"] * name_conf
        weights_used += WEIGHTS["vendor_name"]
        diffs.append(MatchDiff(
            field="vendor_name", invoice_value=invoice_vendor,
            shipment_value=shipment_vendor, matched=name_matched,
            confidence=name_conf,
            note="Vendor name matches" if name_matched else "Vendor names differ",
        ))
        if name_matched:
            reasons.append(f"Vendor match: {invoice_vendor} ≈ {shipment_vendor}")

    # 3. Total amount match
    invoice_total = invoice.get("total_amount")
    shipment_amount = shipment.get("amount") or shipment.get("total_amount")
    if invoice_total is not None and shipment_amount is not None:
        try:
            inv_amt = float(invoice_total)
            shp_amt = float(shipment_amount)
            amt_matched, amt_conf = match_numeric(
                inv_amt, shp_amt, amount_tolerance_pct, amount_tolerance_abs
            )
            score += WEIGHTS["total_amount"] * amt_conf
            weights_used += WEIGHTS["total_amount"]
            diff_val = abs(inv_amt - shp_amt)
            diffs.append(MatchDiff(
                field="total_amount", invoice_value=inv_amt,
                shipment_value=shp_amt, matched=amt_matched,
                confidence=amt_conf,
                note=f"Amounts {'match' if amt_matched else 'differ'} (diff: ${diff_val:.2f})",
            ))
            if amt_matched:
                reasons.append(f"Amount match: ${inv_amt:,.2f} ≈ ${shp_amt:,.2f}")
        except (ValueError, TypeError):
            pass

    # 4. Date window match
    invoice_date = invoice.get("invoice_date")
    shipment_date = (
        shipment.get("ship_date")
        or shipment.get("delivery_date")
        or shipment.get("date")
    )
    if invoice_date and shipment_date:
        date_matched, date_conf = match_by_date(
            str(invoice_date), str(shipment_date), date_tolerance_days
        )
        score += WEIGHTS["date"] * date_conf
        weights_used += WEIGHTS["date"]
        diffs.append(MatchDiff(
            field="date", invoice_value=str(invoice_date),
            shipment_value=str(shipment_date), matched=date_matched,
            confidence=date_conf,
            note=f"Dates {'within window' if date_matched else 'outside window'}",
        ))
        if date_matched:
            reasons.append(f"Date match: {invoice_date} ≈ {shipment_date}")

    # 5. Reference number cross-match
    invoice_ref = invoice.get("invoice_number")
    shipment_invoice_ref = shipment.get("invoice_ref") or shipment.get("invoice_number")
    if invoice_ref and shipment_invoice_ref:
        ref_matched, ref_conf = match_by_reference(invoice_ref, shipment_invoice_ref)
        score += WEIGHTS["reference"] * ref_conf
        weights_used += WEIGHTS["reference"]
        if ref_matched:
            reasons.append(f"Invoice ref match: {invoice_ref}")

    # Normalize score by weights actually used (so missing fields don't penalize)
    if weights_used > 0:
        score = score / weights_used
    else:
        score = 0.0

    return round(score, 4), reasons, diffs


def reconcile_invoice(
    invoice_extraction: dict,
    shipments: list[dict],
    top_n: int = 3,
    min_score: float = 0.20,
    amount_tolerance_pct: float = 0.05,
    amount_tolerance_abs: float = 100.0,
    date_tolerance_days: int = 7,
) -> InvoiceReconciliationResult:
    """Reconcile an invoice extraction against a pool of shipments.

    Args:
        invoice_extraction: The extraction dict from the invoice.
        shipments: List of shipment dicts (each must have an 'id' or 'shipment_id' key).
        top_n: Number of top candidates to return.
        min_score: Minimum score to include as a candidate.
        amount_tolerance_pct: Amount tolerance percentage.
        amount_tolerance_abs: Amount tolerance absolute.
        date_tolerance_days: Date window tolerance.

    Returns:
        InvoiceReconciliationResult with ranked candidates.
    """
    invoice_number = invoice_extraction.get("invoice_number", "UNKNOWN")
    invoice_vendor = (
        invoice_extraction.get("vendor_name")
        or _get_party_name(invoice_extraction, "seller")
    )
    invoice_total = invoice_extraction.get("total_amount")

    candidates: list[ReconciliationCandidate] = []
    exceptions: list[str] = []

    for shipment in shipments:
        shipment_id = str(
            shipment.get("id") or shipment.get("shipment_id") or "unknown"
        )
        shipment_ref = str(
            shipment.get("reference_number")
            or shipment.get("shipment_ref")
            or shipment_id
        )

        score, reasons, diffs = score_invoice_against_shipment(
            invoice_extraction,
            shipment,
            amount_tolerance_pct=amount_tolerance_pct,
            amount_tolerance_abs=amount_tolerance_abs,
            date_tolerance_days=date_tolerance_days,
        )

        if score >= min_score:
            candidates.append(ReconciliationCandidate(
                shipment_id=shipment_id,
                shipment_ref=shipment_ref,
                match_score=score,
                status=_classify_candidate(score),
                match_reasons=reasons,
                diffs=diffs,
                shipment_data=shipment,
            ))

    # Sort by score descending
    candidates.sort(key=lambda c: c.match_score, reverse=True)

    # Take top N
    top_candidates = candidates[:top_n]

    # Determine best match and auto-match eligibility
    best_match: ReconciliationCandidate | None = None
    auto_match = False

    if top_candidates:
        best = top_candidates[0]
        if best.status == CandidateStatus.STRONG_MATCH:
            best_match = best
            # Auto-match only if single strong match with significant gap to #2
            if len(top_candidates) == 1 or (
                len(top_candidates) > 1
                and best.match_score - top_candidates[1].match_score > 0.15
            ):
                auto_match = True
        elif best.status == CandidateStatus.LIKELY_MATCH:
            best_match = best

    # Build exceptions
    if not top_candidates:
        exceptions.append(f"No matching shipments found for invoice {invoice_number}")
    elif not best_match:
        exceptions.append(
            f"No strong match found — top score {top_candidates[0].match_score:.2f}"
        )
    elif not auto_match and len(top_candidates) > 1:
        exceptions.append(
            f"Multiple candidates — manual review needed "
            f"(top: {top_candidates[0].match_score:.2f}, "
            f"#2: {top_candidates[1].match_score:.2f})"
        )

    return InvoiceReconciliationResult(
        invoice_number=invoice_number,
        invoice_vendor=invoice_vendor,
        invoice_total=invoice_total,
        candidates=top_candidates,
        best_match=best_match,
        auto_match=auto_match,
        exceptions=exceptions,
    )


def _get_party_name(data: dict, field_name: str) -> str | None:
    """Extract a party name from extraction data (handles dict or string)."""
    party = data.get(field_name)
    if isinstance(party, dict):
        return party.get("name")
    if isinstance(party, str):
        return party
    return None
