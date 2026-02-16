"""HITL review queue endpoints — browse, act on, and get stats for review items."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_hitl_service
from app.hitl_workflow.service import HITLService
from app.models.review import ReviewItem
from app.schemas.review import (
    ReviewActionRequest,
    ReviewItemListResponse,
    ReviewItemResponse,
    ReviewQueueStats,
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


@router.get("/{item_id}", response_model=ReviewItemResponse)
async def get_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ReviewItemResponse:
    """Get a specific review item."""
    result = await db.execute(select(ReviewItem).where(ReviewItem.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Review item not found")
    return _item_to_response(item)


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


def _item_to_response(item: ReviewItem) -> ReviewItemResponse:
    """Convert ORM ReviewItem to response schema."""
    from app.models.review import ReviewItemType, ReviewStatus
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
