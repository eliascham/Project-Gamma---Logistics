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

    async def update_fields(
        self,
        db: AsyncSession,
        item_id: uuid.UUID,
        *,
        updated_by: str = "user",
        **fields,
    ) -> ReviewItem:
        """Update editable fields on a review item.

        Allowed fields: title, description, assigned_to, severity,
        dollar_amount, review_metadata.
        """
        EDITABLE_FIELDS = {
            "title", "description", "assigned_to", "severity",
            "dollar_amount", "review_metadata",
        }

        result = await db.execute(
            select(ReviewItem).where(ReviewItem.id == item_id)
        )
        item = result.scalar_one_or_none()
        if item is None:
            raise ValueError(f"Review item {item_id} not found")

        previous_state = {}
        new_state = {}

        for field_name, value in fields.items():
            if field_name not in EDITABLE_FIELDS:
                continue
            if value is None:
                continue
            old_val = getattr(item, field_name, None)
            previous_state[field_name] = old_val
            setattr(item, field_name, value)
            new_state[field_name] = value

        if not new_state:
            return item

        item.updated_at = datetime.now(timezone.utc)
        await db.flush()

        await AuditService.log_event(
            db,
            event_type="REVIEW_ITEM_UPDATED",
            entity_type="review_item",
            entity_id=item.id,
            action="update_fields",
            actor=updated_by,
            actor_type="user",
            previous_state=previous_state,
            new_state=new_state,
        )

        return item

    async def create_exception_task(
        self,
        db: AsyncSession,
        parent_id: uuid.UUID,
        *,
        title: str,
        description: str | None = None,
        assigned_to: str | None = None,
        severity: str = "medium",
        created_by: str = "user",
    ) -> ReviewItem:
        """Create an exception task linked to a parent review item.

        Exception tasks are follow-up investigation items created when
        a reviewer identifies something that needs further action.
        """
        # Verify parent exists
        result = await db.execute(
            select(ReviewItem).where(ReviewItem.id == parent_id)
        )
        parent = result.scalar_one_or_none()
        if parent is None:
            raise ValueError(f"Parent review item {parent_id} not found")

        task = ReviewItem(
            id=uuid.uuid4(),
            status=ReviewStatus.PENDING_REVIEW,
            item_type=ReviewItemType.EXCEPTION_TASK,
            entity_id=parent.entity_id,
            entity_type=parent.entity_type,
            title=title,
            description=description,
            severity=severity,
            assigned_to=assigned_to,
            auto_approve_eligible=False,
            dollar_amount=parent.dollar_amount,
            review_metadata={
                "parent_review_id": str(parent_id),
                "parent_title": parent.title,
                "created_by": created_by,
            },
        )
        db.add(task)
        await db.flush()

        await AuditService.log_event(
            db,
            event_type="EXCEPTION_TASK_CREATED",
            entity_type="review_item",
            entity_id=task.id,
            action="create_exception",
            actor=created_by,
            actor_type="user",
            new_state={
                "parent_review_id": str(parent_id),
                "title": title,
                "assigned_to": assigned_to,
                "severity": severity,
            },
        )

        return task

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
