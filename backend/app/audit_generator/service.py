"""AuditService — immutable append-only audit log.

Static methods so any module can call AuditService.log_event() directly
without DI wiring — avoids circular imports.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent


class AuditService:
    """Static audit event logger and query interface."""

    @staticmethod
    async def log_event(
        db: AsyncSession,
        *,
        event_type: str,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        action: str | None = None,
        actor: str = "system",
        actor_type: str = "system",
        event_data: dict | None = None,
        previous_state: dict | None = None,
        new_state: dict | None = None,
        rationale: str | None = None,
        model_used: str | None = None,
        ip_address: str | None = None,
    ) -> AuditEvent:
        """Append an immutable audit event."""
        event = AuditEvent(
            id=uuid.uuid4(),
            event_type=event_type,
            event_data=event_data,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action or event_type,
            actor=actor,
            actor_type=actor_type,
            previous_state=previous_state,
            new_state=new_state,
            rationale=rationale,
            model_used=model_used,
            ip_address=ip_address,
        )
        db.add(event)
        await db.flush()
        return event

    @staticmethod
    async def get_events(
        db: AsyncSession,
        *,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        event_type: str | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> tuple[list[AuditEvent], int]:
        """Query audit events with filtering and pagination."""
        query = select(AuditEvent)
        count_query = select(func.count(AuditEvent.id))

        if entity_type:
            query = query.where(AuditEvent.entity_type == entity_type)
            count_query = count_query.where(AuditEvent.entity_type == entity_type)
        if entity_id:
            query = query.where(AuditEvent.entity_id == entity_id)
            count_query = count_query.where(AuditEvent.entity_id == entity_id)
        if event_type:
            query = query.where(AuditEvent.event_type == event_type)
            count_query = count_query.where(AuditEvent.event_type == event_type)

        total = (await db.execute(count_query)).scalar_one()

        offset = (page - 1) * per_page
        query = query.order_by(AuditEvent.created_at.desc()).offset(offset).limit(per_page)
        result = await db.execute(query)
        events = list(result.scalars().all())

        return events, total

    @staticmethod
    async def get_stats(db: AsyncSession) -> dict:
        """Get audit event statistics."""
        total = (await db.execute(select(func.count(AuditEvent.id)))).scalar_one()

        # Events by type
        rows = (await db.execute(
            select(AuditEvent.event_type, func.count(AuditEvent.id))
            .group_by(AuditEvent.event_type)
        )).all()
        by_type = {row[0] or "unknown": row[1] for row in rows}

        # Events by actor type
        rows = (await db.execute(
            select(AuditEvent.actor_type, func.count(AuditEvent.id))
            .group_by(AuditEvent.actor_type)
        )).all()
        by_actor_type = {row[0] or "unknown": row[1] for row in rows}

        # Recent events
        recent_result = await db.execute(
            select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(10)
        )
        recent = list(recent_result.scalars().all())

        return {
            "total_events": total,
            "events_by_type": by_type,
            "events_by_actor_type": by_actor_type,
            "recent_events": recent,
        }
