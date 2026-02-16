"""
Cost allocation endpoints.

Triggers cost allocation on extracted freight invoices, retrieves results,
allows manual overrides, and manages business rules.
"""

import json as json_module
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.cost_allocator.pipeline import CostAllocationPipeline
from app.cost_allocator.rules import format_rules_for_prompt, get_active_rules, seed_default_rules
from app.dependencies import get_cost_allocation_pipeline, get_db
from app.models.cost_allocation import (
    AllocationLineItem,
    AllocationStatus,
    CostAllocation,
    LineItemStatus,
)
from app.models.document import Document, DocumentStatus
from app.schemas.cost_allocation import (
    AllocationApprovalRequest,
    AllocationLineItemResponse,
    AllocationOverrideRequest,
    AllocationRuleResponse,
    CostAllocationResponse,
)

router = APIRouter()


# ── Static routes MUST come before parameterized /{document_id} routes ──

@router.get("/rules/list", response_model=list[AllocationRuleResponse])
async def list_rules(
    db: AsyncSession = Depends(get_db),
) -> list[AllocationRuleResponse]:
    """List all active allocation rules."""
    rules = await get_active_rules(db)
    return [AllocationRuleResponse.model_validate(r) for r in rules]


@router.post("/rules/seed")
async def seed_rules(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Seed default business rules for demo purposes."""
    count = await seed_default_rules(db)
    return {"seeded": count, "message": f"Seeded {count} allocation rules" if count else "Rules already exist"}


@router.put("/line-items/{line_item_id}")
async def override_line_item(
    line_item_id: uuid.UUID,
    override: AllocationOverrideRequest,
    db: AsyncSession = Depends(get_db),
) -> AllocationLineItemResponse:
    """Override a line item's allocation codes."""
    result = await db.execute(
        select(AllocationLineItem).where(AllocationLineItem.id == line_item_id)
    )
    line_item = result.scalar_one_or_none()
    if line_item is None:
        raise HTTPException(status_code=404, detail="Line item not found")

    if override.project_code is not None:
        line_item.override_project_code = override.project_code
    if override.cost_center is not None:
        line_item.override_cost_center = override.cost_center
    if override.gl_account is not None:
        line_item.override_gl_account = override.gl_account

    line_item.status = LineItemStatus.MANUALLY_OVERRIDDEN
    line_item.overridden_by = "user"
    line_item.overridden_at = datetime.now(timezone.utc)
    await db.flush()

    return AllocationLineItemResponse.model_validate(line_item)


# ── Parameterized routes ──

@router.post("/{document_id}", response_model=CostAllocationResponse)
async def run_allocation(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    pipeline: CostAllocationPipeline = Depends(get_cost_allocation_pipeline),
) -> CostAllocationResponse:
    """Run cost allocation on an extracted freight invoice."""
    # Fetch document
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if document.status != DocumentStatus.EXTRACTED:
        raise HTTPException(status_code=400, detail="Document must be extracted before allocation")
    if document.document_type != "freight_invoice":
        raise HTTPException(status_code=400, detail="Cost allocation only supports freight invoices")

    # Get the latest extraction
    ext_row = (
        await db.execute(
            sa_text(
                "SELECT id, extraction_data FROM extractions "
                "WHERE document_id = :doc_id ORDER BY created_at DESC LIMIT 1"
            ),
            {"doc_id": document_id},
        )
    ).first()

    if ext_row is None:
        raise HTTPException(status_code=404, detail="No extraction found for this document")

    extraction_data = ext_row.extraction_data
    if isinstance(extraction_data, str):
        extraction_data = json_module.loads(extraction_data)

    # Load business rules
    rules = await get_active_rules(db)
    rules_text = format_rules_for_prompt(rules)

    # Run the allocation pipeline
    alloc_result = await pipeline.allocate(extraction_data, rules_text)

    # Create the allocation record
    allocation = CostAllocation(
        id=uuid.uuid4(),
        document_id=document_id,
        extraction_id=ext_row.id,
        status=AllocationStatus.ALLOCATED,
        total_amount=alloc_result.total_amount,
        currency=alloc_result.currency,
        allocated_by_model=alloc_result.model_used,
        processing_time_ms=alloc_result.processing_time_ms,
    )
    db.add(allocation)
    await db.flush()

    # Create line item records
    has_review_items = False
    for item in alloc_result.line_items:
        needs_review = item.confidence < settings.allocation_confidence_threshold
        if needs_review:
            has_review_items = True

        line_item = AllocationLineItem(
            id=uuid.uuid4(),
            allocation_id=allocation.id,
            line_item_index=item.line_item_index,
            description=item.description,
            amount=item.amount,
            project_code=item.project_code,
            cost_center=item.cost_center,
            gl_account=item.gl_account,
            confidence=item.confidence,
            reasoning=item.reasoning,
            status=LineItemStatus.NEEDS_REVIEW if needs_review else LineItemStatus.AUTO_APPROVED,
        )
        db.add(line_item)

    # If any items need review, update allocation status
    if has_review_items:
        allocation.status = AllocationStatus.REVIEW_NEEDED

    await db.flush()

    # Reload with line items
    result = await db.execute(
        select(CostAllocation)
        .options(selectinload(CostAllocation.line_items))
        .where(CostAllocation.id == allocation.id)
    )
    allocation = result.scalar_one()

    return _allocation_to_response(allocation)


@router.get("/{document_id}", response_model=CostAllocationResponse)
async def get_allocation(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> CostAllocationResponse:
    """Get the latest cost allocation for a document."""
    result = await db.execute(
        select(CostAllocation)
        .options(selectinload(CostAllocation.line_items))
        .where(CostAllocation.document_id == document_id)
        .order_by(CostAllocation.created_at.desc())
        .limit(1)
    )
    allocation = result.scalar_one_or_none()
    if allocation is None:
        raise HTTPException(status_code=404, detail="No allocation found for this document")

    return _allocation_to_response(allocation)


@router.post("/{allocation_id}/approve")
async def approve_allocation(
    allocation_id: uuid.UUID,
    request: AllocationApprovalRequest,
    db: AsyncSession = Depends(get_db),
) -> CostAllocationResponse:
    """Approve or reject a cost allocation."""
    result = await db.execute(
        select(CostAllocation)
        .options(selectinload(CostAllocation.line_items))
        .where(CostAllocation.id == allocation_id)
    )
    allocation = result.scalar_one_or_none()
    if allocation is None:
        raise HTTPException(status_code=404, detail="Allocation not found")

    if request.action == "approve":
        allocation.status = AllocationStatus.APPROVED
    else:
        allocation.status = AllocationStatus.REJECTED

    await db.flush()
    return _allocation_to_response(allocation)


def _allocation_to_response(allocation: CostAllocation) -> CostAllocationResponse:
    """Convert ORM allocation to response schema."""
    return CostAllocationResponse(
        id=allocation.id,
        document_id=allocation.document_id,
        status=allocation.status.value if isinstance(allocation.status, AllocationStatus) else allocation.status,
        line_items=[
            AllocationLineItemResponse(
                id=li.id,
                line_item_index=li.line_item_index,
                description=li.description,
                amount=li.amount,
                project_code=li.project_code,
                cost_center=li.cost_center,
                gl_account=li.gl_account,
                confidence=li.confidence,
                reasoning=li.reasoning,
                status=li.status.value if isinstance(li.status, LineItemStatus) else li.status,
                override_project_code=li.override_project_code,
                override_cost_center=li.override_cost_center,
                override_gl_account=li.override_gl_account,
            )
            for li in sorted(allocation.line_items, key=lambda x: x.line_item_index)
        ],
        total_amount=allocation.total_amount,
        currency=allocation.currency,
        allocated_by_model=allocation.allocated_by_model,
        processing_time_ms=allocation.processing_time_ms,
        created_at=allocation.created_at,
    )
