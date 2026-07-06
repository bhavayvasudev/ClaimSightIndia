"""create claims table

Revision ID: 0001
Revises:
Create Date: 2026-07-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "claims",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("claim_id", sa.String(length=32), nullable=False),
        sa.Column("vehicle_type", sa.String(length=32), nullable=False),
        sa.Column("vehicle_make", sa.String(length=64), nullable=True),
        sa.Column("vehicle_model", sa.String(length=64), nullable=True),
        sa.Column("vehicle_year", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="intake"),
        sa.Column("ai_assessment", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("pricing_assessment", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_claims_claim_id", "claims", ["claim_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_claims_claim_id", table_name="claims")
    op.drop_table("claims")
