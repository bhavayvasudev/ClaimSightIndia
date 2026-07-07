"""add legal consent fields to users

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-07

All three columns are nullable with no default backfill: existing users
keep signing in exactly as before, and simply have no recorded consent
until they next go through the sign-in page's consent checkbox (see
app/core/legal.py).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("privacy_accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("legal_version_accepted", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "legal_version_accepted")
    op.drop_column("users", "privacy_accepted_at")
    op.drop_column("users", "terms_accepted_at")
