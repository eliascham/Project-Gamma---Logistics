"""ORM model for HITL review queue items."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ReviewStatus(str, enum.Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    AUTO_APPROVED = "auto_approved"


class ReviewItemType(str, enum.Enum):
    COST_ALLOCATION = "cost_allocation"
    ANOMALY = "anomaly"
    RECONCILIATION_MISMATCH = "reconciliation_mismatch"


class ReviewItem(Base):
    __tablename__ = "review_queue"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[ReviewStatus] = mapped_column(
        SAEnum(ReviewStatus, name="review_status", values_callable=lambda e: [m.value for m in e]),
        default=ReviewStatus.PENDING_REVIEW,
    )
    item_type: Mapped[ReviewItemType | None] = mapped_column(
        SAEnum(ReviewItemType, name="review_item_type", values_callable=lambda e: [m.value for m in e]),
        nullable=True,
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str | None] = mapped_column(
        SAEnum(
            "low", "medium", "high", "critical",
            name="anomaly_severity",
            values_callable=lambda e: [m.value for m in e] if hasattr(e, '__members__') else list(e),
            create_type=False,
        ),
        nullable=True,
    )
    assigned_to: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    auto_approve_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    dollar_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
