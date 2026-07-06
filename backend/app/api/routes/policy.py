"""Policy document upload + status endpoints (Task 2 prerequisite).

Ownership-aware exactly like `app/api/routes/claims.py`: every route
resolves the claim via `ClaimRepository.get_by_claim_id_for_user` first,
so a policy document can never be uploaded to or read from a claim that
isn't the caller's own.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.core.security import get_current_user
from app.db.models.user import UserRecord
from app.db.notification_repository import NotificationRepository
from app.db.policy_repository import PolicyDocumentRepository
from app.db.repository import ClaimRepository
from app.db.review_repository import ReviewItemRepository
from app.graph.orchestrator import run_claim_workflow
from app.db.session import get_db
from app.schemas.policy_api import PolicyDocumentResponse
from app.services.notifications import service as notification_service
from app.services.ai_client import AIServiceClient
from app.services.policy.service import PolicyUploadRejected, upload_and_process_policy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/claims", tags=["policy"])


def get_ai_service_client() -> AIServiceClient:
    return AIServiceClient()


@router.post("/{claim_id}/policy", response_model=PolicyDocumentResponse, status_code=201)
@limiter.limit("10/minute")
async def upload_policy(
    request: Request,
    claim_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user),
    ai_client: AIServiceClient = Depends(get_ai_service_client),
) -> PolicyDocumentResponse:
    claim_repo = ClaimRepository(db)
    claim = await claim_repo.get_by_claim_id_for_user(claim_id, current_user.id)
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found.")

    content = await file.read()
    policy_repo = PolicyDocumentRepository(db)

    try:
        record = await upload_and_process_policy(
            policy_repo,
            claim_id=claim.id,
            claim_public_id=claim.claim_id,
            user_id=current_user.id,
            filename=file.filename or "policy",
            content_type=file.content_type or "application/octet-stream",
            content=content,
        )
    except PolicyUploadRejected as exc:
        raise HTTPException(status_code=422, detail={"error_code": exc.error_code, "message": str(exc)})

    if record.status == "processed":
        review_repo = ReviewItemRepository(db)
        await run_claim_workflow(claim_repo, policy_repo, review_repo, ai_client, claim)

        if current_user.id is not None:
            notif_repo = NotificationRepository(db)
            await notification_service.notify_policy_analysis_completed(
                notif_repo, user_id=current_user.id, claim_id=claim.id, claim_public_id=claim.claim_id
            )
            await notification_service.notify_report_ready(
                notif_repo, user_id=current_user.id, claim_id=claim.id, claim_public_id=claim.claim_id
            )

    return PolicyDocumentResponse.from_record(record)


@router.get("/{claim_id}/policy", response_model=PolicyDocumentResponse)
async def get_policy_status(
    claim_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user),
) -> PolicyDocumentResponse:
    claim_repo = ClaimRepository(db)
    claim = await claim_repo.get_by_claim_id_for_user(claim_id, current_user.id)
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found.")

    policy_repo = PolicyDocumentRepository(db)
    record = await policy_repo.get_by_claim_id(claim.id)
    if record is None:
        raise HTTPException(status_code=404, detail="No policy document has been uploaded for this claim.")

    return PolicyDocumentResponse.from_record(record)
