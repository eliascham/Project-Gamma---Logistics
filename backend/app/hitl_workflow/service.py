"""HITLService — Human-in-the-Loop review queue state machine.

Manages review item lifecycle: create → review (approve/reject/escalate).
Applies autonomy rules for auto-approval of low-risk items.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit_generator.service import AuditService
from app.config import Settings
from app.models.review import ReviewItem, ReviewItemType, ReviewStatus


class HITLService:
    """Review queue state machine."""

    def __init__(self, settings: Settings):
        self.auto_approve_threshold = settings.hitl_auto_approve_dollar_threshold
        self.high_risk_threshold = settings.hitl_high_risk_dollar_threshold

    async def create_review_item(
        self,
        db: AsyncSession,
        *,
        item_type: ReviewItemType,
        entity_id: uuid.UUID,
        entity_type: str,
        title: str,
        description: str | None = None,
        severity: str | None = None,
        dollar_amount: float | None = None,
        confidence: float | None = None,
        metadata: dict | None = None,
    ) -> ReviewItem:
        """Create a review item, applying autonomy rules.

        Auto-approve rules:
        - Low-risk: dollar_amount < auto_approve_threshold AND confidence >= 0.85
        Mandatory review:
        - High-risk: dollar_amount >= high_risk_threshold
        """
        # Determine auto-approval eligibility
        auto_eligible = False
        status = ReviewStatus.PENDING_REVIEW

        if dollar_amount is not None and confidence is not None:
            if dollar_amount < self.auto_approve_threshold and confidence >= 0.85:
                auto_eligible = True
                status = ReviewStatus.AUTO_APPROVED

        # High-risk items always need review
        if dollar_amount is not None and dollar_amount >= self.high_risk_threshold:
            auto_eligible = False
            status = ReviewStatus.PENDING_REVIEW
            severity = severity or "high"

        item = ReviewItem(
            id=uuid.uuid4(),
            status=status,
            item_type=item_type,
            entity_id=entity_id,
            entity_type=entity_type,
            title=title,
            description=description,
            severity=severity,
            auto_approve_eligible=auto_eligible,
            dollar_amount=dollar_amount,
            review_metadata=metadata,
        )
        db.add(item)
        await db.flush()

        # Log audit event
        await AuditService.log_event(
            db,
            event_type="REVIEW_ITEM_CREATED",
            entity_type="review_item",
            entity_id=item.id,
            action="create",
            actor="system",
            actor_type="ai",
            new_state={
                "status": status.value,
                "item_type": item_type.value,
                "dollar_amount": dollar_amount,
                "auto_approved": status == ReviewStatus.AUTO_APPROVED,
            },
        )

        return item

    async def review_item(
        self,
        db: AsyncSession,
        item_id: uuid.UUID,
        action: str,
        reviewed_by: str = "user",
        notes: str | None = None,
    ) -> ReviewItem:
        """Process a review action (approve/reject/escalate)."""
        result = await db.execute(
            select(ReviewItem).where(ReviewItem.id == item_id)
        )
        item = result.scalar_one_or_none()
        if item is None:
            raise ValueError(f"Review item {item_id} not found")

        previous_status = item.status.value if isinstance(item.status, ReviewStatus) else item.status

        if action == "approve":
            item.status = ReviewStatus.APPROVED
        elif action == "reject":
            item.status = ReviewStatus.REJECTED
        elif action == "escalate":
            item.status = ReviewStatus.ESCALATED
        else:
            raise ValueError(f"Invalid action: {action}. Must be approve, reject, or escalate.")

        item.reviewed_by = reviewed_by
        item.reviewed_at = datetime.now(timezone.utc)
        item.review_notes = notes
        await db.flush()

        new_status = item.status.value if isinstance(item.status, ReviewStatus) else item.status

        await AuditService.log_event(
            db,
            event_type="REVIEW_ITEM_ACTIONED",
            entity_type="review_item",
            entity_id=item.id,
            action=action,
            actor=reviewed_by,
            actor_type="user",
            previous_state={"status": previous_status},
            new_state={"status": new_status, "notes": notes},
        )

        return item

    async def get_queue(
        self,
        db: AsyncSession,
        *,
        status: str | None = None,
        item_type: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[ReviewItem], int]:
        """Get paginated, filterable review queue."""
        query = select(ReviewItem)
        count_query = select(func.count(ReviewItem.id))

        if status:
            query = query.where(ReviewItem.status == status)
            count_query = count_query.where(ReviewItem.status == status)
        if item_type:
            query = query.where(ReviewItem.item_type == item_type)
            count_query = count_query.where(ReviewItem.item_type == item_type)

        total = (await db.execute(count_query)).scalar_one()

        offset = (page - 1) * per_page
        query = query.order_by(ReviewItem.created_at.desc()).offset(offset).limit(per_page)
        result = await db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def get_stats(self, db: AsyncSession) -> dict:
        """Get review queue statistics."""
        total = (await db.execute(select(func.count(ReviewItem.id)))).scalar_one()

        counts = {}
        for status in ReviewStatus:
            count = (await db.execute(
                select(func.count(ReviewItem.id)).where(ReviewItem.status == status)
            )).scalar_one()
            counts[status.value] = count

        return {
            "total": total,
            **counts,
        }
