"""add vehicle_reference_images table

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vehicle_reference_images",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("normalized_query", sa.String(length=255), nullable=False),
        sa.Column("image_url", sa.String(length=512), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("match_confidence", sa.Float(), nullable=False),
        sa.Column(
            "resolved_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_vehicle_reference_images_normalized_query",
        "vehicle_reference_images",
        ["normalized_query"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_vehicle_reference_images_normalized_query", table_name="vehicle_reference_images")
    op.drop_table("vehicle_reference_images")
