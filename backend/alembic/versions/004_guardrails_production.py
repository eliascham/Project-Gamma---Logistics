"""Phase 4: Guardrails & Production Hardening

Revision ID: 004_guardrails
Revises: 003_cost_allocation_rag
Create Date: 2026-02-15

Expands scaffold tables (audit_events, review_queue, reconciliation_runs)
and creates new tables (anomaly_flags, reconciliation_records, mock_logistics_data,
project_budgets) for Phase 4 features.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "004_guardrails"
down_revision: Union[str, None] = "003_cost_allocation_rag"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Create enum types via raw SQL ──
    op.execute("""
        CREATE TYPE review_status AS ENUM (
            'pending_review', 'approved', 'rejected', 'escalated', 'auto_approved'
        )
    """)
    op.execute("""
        CREATE TYPE review_item_type AS ENUM (
            'cost_allocation', 'anomaly', 'reconciliation_mismatch'
        )
    """)
    op.execute("""
        CREATE TYPE anomaly_type AS ENUM (
            'duplicate_invoice', 'budget_overrun', 'misallocated_cost',
            'unusual_amount', 'missing_approval', 'reconciliation_mismatch'
        )
    """)
    op.execute("""
        CREATE TYPE anomaly_severity AS ENUM (
            'low', 'medium', 'high', 'critical'
        )
    """)
    op.execute("""
        CREATE TYPE reconciliation_status AS ENUM (
            'pending', 'matched', 'partial_match', 'mismatch', 'resolved'
        )
    """)
    op.execute("""
        CREATE TYPE record_source AS ENUM (
            'tms', 'wms', 'erp'
        )
    """)

    # ── Expand audit_events (scaffold had: id, event_type, event_data, created_at) ──
    op.add_column("audit_events", sa.Column("entity_type", sa.String(100), nullable=True))
    op.add_column("audit_events", sa.Column("entity_id", UUID(as_uuid=True), nullable=True))
    op.add_column("audit_events", sa.Column("action", sa.String(100), nullable=True))
    op.add_column("audit_events", sa.Column("actor", sa.String(200), nullable=True))
    op.add_column("audit_events", sa.Column("actor_type", sa.String(50), nullable=True, server_default="system"))
    op.add_column("audit_events", sa.Column("previous_state", sa.JSON, nullable=True))
    op.add_column("audit_events", sa.Column("new_state", sa.JSON, nullable=True))
    op.add_column("audit_events", sa.Column("rationale", sa.Text, nullable=True))
    op.add_column("audit_events", sa.Column("model_used", sa.String(100), nullable=True))
    op.add_column("audit_events", sa.Column("ip_address", sa.String(45), nullable=True))
    op.add_column("audit_events", sa.Column(
        "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True
    ))
    op.create_index("ix_audit_events_entity", "audit_events", ["entity_type", "entity_id"])
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])

    # ── Expand review_queue (scaffold had: id, status VARCHAR, created_at) ──
    # Drop old VARCHAR status column (table is empty, safe)
    op.drop_column("review_queue", "status")
    # Add new columns with enum status
    from sqlalchemy.dialects.postgresql import ENUM as PgENUM
    op.add_column("review_queue", sa.Column(
        "status",
        PgENUM("pending_review", "approved", "rejected", "escalated", "auto_approved",
               name="review_status", create_type=False),
        nullable=False,
        server_default="pending_review",
    ))
    op.add_column("review_queue", sa.Column(
        "item_type",
        PgENUM("cost_allocation", "anomaly", "reconciliation_mismatch",
               name="review_item_type", create_type=False),
        nullable=True,
    ))
    op.add_column("review_queue", sa.Column("entity_id", UUID(as_uuid=True), nullable=True))
    op.add_column("review_queue", sa.Column("entity_type", sa.String(100), nullable=True))
    op.add_column("review_queue", sa.Column("title", sa.String(500), nullable=True))
    op.add_column("review_queue", sa.Column("description", sa.Text, nullable=True))
    op.add_column("review_queue", sa.Column(
        "severity",
        PgENUM("low", "medium", "high", "critical",
               name="anomaly_severity", create_type=False),
        nullable=True,
    ))
    op.add_column("review_queue", sa.Column("assigned_to", sa.String(200), nullable=True))
    op.add_column("review_queue", sa.Column("reviewed_by", sa.String(200), nullable=True))
    op.add_column("review_queue", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("review_queue", sa.Column("review_notes", sa.Text, nullable=True))
    op.add_column("review_queue", sa.Column("auto_approve_eligible", sa.Boolean, server_default="false"))
    op.add_column("review_queue", sa.Column("dollar_amount", sa.Float, nullable=True))
    op.add_column("review_queue", sa.Column("metadata", sa.JSON, nullable=True))
    op.add_column("review_queue", sa.Column(
        "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True
    ))
    op.create_index("ix_review_queue_status", "review_queue", ["status"])
    op.create_index("ix_review_queue_item_type", "review_queue", ["item_type"])

    # ── New table: anomaly_flags ──
    op.create_table(
        "anomaly_flags",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("allocation_id", UUID(as_uuid=True), sa.ForeignKey("cost_allocations.id"), nullable=True),
        sa.Column(
            "anomaly_type",
            PgENUM("duplicate_invoice", "budget_overrun", "misallocated_cost",
                   "unusual_amount", "missing_approval", "reconciliation_mismatch",
                   name="anomaly_type", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "severity",
            PgENUM("low", "medium", "high", "critical",
                   name="anomaly_severity", create_type=False),
            nullable=False,
            server_default="medium",
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("details", sa.JSON, nullable=True),
        sa.Column("is_resolved", sa.Boolean, server_default="false", nullable=False),
        sa.Column("resolved_by", sa.String(200), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_notes", sa.Text, nullable=True),
        sa.Column("review_item_id", UUID(as_uuid=True), sa.ForeignKey("review_queue.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )

    # ── Expand reconciliation_runs (scaffold had: id, created_at) ──
    op.add_column("reconciliation_runs", sa.Column("name", sa.String(200), nullable=True))
    op.add_column("reconciliation_runs", sa.Column("description", sa.Text, nullable=True))
    op.add_column("reconciliation_runs", sa.Column(
        "status",
        PgENUM("pending", "matched", "partial_match", "mismatch", "resolved",
               name="reconciliation_status", create_type=False),
        nullable=True,
        server_default="pending",
    ))
    op.add_column("reconciliation_runs", sa.Column("total_records", sa.Integer, nullable=True))
    op.add_column("reconciliation_runs", sa.Column("matched_count", sa.Integer, nullable=True))
    op.add_column("reconciliation_runs", sa.Column("mismatch_count", sa.Integer, nullable=True))
    op.add_column("reconciliation_runs", sa.Column("match_rate", sa.Float, nullable=True))
    op.add_column("reconciliation_runs", sa.Column("run_by", sa.String(200), nullable=True))
    op.add_column("reconciliation_runs", sa.Column("model_used", sa.String(100), nullable=True))
    op.add_column("reconciliation_runs", sa.Column("processing_time_ms", sa.Integer, nullable=True))
    op.add_column("reconciliation_runs", sa.Column("summary", sa.JSON, nullable=True))
    op.add_column("reconciliation_runs", sa.Column(
        "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True
    ))

    # ── New table: reconciliation_records ──
    op.create_table(
        "reconciliation_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "source",
            PgENUM("tms", "wms", "erp", name="record_source", create_type=False),
            nullable=False,
        ),
        sa.Column("record_type", sa.String(100), nullable=True),
        sa.Column("reference_number", sa.String(200), nullable=True),
        sa.Column("record_data", sa.JSON, nullable=True),
        sa.Column(
            "match_status",
            PgENUM("pending", "matched", "partial_match", "mismatch", "resolved",
                   name="reconciliation_status", create_type=False),
            nullable=True,
            server_default="pending",
        ),
        sa.Column("matched_with_id", UUID(as_uuid=True), nullable=True),
        sa.Column("match_confidence", sa.Float, nullable=True),
        sa.Column("match_reasoning", sa.Text, nullable=True),
        sa.Column("mismatch_details", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_reconciliation_records_ref", "reconciliation_records", ["reference_number"])

    # ── New table: mock_logistics_data ──
    op.create_table(
        "mock_logistics_data",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "data_source",
            PgENUM("tms", "wms", "erp", name="record_source", create_type=False),
            nullable=False,
        ),
        sa.Column("record_type", sa.String(100), nullable=True),
        sa.Column("reference_number", sa.String(200), nullable=True),
        sa.Column("data", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_mock_logistics_data_ref", "mock_logistics_data", ["reference_number"])

    # ── New table: project_budgets ──
    op.create_table(
        "project_budgets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_code", sa.String(50), nullable=False, unique=True),
        sa.Column("project_name", sa.String(200), nullable=True),
        sa.Column("budget_amount", sa.Float, nullable=False),
        sa.Column("spent_amount", sa.Float, server_default="0", nullable=False),
        sa.Column("currency", sa.String(10), server_default="USD"),
        sa.Column("fiscal_year", sa.Integer, nullable=True),
        sa.Column("cost_center", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("project_budgets")
    op.drop_table("mock_logistics_data")
    op.drop_table("reconciliation_records")

    # Revert reconciliation_runs
    op.drop_column("reconciliation_runs", "updated_at")
    op.drop_column("reconciliation_runs", "summary")
    op.drop_column("reconciliation_runs", "processing_time_ms")
    op.drop_column("reconciliation_runs", "model_used")
    op.drop_column("reconciliation_runs", "run_by")
    op.drop_column("reconciliation_runs", "match_rate")
    op.drop_column("reconciliation_runs", "mismatch_count")
    op.drop_column("reconciliation_runs", "matched_count")
    op.drop_column("reconciliation_runs", "total_records")
    op.drop_column("reconciliation_runs", "status")
    op.drop_column("reconciliation_runs", "description")
    op.drop_column("reconciliation_runs", "name")

    op.drop_table("anomaly_flags")

    # Revert review_queue
    op.drop_index("ix_review_queue_item_type")
    op.drop_index("ix_review_queue_status")
    op.drop_column("review_queue", "updated_at")
    op.drop_column("review_queue", "metadata")
    op.drop_column("review_queue", "dollar_amount")
    op.drop_column("review_queue", "auto_approve_eligible")
    op.drop_column("review_queue", "review_notes")
    op.drop_column("review_queue", "reviewed_at")
    op.drop_column("review_queue", "reviewed_by")
    op.drop_column("review_queue", "assigned_to")
    op.drop_column("review_queue", "severity")
    op.drop_column("review_queue", "description")
    op.drop_column("review_queue", "title")
    op.drop_column("review_queue", "entity_type")
    op.drop_column("review_queue", "entity_id")
    op.drop_column("review_queue", "item_type")
    op.drop_column("review_queue", "status")
    op.add_column("review_queue", sa.Column("status", sa.String(50), server_default="pending_review"))

    # Revert audit_events
    op.drop_index("ix_audit_events_event_type")
    op.drop_index("ix_audit_events_entity")
    op.drop_column("audit_events", "updated_at")
    op.drop_column("audit_events", "ip_address")
    op.drop_column("audit_events", "model_used")
    op.drop_column("audit_events", "rationale")
    op.drop_column("audit_events", "new_state")
    op.drop_column("audit_events", "previous_state")
    op.drop_column("audit_events", "actor_type")
    op.drop_column("audit_events", "actor")
    op.drop_column("audit_events", "action")
    op.drop_column("audit_events", "entity_id")
    op.drop_column("audit_events", "entity_type")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS record_source")
    op.execute("DROP TYPE IF EXISTS reconciliation_status")
    op.execute("DROP TYPE IF EXISTS anomaly_severity")
    op.execute("DROP TYPE IF EXISTS anomaly_type")
    op.execute("DROP TYPE IF EXISTS review_item_type")
    op.execute("DROP TYPE IF EXISTS review_status")
