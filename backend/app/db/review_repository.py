"""Data-access layer for manual review items. See
`app/db/models/review_item.py` for why there is deliberately no
public-facing "resolve" HTTP route built on top of this yet.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.review_item import ReviewItemRecord, ReviewItemStatus


class ReviewItemRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(
        self, *, claim_id: int, part: Optional[str], reason: str, source: str
    ) -> ReviewItemRecord:
        record = ReviewItemRecord(claim_id=claim_id, part=part, reason=reason, source=source)
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        return record

    async def list_for_claim(self, claim_id: int) -> List[ReviewItemRecord]:
        result = await self._session.execute(
            select(ReviewItemRecord)
            .where(ReviewItemRecord.claim_id == claim_id)
            .order_by(ReviewItemRecord.created_at.asc())
        )
        return list(result.scalars().all())

    async def replace_open_items_for_claim(
        self, claim_id: int, new_items: List[tuple[Optional[str], str, str]]
    ) -> None:
        """Re-derives the open (pending/in_review) review queue for a claim
        from the latest analysis pass. Resolved items are historical
        record and are never touched here — only pending/in_review items
        (which reflect the *previous* pass's findings) are replaced."""

        existing = await self.list_for_claim(claim_id)
        for item in existing:
            if item.status != ReviewItemStatus.RESOLVED.value:
                await self._session.delete(item)
        await self._session.flush()

        for part, reason, source in new_items:
            self._session.add(
                ReviewItemRecord(claim_id=claim_id, part=part, reason=reason, source=source)
            )
        await self._session.commit()

    async def resolve(
        self, review_item_id: int, *, reviewer_note: Optional[str] = None
    ) -> Optional[ReviewItemRecord]:
        """Internal capability, not exposed over HTTP yet — see module
        docstring on `app/db/models/review_item.py`."""
        result = await self._session.execute(
            select(ReviewItemRecord).where(ReviewItemRecord.id == review_item_id)
        )
        record = result.scalar_one_or_none()
        if record is None:
            return None
        record.status = ReviewItemStatus.RESOLVED.value
        record.reviewer_note = reviewer_note
        record.resolved_at = datetime.now(timezone.utc)
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        return record
