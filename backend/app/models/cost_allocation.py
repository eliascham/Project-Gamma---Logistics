"""ORM models for cost allocation: allocations, line items, and business rules."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class AllocationStatus(str, enum.Enum):
    PENDING = "pending"
    ALLOCATED = "allocated"
    REVIEW_NEEDED = "review_needed"
    APPROVED = "approved"
    REJECTED = "rejected"


class LineItemStatus(str, enum.Enum):
    AUTO_APPROVED = "auto_approved"
    NEEDS_REVIEW = "needs_review"
    MANUALLY_OVERRIDDEN = "manually_overridden"


class CostAllocation(Base, TimestampMixin):
    __tablename__ = "cost_allocations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True)
    extraction_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[AllocationStatus] = mapped_column(
        SAEnum(AllocationStatus, name="allocation_status", values_callable=lambda e: [m.value for m in e]),
        default=AllocationStatus.PENDING,
    )
    total_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    allocated_by_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    line_items: Mapped[list["AllocationLineItem"]] = relationship(
        back_populates="allocation", cascade="all, delete-orphan"
    )


class AllocationLineItem(Base):
    __tablename__ = "allocation_line_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    allocation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cost_allocations.id", ondelete="CASCADE"))
    line_item_index: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    project_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cost_center: Mapped[str | None] = mapped_column(String(50), nullable=True)
    gl_account: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[LineItemStatus] = mapped_column(
        SAEnum(LineItemStatus, name="line_item_status", values_callable=lambda e: [m.value for m in e]),
        default=LineItemStatus.AUTO_APPROVED,
    )
    override_project_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    override_cost_center: Mapped[str | None] = mapped_column(String(50), nullable=True)
    override_gl_account: Mapped[str | None] = mapped_column(String(50), nullable=True)
    overridden_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    overridden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    allocation: Mapped["CostAllocation"] = relationship(back_populates="line_items")


class AllocationRule(Base):
    __tablename__ = "allocation_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    match_pattern: Mapped[str] = mapped_column(Text, nullable=False)
    project_code: Mapped[str] = mapped_column(String(50), nullable=False)
    cost_center: Mapped[str] = mapped_column(String(50), nullable=False)
    gl_account: Mapped[str] = mapped_column(String(50), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=10)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
