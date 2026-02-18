"""ORM model for document relationships — links between logistics documents."""

import enum
import uuid

import sqlalchemy as sa
from sqlalchemy import Enum as SAEnum, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class RelationshipType(str, enum.Enum):
    FULFILLS = "fulfills"       # BOL fulfills PO
    INVOICES = "invoices"       # Freight Invoice invoices BOL
    SUPPORTS = "supports"       # Packing List supports Commercial Invoice
    ADJUSTS = "adjusts"         # Credit Note adjusts Freight Invoice
    CERTIFIES = "certifies"     # CO certifies Commercial Invoice origin
    CLEARS = "clears"           # CBP 7501 clears Commercial Invoice
    CONFIRMS = "confirms"       # POD confirms BOL
    NOTIFIES = "notifies"       # Arrival Notice notifies BOL


class DocumentRelationship(Base, TimestampMixin):
    __tablename__ = "document_relationships"
    __table_args__ = (
        sa.UniqueConstraint(
            "source_document_id", "target_document_id", "relationship_type",
            name="uq_document_relationships_src_tgt_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    target_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    relationship_type: Mapped[RelationshipType] = mapped_column(
        SAEnum(
            RelationshipType,
            name="relationship_type",
            values_callable=lambda e: [member.value for member in e],
        ),
        nullable=False,
    )
    reference_field: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reference_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_by: Mapped[str] = mapped_column(String(50), default="system", nullable=False)
