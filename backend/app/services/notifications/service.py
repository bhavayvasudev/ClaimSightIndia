"""In-app notification creation (Task 12).

No SMS/WhatsApp — not implemented. No email — no email provider is
configured anywhere in this project (`app/config.py` has no SMTP/email
settings), so this stays in-app only, as instructed. Each `notify_*`
function is called from the route layer at the exact point the
corresponding real event completes — never speculatively, never once per
internal graph node (see Task 12: "do not spam users").
"""

from __future__ import annotations

from typing import Optional

from app.db.models.notification import NotificationType
from app.db.notification_repository import NotificationRepository


async def notify_claim_analysis_completed(repo: NotificationRepository, *, user_id: int, claim_id: int, claim_public_id: str) -> None:
    await repo.create(
        user_id=user_id,
        claim_id=claim_id,
        type=NotificationType.CLAIM_ANALYSIS_COMPLETED.value,
        title="Claim analysis completed",
        body=f"The damage assessment for claim {claim_public_id} is ready to view.",
    )


async def notify_claim_review_required(repo: NotificationRepository, *, user_id: int, claim_id: int, claim_public_id: str) -> None:
    await repo.create(
        user_id=user_id,
        claim_id=claim_id,
        type=NotificationType.CLAIM_REVIEW_REQUIRED.value,
        title="Claim moved to manual review",
        body=f"Claim {claim_public_id} has one or more findings that need manual review.",
    )


async def notify_policy_analysis_completed(repo: NotificationRepository, *, user_id: int, claim_id: int, claim_public_id: str) -> None:
    await repo.create(
        user_id=user_id,
        claim_id=claim_id,
        type=NotificationType.POLICY_ANALYSIS_COMPLETED.value,
        title="Policy analysis completed",
        body=f"The uploaded policy document for claim {claim_public_id} has been processed.",
    )


async def notify_report_ready(repo: NotificationRepository, *, user_id: int, claim_id: int, claim_public_id: str) -> None:
    await repo.create(
        user_id=user_id,
        claim_id=claim_id,
        type=NotificationType.REPORT_READY.value,
        title="Claim report ready",
        body=f"The unified claim report for {claim_public_id} is ready to view.",
    )
