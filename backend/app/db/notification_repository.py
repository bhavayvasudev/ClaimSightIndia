"""Data-access layer for notifications. Every query is scoped to a
`user_id` in the query itself — same ownership-in-the-query principle as
`ClaimRepository` (see that module's docstring).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.notification import NotificationRecord


class NotificationRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(
        self,
        *,
        user_id: int,
        claim_id: Optional[int],
        type: str,
        title: str,
        body: str,
    ) -> NotificationRecord:
        record = NotificationRecord(
            user_id=user_id, claim_id=claim_id, type=type, title=title, body=body
        )
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        return record

    async def list_for_user(
        self, user_id: int, *, limit: int = 50, offset: int = 0
    ) -> List[NotificationRecord]:
        result = await self._session.execute(
            select(NotificationRecord)
            .where(NotificationRecord.user_id == user_id)
            .order_by(NotificationRecord.created_at.desc(), NotificationRecord.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def unread_count(self, user_id: int) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(NotificationRecord)
            .where(NotificationRecord.user_id == user_id, NotificationRecord.read_at.is_(None))
        )
        return int(result.scalar_one())

    async def mark_read(self, notification_id: int, user_id: int) -> Optional[NotificationRecord]:
        """Ownership-scoped: a caller can only ever mark their own
        notification read — the `user_id` filter is in the query, not
        checked after the fact."""
        result = await self._session.execute(
            select(NotificationRecord).where(
                NotificationRecord.id == notification_id, NotificationRecord.user_id == user_id
            )
        )
        record = result.scalar_one_or_none()
        if record is None:
            return None
        if record.read_at is None:
            record.read_at = datetime.now(timezone.utc)
            self._session.add(record)
            await self._session.commit()
            await self._session.refresh(record)
        return record

    async def mark_all_read(self, user_id: int) -> None:
        await self._session.execute(
            update(NotificationRecord)
            .where(NotificationRecord.user_id == user_id, NotificationRecord.read_at.is_(None))
            .values(read_at=datetime.now(timezone.utc))
        )
        await self._session.commit()
