"""Data-access layer for users. Mirrors `app/db/repository.py`'s pattern
for claims — the route/service layers never issue SQL directly.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import UserRecord


class UserRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_google_sub(self, google_sub: str) -> Optional[UserRecord]:
        result = await self._session.execute(
            select(UserRecord).where(UserRecord.google_sub == google_sub)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> Optional[UserRecord]:
        result = await self._session.execute(
            select(UserRecord).where(UserRecord.id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        google_sub: str,
        email: str,
        name: Optional[str],
        avatar_url: Optional[str],
    ) -> UserRecord:
        record = UserRecord(google_sub=google_sub, email=email, name=name, avatar_url=avatar_url)
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        return record

    async def save(self, record: UserRecord) -> UserRecord:
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        return record
