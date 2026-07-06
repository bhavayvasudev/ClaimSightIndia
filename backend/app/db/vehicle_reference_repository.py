"""Data-access layer for cached vehicle reference image resolutions.
Mirrors `app/db/repository.py`'s pattern — callers never issue SQL directly.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.vehicle_reference import VehicleReferenceImageRecord


class VehicleReferenceImageRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_normalized_query(self, normalized_query: str) -> Optional[VehicleReferenceImageRecord]:
        result = await self._session.execute(
            select(VehicleReferenceImageRecord).where(
                VehicleReferenceImageRecord.normalized_query == normalized_query
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self, *, normalized_query: str, image_url: str, source: str, match_confidence: float
    ) -> VehicleReferenceImageRecord:
        record = VehicleReferenceImageRecord(
            normalized_query=normalized_query,
            image_url=image_url,
            source=source,
            match_confidence=match_confidence,
        )
        self._session.add(record)
        try:
            await self._session.commit()
        except IntegrityError:
            # Two concurrent requests resolved the same vehicle — the
            # unique constraint on normalized_query means someone else
            # won; return their row instead of failing the request.
            await self._session.rollback()
            existing = await self.get_by_normalized_query(normalized_query)
            if existing is not None:
                return existing
            raise
        await self._session.refresh(record)
        return record

    async def update_resolution(
        self,
        record: VehicleReferenceImageRecord,
        *,
        image_url: str,
        source: str,
        match_confidence: float,
    ) -> VehicleReferenceImageRecord:
        """Upgrades a cached fallback row in place once a real image
        resolves — old claims pick the better image up automatically."""
        record.image_url = image_url
        record.source = source
        record.match_confidence = match_confidence
        await self._session.commit()
        await self._session.refresh(record)
        return record
