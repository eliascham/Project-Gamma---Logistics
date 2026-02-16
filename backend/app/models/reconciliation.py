"""ORM models for reconciliation runs and records."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ReconciliationStatus(str, enum.Enum):
    PENDING = "pending"
    MATCHED = "matched"
    PARTIAL_MATCH = "partial_match"
    MISMATCH = "mismatch"
    RESOLVED = "resolved"


class RecordSource(str, enum.Enum):
    TMS = "tms"
    WMS = "wms"
    ERP = "erp"


class ReconciliationRun(Base):
    __tablename__ = "reconciliation_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ReconciliationStatus | None] = mapped_column(
        SAEnum(ReconciliationStatus, name="reconciliation_status",
               values_callable=lambda e: [m.value for m in e]),
        default=ReconciliationStatus.PENDING,
        nullable=True,
    )
    total_records: Mapped[int | None] = mapped_column(Integer, nullable=True)
    matched_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mismatch_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    match_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    run_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )

    records: Mapped[list["ReconciliationRecord"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class ReconciliationRecord(Base):
    __tablename__ = "reconciliation_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[RecordSource] = mapped_column(
        SAEnum(RecordSource, name="record_source", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    record_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reference_number: Mapped[str | None] = mapped_column(String(200), nullable=True)
    record_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    match_status: Mapped[ReconciliationStatus | None] = mapped_column(
        SAEnum(ReconciliationStatus, name="reconciliation_status",
               values_callable=lambda e: [m.value for m in e]),
        default=ReconciliationStatus.PENDING,
        nullable=True,
    )
    matched_with_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    match_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    match_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    mismatch_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    run: Mapped["ReconciliationRun"] = relationship(back_populates="records")
