"""add policy documents/chunks, review items, notifications, and claim
workflow columns

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("claims", sa.Column("incident_date", sa.Date(), nullable=True))
    # JSONB (not plain JSON) to match app/db/models/claim.py's `_jsonb_or_json()` —
    # same convention migration 0001 already established for ai_assessment/pricing_assessment.
    op.add_column(
        "claims", sa.Column("image_hashes", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.add_column(
        "claims",
        sa.Column("coverage_analysis", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "claims", sa.Column("risk_assessment", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.add_column(
        "claims", sa.Column("report_generated_at", sa.DateTime(timezone=True), nullable=True)
    )

    op.create_table(
        "policy_documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("claim_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("extraction_method", sa.String(length=16), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("structured_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_policy_documents_claim_id", "policy_documents", ["claim_id"], unique=True
    )
    op.create_index("ix_policy_documents_user_id", "policy_documents", ["user_id"])
    op.create_foreign_key(
        "fk_policy_documents_claim_id_claims", "policy_documents", "claims", ["claim_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_policy_documents_user_id_users", "policy_documents", "users", ["user_id"], ["id"]
    )

    op.create_table(
        "policy_chunks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("policy_document_id", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section", sa.String(length=255), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_policy_chunks_policy_document_id", "policy_chunks", ["policy_document_id"]
    )
    op.create_foreign_key(
        "fk_policy_chunks_policy_document_id_policy_documents",
        "policy_chunks",
        "policy_documents",
        ["policy_document_id"],
        ["id"],
    )

    op.create_table(
        "review_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("claim_id", sa.Integer(), nullable=False),
        sa.Column("part", sa.String(length=128), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reviewer_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_review_items_claim_id", "review_items", ["claim_id"])
    op.create_foreign_key(
        "fk_review_items_claim_id_claims", "review_items", "claims", ["claim_id"], ["id"]
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("claim_id", sa.Integer(), nullable=True),
        sa.Column("type", sa.String(length=48), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_claim_id", "notifications", ["claim_id"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])
    op.create_foreign_key(
        "fk_notifications_user_id_users", "notifications", "users", ["user_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_notifications_claim_id_claims", "notifications", "claims", ["claim_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("review_items")
    op.drop_index("ix_policy_chunks_policy_document_id", table_name="policy_chunks")
    op.drop_table("policy_chunks")
    op.drop_index("ix_policy_documents_user_id", table_name="policy_documents")
    op.drop_index("ix_policy_documents_claim_id", table_name="policy_documents")
    op.drop_table("policy_documents")

    op.drop_column("claims", "report_generated_at")
    op.drop_column("claims", "risk_assessment")
    op.drop_column("claims", "coverage_analysis")
    op.drop_column("claims", "image_hashes")
    op.drop_column("claims", "incident_date")
