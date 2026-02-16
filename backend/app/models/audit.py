"""ORM model for audit events — immutable append-only log."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    event_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str | None] = mapped_column(String(100), nullable=True)
    actor: Mapped[str | None] = mapped_column(String(200), nullable=True)
    actor_type: Mapped[str | None] = mapped_column(String(50), nullable=True, default="system")
    previous_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
