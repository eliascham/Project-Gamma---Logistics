"""Phase 3: Cost Allocation & RAG tables

Expands scaffold tables from Phase 1 and adds new tables for cost allocation
business rules, allocation line items, and RAG query history.

Revision ID: 003_cost_allocation_rag
Revises: 002_doc_intelligence
Create Date: 2026-02-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PgENUM, UUID

revision: str = "003_cost_allocation_rag"
down_revision: Union[str, None] = "002_doc_intelligence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Create enum types via raw SQL (avoids sa.Enum auto-create conflicts) ──
    op.execute("CREATE TYPE allocation_status AS ENUM ('pending', 'allocated', 'review_needed', 'approved', 'rejected')")
    op.execute("CREATE TYPE line_item_status AS ENUM ('auto_approved', 'needs_review', 'manually_overridden')")

    # Reference-only: PgENUM with create_type=False to prevent auto-create in create_table
    allocation_status = PgENUM(
        "pending", "allocated", "review_needed", "approved", "rejected",
        name="allocation_status", create_type=False,
    )
    line_item_status = PgENUM(
        "auto_approved", "needs_review", "manually_overridden",
        name="line_item_status", create_type=False,
    )

    # ── Expand cost_allocations scaffold ──
    op.add_column("cost_allocations", sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=True))
    op.add_column("cost_allocations", sa.Column("extraction_id", UUID(as_uuid=True), sa.ForeignKey("extractions.id"), nullable=True))
    op.add_column("cost_allocations", sa.Column(
        "status",
        allocation_status,
        nullable=True,
        server_default="pending",
    ))
    op.add_column("cost_allocations", sa.Column("total_amount", sa.Float, nullable=True))
    op.add_column("cost_allocations", sa.Column("currency", sa.String(10), nullable=True, server_default="USD"))
    op.add_column("cost_allocations", sa.Column("allocated_by_model", sa.String(100), nullable=True))
    op.add_column("cost_allocations", sa.Column("processing_time_ms", sa.Integer, nullable=True))
    op.add_column("cost_allocations", sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=True,
    ))

    # ── New: allocation_line_items ──
    op.create_table(
        "allocation_line_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("allocation_id", UUID(as_uuid=True), sa.ForeignKey("cost_allocations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_item_index", sa.Integer, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("amount", sa.Float, nullable=False),
        sa.Column("project_code", sa.String(50), nullable=True),
        sa.Column("cost_center", sa.String(50), nullable=True),
        sa.Column("gl_account", sa.String(50), nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("reasoning", sa.Text, nullable=True),
        sa.Column(
            "status",
            line_item_status,
            nullable=True,
            server_default="auto_approved",
        ),
        sa.Column("override_project_code", sa.String(50), nullable=True),
        sa.Column("override_cost_center", sa.String(50), nullable=True),
        sa.Column("override_gl_account", sa.String(50), nullable=True),
        sa.Column("overridden_by", sa.String(100), nullable=True),
        sa.Column("overridden_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )

    # ── New: allocation_rules ──
    op.create_table(
        "allocation_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("rule_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("match_pattern", sa.Text, nullable=False),
        sa.Column("project_code", sa.String(50), nullable=False),
        sa.Column("cost_center", sa.String(50), nullable=False),
        sa.Column("gl_account", sa.String(50), nullable=False),
        sa.Column("priority", sa.Integer, nullable=False, server_default="10"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )

    # ── Expand embeddings scaffold ──
    # Change vector dimension from 1536 to 1024 (for Voyage 3)
    op.execute("ALTER TABLE embeddings DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE embeddings ADD COLUMN embedding vector(1024)")
    op.add_column("embeddings", sa.Column("source_type", sa.String(50), nullable=True))
    op.add_column("embeddings", sa.Column("source_id", UUID(as_uuid=True), nullable=True))
    op.add_column("embeddings", sa.Column("chunk_index", sa.Integer, nullable=True, server_default="0"))
    op.add_column("embeddings", sa.Column("metadata", sa.JSON, nullable=True))
    op.add_column("embeddings", sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=True,
    ))

    # ── New: rag_queries ──
    op.create_table(
        "rag_queries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("answer", sa.Text, nullable=True),
        sa.Column("source_document_ids", sa.JSON, nullable=True),
        sa.Column("source_chunks", sa.JSON, nullable=True),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("processing_time_ms", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── Indexes ──
    op.create_index("ix_allocation_line_items_allocation_id", "allocation_line_items", ["allocation_id"])
    op.create_index("ix_embeddings_source", "embeddings", ["source_type", "source_id"])
    op.create_index("ix_cost_allocations_document_id", "cost_allocations", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_cost_allocations_document_id")
    op.drop_index("ix_embeddings_source")
    op.drop_index("ix_allocation_line_items_allocation_id")
    op.drop_table("rag_queries")
    op.drop_column("embeddings", "updated_at")
    op.drop_column("embeddings", "metadata")
    op.drop_column("embeddings", "chunk_index")
    op.drop_column("embeddings", "source_id")
    op.drop_column("embeddings", "source_type")
    op.execute("ALTER TABLE embeddings DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE embeddings ADD COLUMN embedding vector(1536)")
    op.drop_table("allocation_rules")
    op.drop_table("allocation_line_items")
    op.execute("DROP TYPE IF EXISTS line_item_status")
    op.drop_column("cost_allocations", "updated_at")
    op.drop_column("cost_allocations", "processing_time_ms")
    op.drop_column("cost_allocations", "allocated_by_model")
    op.drop_column("cost_allocations", "currency")
    op.drop_column("cost_allocations", "total_amount")
    op.drop_column("cost_allocations", "status")
    op.drop_column("cost_allocations", "extraction_id")
    op.drop_column("cost_allocations", "document_id")
    op.execute("DROP TYPE IF EXISTS allocation_status")
