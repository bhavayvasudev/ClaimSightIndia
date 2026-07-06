"""Notification endpoints (Task 12). Every route is scoped to the
authenticated caller's own notifications — see
`app/db/notification_repository.py`."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.models.user import UserRecord
from app.db.notification_repository import NotificationRepository
from app.db.repository import ClaimRepository
from app.db.session import get_db
from app.schemas.notification_api import NotificationItem, NotificationListResponse

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> NotificationListResponse:
    repo = NotificationRepository(db)
    claim_repo = ClaimRepository(db)
    records = await repo.list_for_user(current_user.id, limit=limit, offset=offset)
    unread_count = await repo.unread_count(current_user.id)

    claim_ids = [r.claim_id for r in records if r.claim_id is not None]
    claims_by_id = {c.id: c.claim_id for c in await claim_repo.get_by_ids(claim_ids)}

    items = [
        NotificationItem.from_record(record, claims_by_id.get(record.claim_id))
        for record in records
    ]

    return NotificationListResponse(items=items, unread_count=unread_count)


@router.get("/unread-count")
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user),
) -> dict:
    repo = NotificationRepository(db)
    return {"unread_count": await repo.unread_count(current_user.id)}


@router.post("/{notification_id}/read", response_model=NotificationItem)
async def mark_notification_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user),
) -> NotificationItem:
    repo = NotificationRepository(db)
    record = await repo.mark_read(notification_id, current_user.id)
    if record is None:
        raise HTTPException(status_code=404, detail="Notification not found.")
    return NotificationItem.from_record(record, None)


@router.post("/read-all")
async def mark_all_notifications_read(
    db: AsyncSession = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user),
) -> dict:
    repo = NotificationRepository(db)
    await repo.mark_all_read(current_user.id)
    return {"status": "ok"}
