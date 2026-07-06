"""Alembic environment.

Uses a synchronous engine for migrations even though the app talks to
Postgres asynchronously at runtime (`app/db/session.py`). `postgresql+psycopg`
(psycopg 3) is the one SQLAlchemy driver that supports both sync and async
under the same URL, so `settings.database_url` is reused unchanged here —
there's no separate "migration URL" to keep in sync with the app's.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.db.base import Base
from app.db.models.claim import ClaimRecord  # noqa: F401  (registers the table on Base.metadata)
from app.db.models.user import UserRecord  # noqa: F401  (registers the table on Base.metadata)
from app.db.models.vehicle_reference import VehicleReferenceImageRecord  # noqa: F401  (registers the table on Base.metadata)
from app.db.models.policy_document import PolicyDocumentRecord  # noqa: F401  (registers the table on Base.metadata)
from app.db.models.policy_chunk import PolicyChunkRecord  # noqa: F401  (registers the table on Base.metadata)
from app.db.models.review_item import ReviewItemRecord  # noqa: F401  (registers the table on Base.metadata)
from app.db.models.notification import NotificationRecord  # noqa: F401  (registers the table on Base.metadata)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
