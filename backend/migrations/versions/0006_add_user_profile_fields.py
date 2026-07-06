"""add user-customizable profile fields to users

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-06

All three columns are nullable with no default backfill: existing users
keep behaving exactly as before (provider-derived email/name/avatar stay
the effective values until the user customizes something).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("display_name", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("contact_email", sa.String(length=320), nullable=True))
    op.add_column("users", sa.Column("custom_avatar_url", sa.String(length=1024), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "custom_avatar_url")
    op.drop_column("users", "contact_email")
    op.drop_column("users", "display_name")
