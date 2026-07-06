"""In-app user notifications (Task 12). No SMS/WhatsApp/email — see
`app/services/notifications/service.py` module docstring.
"""

import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NotificationType(str, enum.Enum):
    CLAIM_ANALYSIS_COMPLETED = "claim_analysis_completed"
    CLAIM_REVIEW_REQUIRED = "claim_review_required"
    POLICY_ANALYSIS_COMPLETED = "policy_analysis_completed"
    REPORT_READY = "report_ready"
    REVIEW_STATUS_UPDATED = "review_status_updated"


class NotificationRecord(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Every notification belongs to exactly one user; ownership is enforced
    # in every query the same way ClaimRepository scopes by user_id — see
    # app/db/notification_repository.py.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    claim_id: Mapped[int | None] = mapped_column(ForeignKey("claims.id"), nullable=True, index=True)

    type: Mapped[str] = mapped_column(String(48), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
