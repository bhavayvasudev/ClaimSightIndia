"""Data-access layer for claims. Routes and services never issue SQL
directly — everything goes through `ClaimRepository` so the one place that
knows about `AsyncSession`/`select()` can change without touching callers.
"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.claim import ClaimRecord


class ClaimRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(
        self,
        *,
        claim_id: str,
        vehicle_type: str,
        vehicle_make: Optional[str],
        vehicle_model: Optional[str],
        vehicle_year: Optional[int],
        vehicle_variant: Optional[str] = None,
        user_id: Optional[int] = None,
        incident_date=None,
    ) -> ClaimRecord:
        record = ClaimRecord(
            claim_id=claim_id,
            vehicle_type=vehicle_type,
            vehicle_make=vehicle_make,
            vehicle_model=vehicle_model,
            vehicle_variant=vehicle_variant,
            vehicle_year=vehicle_year,
            user_id=user_id,
            incident_date=incident_date,
        )
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        return record

    async def get_by_claim_id(self, claim_id: str) -> Optional[ClaimRecord]:
        result = await self._session.execute(
            select(ClaimRecord).where(ClaimRecord.claim_id == claim_id)
        )
        return result.scalar_one_or_none()

    async def get_by_ids(self, ids: list[int]) -> List[ClaimRecord]:
        """Batch lookup by internal primary key — used to resolve the
        public `claim_id` string for rows (e.g. notifications) that only
        store the internal foreign key. Not ownership-scoped itself since
        callers only ever use it to look up ids already known to belong to
        the current user (see app/api/routes/notifications.py)."""
        if not ids:
            return []
        result = await self._session.execute(select(ClaimRecord).where(ClaimRecord.id.in_(ids)))
        return list(result.scalars().all())

    async def get_by_claim_id_for_user(self, claim_id: str, user_id: int) -> Optional[ClaimRecord]:
        """Ownership-aware lookup — returns None both when the claim
        doesn't exist and when it belongs to a different user, so callers
        can't distinguish the two (see the 404-not-403 policy in
        app/api/routes/claims.py)."""
        result = await self._session.execute(
            select(ClaimRecord).where(
                ClaimRecord.claim_id == claim_id, ClaimRecord.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self, user_id: int, *, limit: int = 50, offset: int = 0
    ) -> List[ClaimRecord]:
        """Newest-first, scoped to `user_id` in the query itself (not
        filtered after the fact) — the same ownership-in-the-query
        principle as `get_by_claim_id_for_user`. Never accepts an
        arbitrary caller-supplied user id; the route only ever passes the
        authenticated user's own id."""
        result = await self._session.execute(
            select(ClaimRecord)
            .where(ClaimRecord.user_id == user_id)
            # id DESC as a tiebreaker: created_at has only second-level
            # resolution on some backends (e.g. SQLite's CURRENT_TIMESTAMP),
            # so two claims created within the same second would otherwise
            # sort in an unstable order.
            .order_by(ClaimRecord.created_at.desc(), ClaimRecord.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def save(self, record: ClaimRecord) -> ClaimRecord:
        """Persist mutations the caller already made on `record` (status,
        ai_assessment, pricing_assessment, ...)."""
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        return record
