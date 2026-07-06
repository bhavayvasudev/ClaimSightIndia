"""Request/response schemas for the notification API
(`app/api/routes/notifications.py`)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.db.models.notification import NotificationRecord


class NotificationItem(BaseModel):
    id: int
    claim_id: Optional[str] = None
    type: str
    title: str
    body: str
    read: bool
    created_at: datetime

    @classmethod
    def from_record(cls, record: NotificationRecord, claim_public_id: Optional[str]) -> "NotificationItem":
        return cls(
            id=record.id,
            claim_id=claim_public_id,
            type=record.type,
            title=record.title,
            body=record.body,
            read=record.read_at is not None,
            created_at=record.created_at,
        )


class NotificationListResponse(BaseModel):
    items: list[NotificationItem]
    unread_count: int
