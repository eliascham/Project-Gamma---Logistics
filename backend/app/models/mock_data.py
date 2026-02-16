"""ORM models for mock logistics data and project budgets."""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    Float,
    Integer,
    JSON,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.reconciliation import RecordSource


class MockLogisticsData(Base):
    __tablename__ = "mock_logistics_data"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    data_source: Mapped[RecordSource] = mapped_column(
        SAEnum(RecordSource, name="record_source", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    record_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reference_number: Mapped[str | None] = mapped_column(String(200), nullable=True)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ProjectBudget(Base):
    __tablename__ = "project_budgets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    project_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    budget_amount: Mapped[float] = mapped_column(Float, nullable=False)
    spent_amount: Mapped[float] = mapped_column(Float, default=0)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    fiscal_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_center: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
