"""add users table and claims.user_id

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("google_sub", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.String(length=1024), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_users_google_sub", "users", ["google_sub"], unique=True)

    op.add_column("claims", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_index("ix_claims_user_id", "claims", ["user_id"])
    op.create_foreign_key(
        "fk_claims_user_id_users", "claims", "users", ["user_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_claims_user_id_users", "claims", type_="foreignkey")
    op.drop_index("ix_claims_user_id", table_name="claims")
    op.drop_column("claims", "user_id")

    op.drop_index("ix_users_google_sub", table_name="users")
    op.drop_table("users")
