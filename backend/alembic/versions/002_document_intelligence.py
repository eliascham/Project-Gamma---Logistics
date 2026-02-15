"""Add document_type to documents, expand extractions table for 2-pass pipeline

Revision ID: 002_doc_intelligence
Revises: 001_initial
Create Date: 2026-02-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "002_doc_intelligence"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add document_type to documents table
    op.add_column("documents", sa.Column("document_type", sa.String(50), nullable=True))

    # Expand extractions table with 2-pass pipeline fields
    op.add_column(
        "extractions",
        sa.Column("document_type", sa.String(50), nullable=True),
    )
    op.add_column(
        "extractions",
        sa.Column("raw_extraction", sa.JSON, nullable=True),
    )
    op.add_column(
        "extractions",
        sa.Column("refined_extraction", sa.JSON, nullable=True),
    )
    op.add_column(
        "extractions",
        sa.Column("pass1_model", sa.String(100), nullable=True),
    )
    op.add_column(
        "extractions",
        sa.Column("pass2_model", sa.String(100), nullable=True),
    )
    op.add_column(
        "extractions",
        sa.Column("classifier_model", sa.String(100), nullable=True),
    )
    op.add_column(
        "extractions",
        sa.Column("processing_time_ms", sa.Integer, nullable=True),
    )
    op.add_column(
        "extractions",
        sa.Column("page_count", sa.Integer, nullable=True),
    )
    op.add_column(
        "extractions",
        sa.Column("vision_used", sa.Boolean, nullable=True, server_default="false"),
    )
    op.add_column(
        "extractions",
        sa.Column("metadata", sa.JSON, nullable=True),
    )

    # Add eval suite fields to eval_results
    op.add_column(
        "eval_results",
        sa.Column("document_count", sa.Integer, nullable=True),
    )
    op.add_column(
        "eval_results",
        sa.Column("overall_accuracy", sa.Float, nullable=True),
    )
    op.add_column(
        "eval_results",
        sa.Column("field_scores", sa.JSON, nullable=True),
    )
    op.add_column(
        "eval_results",
        sa.Column("model_used", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    # Remove eval_results additions
    op.drop_column("eval_results", "model_used")
    op.drop_column("eval_results", "field_scores")
    op.drop_column("eval_results", "overall_accuracy")
    op.drop_column("eval_results", "document_count")

    # Remove extractions additions
    op.drop_column("extractions", "metadata")
    op.drop_column("extractions", "vision_used")
    op.drop_column("extractions", "page_count")
    op.drop_column("extractions", "processing_time_ms")
    op.drop_column("extractions", "classifier_model")
    op.drop_column("extractions", "pass2_model")
    op.drop_column("extractions", "pass1_model")
    op.drop_column("extractions", "refined_extraction")
    op.drop_column("extractions", "raw_extraction")
    op.drop_column("extractions", "document_type")

    # Remove documents addition
    op.drop_column("documents", "document_type")
