"""Phase 5: Document Intelligence Expansion

Revision ID: 005_phase5_doc_relationships
Revises: 004_guardrails
Create Date: 2026-02-17

Creates the document_relationships table for tracking links between logistics
documents (PO -> Invoice, BOL -> POD, etc.) and the relationship_type enum.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "005_phase5_doc_relationships"
down_revision: Union[str, None] = "004_guardrails"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum type via raw SQL
    op.execute("""
        CREATE TYPE relationship_type AS ENUM (
            'fulfills', 'invoices', 'supports', 'adjusts',
            'certifies', 'clears', 'confirms', 'notifies'
        )
    """)

    from sqlalchemy.dialects.postgresql import ENUM as PgENUM

    # Create document_relationships table
    op.create_table(
        "document_relationships",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("source_document_id", UUID(as_uuid=True),
                  sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("target_document_id", UUID(as_uuid=True),
                  sa.ForeignKey("documents.id"), nullable=False),
        sa.Column(
            "relationship_type",
            PgENUM("fulfills", "invoices", "supports", "adjusts",
                   "certifies", "clears", "confirms", "notifies",
                   name="relationship_type", create_type=False),
            nullable=False,
        ),
        sa.Column("reference_field", sa.String(100), nullable=True),
        sa.Column("reference_value", sa.String(500), nullable=True),
        sa.Column("confidence", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("created_by", sa.String(50), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=True),
    )

    # Unique constraint: prevent duplicate relationships
    op.create_unique_constraint(
        "uq_document_relationships_src_tgt_type",
        "document_relationships",
        ["source_document_id", "target_document_id", "relationship_type"],
    )

    # Indexes for efficient lookup
    op.create_index(
        "ix_document_relationships_source",
        "document_relationships",
        ["source_document_id"],
    )
    op.create_index(
        "ix_document_relationships_target",
        "document_relationships",
        ["target_document_id"],
    )
    op.create_index(
        "ix_document_relationships_ref_value",
        "document_relationships",
        ["reference_value"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_document_relationships_src_tgt_type", "document_relationships", type_="unique")
    op.drop_index("ix_document_relationships_ref_value")
    op.drop_index("ix_document_relationships_target")
    op.drop_index("ix_document_relationships_source")
    op.drop_table("document_relationships")
    op.execute("DROP TYPE IF EXISTS relationship_type")
