"""ORM model for anomaly flags."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AnomalyType(str, enum.Enum):
    DUPLICATE_INVOICE = "duplicate_invoice"
    BUDGET_OVERRUN = "budget_overrun"
    MISALLOCATED_COST = "misallocated_cost"
    UNUSUAL_AMOUNT = "unusual_amount"
    MISSING_APPROVAL = "missing_approval"
    RECONCILIATION_MISMATCH = "reconciliation_mismatch"


class AnomalySeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyFlag(Base):
    __tablename__ = "anomaly_flags"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )
    allocation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_allocations.id"), nullable=True
    )
    anomaly_type: Mapped[AnomalyType] = mapped_column(
        SAEnum(AnomalyType, name="anomaly_type", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    severity: Mapped[AnomalySeverity] = mapped_column(
        SAEnum(AnomalySeverity, name="anomaly_severity", values_callable=lambda e: [m.value for m in e]),
        default=AnomalySeverity.MEDIUM,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_queue.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
