"""Data-access layer for policy documents and their retrieval chunks.
Mirrors the pattern in `app/db/repository.py` — routes/services never
issue SQL directly.
"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.policy_chunk import PolicyChunkRecord
from app.db.models.policy_document import PolicyDocumentRecord


class PolicyDocumentRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_claim_id(self, claim_id: int) -> Optional[PolicyDocumentRecord]:
        result = await self._session.execute(
            select(PolicyDocumentRecord).where(PolicyDocumentRecord.claim_id == claim_id)
        )
        return result.scalar_one_or_none()

    async def upsert_for_claim(
        self,
        *,
        claim_id: int,
        user_id: Optional[int],
        filename: str,
        content_type: str,
        byte_size: int,
        storage_path: str,
    ) -> PolicyDocumentRecord:
        """A claimant may re-upload their policy (e.g. after a bad scan) —
        replace the prior document for this claim rather than accumulating
        duplicates, since only one policy is ever relevant to a claim."""

        existing = await self.get_by_claim_id(claim_id)
        if existing is not None:
            await self._session.execute(
                delete(PolicyChunkRecord).where(
                    PolicyChunkRecord.policy_document_id == existing.id
                )
            )
            await self._session.delete(existing)
            await self._session.flush()

        record = PolicyDocumentRecord(
            claim_id=claim_id,
            user_id=user_id,
            filename=filename,
            content_type=content_type,
            byte_size=byte_size,
            storage_path=storage_path,
            status="uploaded",
        )
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        return record

    async def save(self, record: PolicyDocumentRecord) -> PolicyDocumentRecord:
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        return record

    async def replace_chunks(
        self, policy_document_id: int, chunks: List[PolicyChunkRecord]
    ) -> None:
        await self._session.execute(
            delete(PolicyChunkRecord).where(
                PolicyChunkRecord.policy_document_id == policy_document_id
            )
        )
        for chunk in chunks:
            self._session.add(chunk)
        await self._session.commit()

    async def get_chunks(self, policy_document_id: int) -> List[PolicyChunkRecord]:
        result = await self._session.execute(
            select(PolicyChunkRecord)
            .where(PolicyChunkRecord.policy_document_id == policy_document_id)
            .order_by(PolicyChunkRecord.chunk_index)
        )
        return list(result.scalars().all())
