"""add vehicle_variant column to claims

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("claims", sa.Column("vehicle_variant", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("claims", "vehicle_variant")
