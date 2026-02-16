"""HITL review queue endpoints — browse, act on, and get stats for review items."""

import json as json_module
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_hitl_service
from app.hitl_workflow.service import HITLService
from app.models.anomaly import AnomalyFlag, AnomalySeverity, AnomalyType
from app.models.review import ReviewItem, ReviewItemType, ReviewStatus
from app.schemas.review import (
    EvidenceItem,
    ReviewActionRequest,
    ReviewContext,
    ReviewItemDetailResponse,
    ReviewItemListResponse,
    ReviewItemResponse,
    ReviewQueueStats,
    SuggestedAction,
)

router = APIRouter()


@router.get("/queue", response_model=ReviewItemListResponse)
async def get_queue(
    status: str | None = None,
    item_type: str | None = None,
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
    hitl: HITLService = Depends(get_hitl_service),
) -> ReviewItemListResponse:
    """Get the review queue with optional filtering."""
    items, total = await hitl.get_queue(
        db, status=status, item_type=item_type, page=page, per_page=per_page,
    )
    return ReviewItemListResponse(
        items=[_item_to_response(i) for i in items],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/stats", response_model=ReviewQueueStats)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    hitl: HITLService = Depends(get_hitl_service),
) -> ReviewQueueStats:
    """Get review queue statistics."""
    stats = await hitl.get_stats(db)
    return ReviewQueueStats(**stats)


