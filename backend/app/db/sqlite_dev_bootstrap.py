"""Sqlite dev/sandbox schema bootstrap.

Real deployments run Postgres with Alembic-managed migrations
(`alembic upgrade head`). This module only runs against the sqlite
substitute described in `backend/.env`'s inline note and
`docs/architecture.md` — Alembic's sync engine can't run migrations
0001+ against sqlite at all, so local/test dev uses
`Base.metadata.create_all()` instead (`tests/conftest.py`'s
fresh-per-test in-memory sqlite already makes this exact tradeoff; this
persists it across runs instead of per-test).

`create_all()` alone only adds missing *tables* — a `dev.db` created
before a model gained a new column still has the old, narrower one, and
every query touching that table then fails with sqlite's
"no such column: ..." (`OperationalError`, surfaced to callers as a
generic 500). That exact drift was the original cause of "claim could
not be found" / repeated 404s this batch was asked to fix — a stale
`dev.db` missing columns the current `ClaimRecord` model expects. Rather
than requiring a manual `rm dev.db` every time a model gains a column
during local dev, `sync_missing_columns` closes that gap by adding any
column present on the model but missing from the actual sqlite table.
Only additive column changes are handled (a real ALTER TABLE ADD COLUMN)
— renames/drops/type changes still require a fresh `dev.db`, same as
before.
"""

from __future__ import annotations

import logging

import sqlalchemy as sa
from sqlalchemy import inspect

from app.db.base import Base

logger = logging.getLogger(__name__)


def sync_missing_columns(sync_conn: sa.engine.Connection) -> None:
    inspector = inspect(sync_conn)
    existing_tables = set(inspector.get_table_names())

    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue  # create_all already created this one from scratch

        existing_columns = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing_columns:
                continue
            column_type = column.type.compile(dialect=sync_conn.dialect)
            logger.warning(
                "sqlite dev.db missing column %s.%s — adding it (ALTER TABLE ADD COLUMN)",
                table.name,
                column.name,
            )
            sync_conn.execute(
                sa.text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {column_type}')
            )
