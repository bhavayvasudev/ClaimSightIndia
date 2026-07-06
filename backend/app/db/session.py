"""Async SQLAlchemy engine/session.

`postgresql+psycopg` (psycopg 3) is the one driver SQLAlchemy supports in
both sync and async mode under the same URL scheme, so `settings.database_url`
works unchanged for the app's async engine here and for Alembic's sync
engine in `migrations/env.py` — no separate "async" URL to keep in sync.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, pool_pre_ping=True)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