@router.get("/{item_id}", response_model=ReviewItemDetailResponse)
async def get_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ReviewItemDetailResponse:
    """Get a specific review item with enriched context for reviewers."""
    result = await db.execute(select(ReviewItem).where(ReviewItem.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Review item not found")
    context = await _build_context(db, item)
    return _item_to_detail_response(item, context)


@router.post("/{item_id}/action", response_model=ReviewItemResponse)
async def review_action(
    item_id: uuid.UUID,
    request: ReviewActionRequest,
    db: AsyncSession = Depends(get_db),
    hitl: HITLService = Depends(get_hitl_service),
) -> ReviewItemResponse:
    """Act on a review item (approve/reject/escalate)."""
    try:
        item = await hitl.review_item(
            db, item_id, action=request.action, reviewed_by=request.reviewed_by, notes=request.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _item_to_response(item)


# ── Suggested actions per anomaly type ──

_SUGGESTED_ACTIONS: dict[str, list[SuggestedAction]] = {
    "duplicate_invoice": [
        SuggestedAction(
            label="Confirmed Duplicate",
            action="reject",
            notes="Confirmed duplicate invoice — rejecting to prevent double payment.",
            variant="danger",
        ),
        SuggestedAction(
            label="Not a Duplicate",
            action="approve",
            notes="Verified as separate invoice despite matching number — approved.",
            variant="success",
        ),
        SuggestedAction(
            label="Need Original for Comparison",
            action="escalate",
            notes="Escalating — need to compare with original invoice before deciding.",
            variant="warning",
        ),
    ],
    "budget_overrun": [
        SuggestedAction(
            label="Budget Exception Granted",
            action="approve",
            notes="Budget overrun approved — exception granted per management authorization.",
            variant="success",
        ),
        SuggestedAction(
            label="Over Budget Limit",
            action="reject",
            notes="Rejected — exceeds project budget and no exception has been authorized.",
            variant="danger",
        ),
        SuggestedAction(
            label="Request Budget Increase",
            action="escalate",
            notes="Escalating — requesting budget increase from finance team.",
            variant="warning",
        ),
    ],
    "misallocated_cost": [
        SuggestedAction(
            label="Allocations Verified",
            action="approve",
            notes="Reviewed low-confidence allocations — AI assignments are correct.",
            variant="success",
        ),
        SuggestedAction(
            label="Incorrect Allocations",
            action="reject",
            notes="Rejected — one or more line item allocations are incorrect and need reassignment.",
            variant="danger",
        ),
        SuggestedAction(
            label="Need Manual Reallocation",
            action="escalate",
            notes="Escalating — line items need manual reallocation by accounting team.",
            variant="warning",
        ),
    ],
    "missing_approval": [
        SuggestedAction(
            label="Authorize Payment",
            action="approve",
            notes="High-value allocation authorized for payment after review.",
            variant="success",
        ),
        SuggestedAction(
            label="Not Authorized",
            action="reject",
            notes="Rejected — this allocation has not been authorized for payment.",
            variant="danger",
        ),
        SuggestedAction(
            label="Needs Manager Approval",
            action="escalate",
            notes="Escalating — requires manager-level approval due to amount.",
            variant="warning",
        ),
    ],
    "reconciliation_mismatch": [
        SuggestedAction(
            label="Discrepancy Explained",
            action="approve",
            notes="Mismatch reviewed — discrepancy is explained by timing/rounding differences.",
            variant="success",
        ),
        SuggestedAction(
            label="Records Don't Match",
            action="reject",
            notes="Rejected — records across systems do not match and need correction.",
            variant="danger",
        ),
        SuggestedAction(
            label="Investigate Further",
            action="escalate",
            notes="Escalating — mismatch requires deeper investigation across source systems.",
            variant="warning",
        ),
    ],
}

_DEFAULT_ACTIONS = [
    SuggestedAction(label="Approve", action="approve", notes="Reviewed and approved.", variant="success"),
    SuggestedAction(label="Reject", action="reject", notes="Reviewed and rejected.", variant="danger"),
    SuggestedAction(label="Escalate", action="escalate", notes="Escalating for further review.", variant="warning"),
]

# ── Guidance text per anomaly type ──

_GUIDANCE: dict[str, str] = {
    "duplicate_invoice": (
        "This invoice has the same number and vendor as an existing invoice. "
        "Compare the dates, amounts, and line items below to determine if this is a true duplicate "
        "or a legitimate re-issue. Check if the original was already paid."
    ),
    "budget_overrun": (
        "Adding this allocation would push the project over its approved budget. "
        "Review the projected spend vs. budget amount and decide whether to authorize "
        "an exception or reject the allocation."
    ),
    "misallocated_cost": (
        "The AI allocated these line items with low confidence (below threshold). "
        "Review each flagged item's description, amount, and assigned GL account/cost center. "
        "Verify the allocations are correct or reject for manual reassignment."
    ),
    "missing_approval": (
        "This is a high-value allocation that has not yet been approved. "
        "Company policy requires explicit sign-off for allocations above the threshold. "
        "Review the allocation details and authorize or reject."
    ),
    "reconciliation_mismatch": (
        "Records from different source systems (TMS, WMS, ERP) don't fully match. "
        "Review the mismatched fields below and determine if the discrepancy is "
        "acceptable (timing, rounding) or requires correction in the source systems."
    ),
}


# ── Context builder ──

async def _build_context(db: AsyncSession, item: ReviewItem) -> ReviewContext:
    """Build rich context by fetching related entities."""
    item_type_val = item.item_type.value if isinstance(item.item_type, ReviewItemType) else item.item_type
    entity_type = item.entity_type or ""
    entity_id = item.entity_id

    context = ReviewContext()
    evidence: list[EvidenceItem] = []
    anomaly_type_str: str | None = None

    # Fetch anomaly details if this is an anomaly review item
    if entity_type == "anomaly_flag" and entity_id:
        anomaly = (await db.execute(
            select(AnomalyFlag).where(AnomalyFlag.id == entity_id)
        )).scalar_one_or_none()

        if anomaly:
            anomaly_type_str = (
                anomaly.anomaly_type.value
                if isinstance(anomaly.anomaly_type, AnomalyType)
                else anomaly.anomaly_type
            )
            context.anomaly_type = anomaly_type_str
            context.anomaly_details = anomaly.details

            if anomaly.document_id:
                context.document_id = str(anomaly.document_id)
                # Fetch document name
                doc_row = (await db.execute(
                    sa_text("SELECT original_filename FROM documents WHERE id = :doc_id"),
                    {"doc_id": anomaly.document_id},
                )).first()
                if doc_row:
                    context.document_name = doc_row[0]

            if anomaly.allocation_id:
                context.allocation_id = str(anomaly.allocation_id)
                # Fetch allocation total
                alloc_row = (await db.execute(
                    sa_text("SELECT total_amount FROM cost_allocations WHERE id = :alloc_id"),
                    {"alloc_id": anomaly.allocation_id},
                )).first()
                if alloc_row:
                    context.allocation_total = alloc_row[0]

            # Build evidence from anomaly details
            evidence = _build_evidence(anomaly_type_str, anomaly.details)

    # Reconciliation mismatch context
    elif entity_type == "reconciliation_record" and entity_id:
        from app.models.reconciliation import ReconciliationRecord, ReconciliationStatus
        rec = (await db.execute(
            select(ReconciliationRecord).where(ReconciliationRecord.id == entity_id)
        )).scalar_one_or_none()

        if rec:
            anomaly_type_str = "reconciliation_mismatch"
            context.anomaly_type = anomaly_type_str
            context.anomaly_details = rec.mismatch_details
            evidence = _build_reconciliation_evidence(rec)

    # Set guidance and suggested actions
    context.evidence = evidence
    context.guidance = _GUIDANCE.get(anomaly_type_str or "", None)
    context.suggested_actions = _SUGGESTED_ACTIONS.get(anomaly_type_str or "", _DEFAULT_ACTIONS)

    return context


def _build_evidence(anomaly_type: str | None, details: dict | None) -> list[EvidenceItem]:
    """Turn anomaly details JSON into structured evidence items."""
    if not details:
        return []

    items: list[EvidenceItem] = []

    if anomaly_type == "duplicate_invoice":
        if "invoice_number" in details:
            items.append(EvidenceItem(label="Invoice Number", value=details["invoice_number"]))
        if "vendor" in details:
            items.append(EvidenceItem(label="Vendor", value=details["vendor"]))
        if "duplicate_of_document_id" in details:
            items.append(EvidenceItem(
                label="Original Document",
                value=details["duplicate_of_document_id"],
                type="link",
            ))
        if "original_date" in details:
            items.append(EvidenceItem(label="Original Date", value=str(details["original_date"])))

    elif anomaly_type == "budget_overrun":
        if "project_code" in details:
            items.append(EvidenceItem(label="Project Code", value=details["project_code"]))
        if "budget_amount" in details:
            items.append(EvidenceItem(
                label="Budget Amount",
                value=f"${details['budget_amount']:,.2f}",
                type="currency",
            ))
        if "spent_amount" in details:
            items.append(EvidenceItem(
                label="Already Spent",
                value=f"${details['spent_amount']:,.2f}",
                type="currency",
            ))
        if "new_amount" in details:
            items.append(EvidenceItem(
                label="New Allocation",
                value=f"${details['new_amount']:,.2f}",
                type="currency",
            ))
        if "projected_total" in details:
            items.append(EvidenceItem(
                label="Projected Total",
                value=f"${details['projected_total']:,.2f}",
                type="currency",
            ))
        if "overrun_pct" in details:
            items.append(EvidenceItem(
                label="Over Budget By",
                value=f"{details['overrun_pct']}%",
                type="percentage",
            ))

    elif anomaly_type == "misallocated_cost":
        flagged = details.get("flagged_items", [])
        for i, fi in enumerate(flagged):
            desc = fi.get("description", f"Item {i + 1}")
            conf = fi.get("confidence", 0)
            amount = fi.get("amount", 0)
            gap = fi.get("gap", 0)
            items.append(EvidenceItem(
                label=f"Line Item: {desc}",
                value=f"${amount:,.2f} | Confidence: {conf:.0%} (gap: {gap:.1%})",
            ))

    elif anomaly_type == "missing_approval":
        if "total_amount" in details:
            items.append(EvidenceItem(
                label="Allocation Amount",
                value=f"${details['total_amount']:,.2f}",
                type="currency",
            ))
        if "threshold" in details:
            items.append(EvidenceItem(
                label="Approval Threshold",
                value=f"${details['threshold']:,.2f}",
                type="currency",
            ))
        if "status" in details:
            items.append(EvidenceItem(label="Current Status", value=details["status"]))

    return items


def _build_reconciliation_evidence(rec) -> list[EvidenceItem]:
    """Build evidence from a reconciliation record."""
    from app.models.reconciliation import RecordSource
    items: list[EvidenceItem] = []

    source = rec.source.value if isinstance(rec.source, RecordSource) else rec.source
    items.append(EvidenceItem(label="Source System", value=source.upper()))

    if rec.reference_number:
        items.append(EvidenceItem(label="Reference Number", value=rec.reference_number))
    if rec.match_confidence is not None:
        items.append(EvidenceItem(
            label="Match Confidence",
            value=f"{rec.match_confidence:.0%}",
            type="percentage",
        ))
    if rec.match_reasoning:
        items.append(EvidenceItem(label="Match Reasoning", value=rec.match_reasoning))

    if rec.mismatch_details:
        for field, detail in rec.mismatch_details.items():
            if isinstance(detail, dict):
                expected = detail.get("expected", "?")
                actual = detail.get("actual", "?")
                items.append(EvidenceItem(
                    label=f"Mismatch: {field}",
                    value=f"Expected: {expected} | Actual: {actual}",
                ))
            else:
                items.append(EvidenceItem(label=f"Mismatch: {field}", value=str(detail)))

    return items


# ── Response converters ──

def _item_to_response(item: ReviewItem) -> ReviewItemResponse:
    """Convert ORM ReviewItem to response schema."""
    return ReviewItemResponse(
        id=item.id,
        status=item.status.value if isinstance(item.status, ReviewStatus) else item.status,
        item_type=item.item_type.value if isinstance(item.item_type, ReviewItemType) else item.item_type,
        entity_id=item.entity_id,
        entity_type=item.entity_type,
        title=item.title,
        description=item.description,
        severity=item.severity,
        assigned_to=item.assigned_to,
        reviewed_by=item.reviewed_by,
        reviewed_at=item.reviewed_at,
        review_notes=item.review_notes,
        auto_approve_eligible=item.auto_approve_eligible,
        dollar_amount=item.dollar_amount,
        created_at=item.created_at,
    )


def _item_to_detail_response(item: ReviewItem, context: ReviewContext) -> ReviewItemDetailResponse:
    """Convert ORM ReviewItem to enriched detail response."""
    return ReviewItemDetailResponse(
        id=item.id,
        status=item.status.value if isinstance(item.status, ReviewStatus) else item.status,
        item_type=item.item_type.value if isinstance(item.item_type, ReviewItemType) else item.item_type,
        entity_id=item.entity_id,
        entity_type=item.entity_type,
        title=item.title,
        description=item.description,
        severity=item.severity,
        assigned_to=item.assigned_to,
        reviewed_by=item.reviewed_by,
        reviewed_at=item.reviewed_at,
        review_notes=item.review_notes,
        auto_approve_eligible=item.auto_approve_eligible,
        dollar_amount=item.dollar_amount,
        created_at=item.created_at,
        review_metadata=item.review_metadata,
        context=context,
    )
