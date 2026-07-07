"""Claim intake + analysis endpoints.

Thin by design: request/response mapping and HTTP-error translation only.
All real orchestration lives in `app.services.claim_service`, which knows
nothing about FastAPI — see that module for the actual create/analyze flow.

Every route requires an authenticated caller (`get_current_user`) and every
claim lookup is ownership-aware (`ClaimRepository.get_by_claim_id_for_user`)
— a claim that exists but belongs to someone else is indistinguishable from
one that doesn't exist at all, so both resolve to the same 404. This is a
deliberate non-leaking policy: confirming "that claim exists, but isn't
yours" would itself hand an attacker information they shouldn't have.
"""

from __future__ import annotations

import io
import logging
import time

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.core.security import get_current_user
from app.db.models.user import UserRecord
from app.db.notification_repository import NotificationRepository
from app.db.policy_repository import PolicyDocumentRepository
from app.db.repository import ClaimRepository
from app.db.review_repository import ReviewItemRepository
from app.db.session import get_db
from app.db.vehicle_reference_repository import VehicleReferenceImageRepository
from app.graph.orchestrator import run_claim_workflow
from app.observability.context import bind_claim_id
from app.schemas.claim_api import ClaimCreateRequest, ClaimResponse
from app.schemas.dashboard_api import ClaimListItem, ClaimListResponse
from app.services import claim_service
from app.services.notifications import service as notification_service
from app.services.ai_client import (
    AIServiceClient,
    AIServiceInvalidResponse,
    AIServiceTimeout,
    AIServiceUnavailable,
    AIServiceValidationRejected,
)
from app.services.vehicle_reference import resolve_vehicle_reference_image

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/claims", tags=["claims"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGES_PER_ANALYZE = 10
# Generous for a phone photo, small next to a deliberately oversized upload.
MAX_IMAGE_BYTES = 10 * 1024 * 1024


def get_ai_service_client() -> AIServiceClient:
    return AIServiceClient()


def _rejected(status_code: int, error_code: str, message: str, invalid_filenames: list[str]) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error_code": error_code, "message": message, "invalid_filenames": invalid_filenames},
    )


@router.post("", response_model=ClaimResponse, status_code=201)
@limiter.limit("20/minute")
async def create_claim(
    request: Request,
    payload: ClaimCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user),
) -> ClaimResponse:
    repo = ClaimRepository(db)
    record = await claim_service.create_claim(
        repo,
        vehicle_type=payload.vehicle_type.value,
        vehicle_make=payload.vehicle_make,
        vehicle_model=payload.vehicle_model,
        vehicle_variant=payload.vehicle_variant,
        vehicle_year=payload.vehicle_year,
        user_id=current_user.id,
        incident_date=payload.incident_date,
    )
    return ClaimResponse.from_record(record)


@router.get("", response_model=ClaimListResponse)
async def list_claims(
    db: AsyncSession = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ClaimListResponse:
    """Newest-first claim history for the authenticated caller only —
    `list_for_user` scopes the query to `current_user.id`, never an
    arbitrary client-supplied user id."""
    repo = ClaimRepository(db)
    reference_repo = VehicleReferenceImageRepository(db)
    policy_repo = PolicyDocumentRepository(db)
    records = await repo.list_for_user(current_user.id, limit=limit, offset=offset)

    items = []
    for record in records:
        reference_image = None
        if record.vehicle_make and record.vehicle_model:
            reference_image = await resolve_vehicle_reference_image(
                reference_repo,
                make=record.vehicle_make,
                model=record.vehicle_model,
                year=record.vehicle_year,
                vehicle_type=record.vehicle_type,
            )
        policy_document = await policy_repo.get_by_claim_id(record.id)
        items.append(ClaimListItem.from_record(record, reference_image, policy_document))

    return ClaimListResponse(items=items)


@router.post("/{claim_id}/analyze", response_model=ClaimResponse)
@limiter.limit("10/minute")
async def analyze_claim(
    request: Request,
    claim_id: str,
    images: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user),
    ai_client: AIServiceClient = Depends(get_ai_service_client),
) -> ClaimResponse:
    # Whole-route claim binding + timing: every log line emitted while
    # handling this analyze call (including deep inside claim_service and
    # the ai_client's timed_operation line) carries claim=<id>, and the
    # route's own total is logged even though the middleware also times the
    # request — the two together distinguish "handler was slow" from
    # "response never left the box".
    request_start = time.perf_counter()
    with bind_claim_id(claim_id):
        logger.info("analyze_request_received images=%d", len(images))

        if not images:
            raise _rejected(422, "unsupported_file_type", "At least one image is required.", [])

        if len(images) > MAX_IMAGES_PER_ANALYZE:
            raise _rejected(
                422,
                "too_many_files",
                f"Maximum {MAX_IMAGES_PER_ANALYZE} images allowed per claim.",
                [],
            )

        payload_images: list[tuple[str, bytes, str]] = []
        corrupted_filenames: list[str] = []

        for image in images:
            filename = image.filename or "upload.jpg"

            # Never trust the extension or client-supplied content_type alone
            # for MIME — this at least restricts it to the declared allow-list
            # before any bytes are read; the Pillow decode below is what
            # actually proves the bytes are a real image of that kind.
            if image.content_type not in ALLOWED_CONTENT_TYPES:
                raise _rejected(422, "unsupported_file_type", f"{filename}: unsupported file type.", [filename])

            content = await image.read()
            if len(content) > MAX_IMAGE_BYTES:
                raise _rejected(
                    422,
                    "file_too_large",
                    f"{filename}: exceeds the {MAX_IMAGE_BYTES // (1024 * 1024)}MB limit.",
                    [filename],
                )

            try:
                with Image.open(io.BytesIO(content)) as img:
                    img.verify()
            except (UnidentifiedImageError, OSError, ValueError):
                # Collected across the whole batch, like the ai-service's
                # vehicle-presence check — the caller learns about every bad
                # file in one response, never silently dropped or fixed one
                # at a time across repeated submissions.
                corrupted_filenames.append(filename)
                continue

            payload_images.append((filename, content, image.content_type))

        if corrupted_filenames:
            raise _rejected(422, "corrupted_image", "One or more images could not be read.", corrupted_filenames)

        repo = ClaimRepository(db)

        try:
            record, reused_existing_result = await claim_service.analyze_claim(
                repo,
                ai_client,
                claim_id=claim_id,
                images=payload_images,
                user_id=current_user.id,
            )
        except claim_service.ClaimNotFoundError:
            raise HTTPException(status_code=404, detail="Claim not found.")
        except AIServiceValidationRejected as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "error_code": exc.error_code,
                    "message": str(exc),
                    "invalid_filenames": exc.invalid_filenames,
                },
            )
        except AIServiceTimeout:
            raise HTTPException(status_code=504, detail="AI service timed out. Please try again.")
        except AIServiceUnavailable:
            raise HTTPException(status_code=503, detail="AI service is currently unavailable.")
        except AIServiceInvalidResponse:
            logger.exception("AI service returned a malformed response for claim %s", claim_id)
            raise HTTPException(
                status_code=502, detail="AI service returned an invalid response."
            )

        # A retry that matched an already-completed assessment (byte-identical
        # images) changed nothing, so the workflow below already ran for it —
        # running it again would only re-do coverage/risk/report work and emit
        # duplicate "analysis completed" notifications for the same claim.
        if reused_existing_result:
            logger.info(
                "analyze_response_returned reused=1 status=%s total_analyze_duration_ms=%d",
                record.status,
                int((time.perf_counter() - request_start) * 1000),
            )
            return ClaimResponse.from_record(record)

        # Continue the workflow (policy retrieval/coverage/risk/report — Task 5)
        # now that damage assessment + pricing are persisted. Deliberately
        # isolated in its own try/except: a bug here must never turn an
        # otherwise-successful analysis into a failed response — the existing,
        # tested damage assessment + pricing result always wins.
        logger.info("post_analysis_workflow_started")
        workflow_start = time.perf_counter()
        try:
            policy_repo = PolicyDocumentRepository(db)
            review_repo = ReviewItemRepository(db)
            record = await run_claim_workflow(repo, policy_repo, review_repo, ai_client, record)

            if current_user.id is not None:
                notif_repo = NotificationRepository(db)
                await notification_service.notify_claim_analysis_completed(
                    notif_repo, user_id=current_user.id, claim_id=record.id, claim_public_id=record.claim_id
                )
                if record.status == "review_required":
                    await notification_service.notify_claim_review_required(
                        notif_repo, user_id=current_user.id, claim_id=record.id, claim_public_id=record.claim_id
                    )
            logger.info(
                "post_analysis_workflow_completed duration_ms=%d",
                int((time.perf_counter() - workflow_start) * 1000),
            )
        except Exception:
            logger.exception("Post-analysis workflow (coverage/risk/report) failed for claim %s", claim_id)
            logger.warning(
                "post_analysis_workflow_failed duration_ms=%d",
                int((time.perf_counter() - workflow_start) * 1000),
            )

        logger.info(
            "analyze_response_returned reused=0 status=%s total_analyze_duration_ms=%d",
            record.status,
            int((time.perf_counter() - request_start) * 1000),
        )
        return ClaimResponse.from_record(record)


@router.get("/{claim_id}", response_model=ClaimResponse)
async def get_claim(
    claim_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user),
) -> ClaimResponse:
    repo = ClaimRepository(db)
    record = await repo.get_by_claim_id_for_user(claim_id, current_user.id)
    if record is None:
        raise HTTPException(status_code=404, detail="Claim not found.")

    reference_image = None
    if record.vehicle_make and record.vehicle_model:
        reference_image = await resolve_vehicle_reference_image(
            VehicleReferenceImageRepository(db),
            make=record.vehicle_make,
            model=record.vehicle_model,
            year=record.vehicle_year,
            vehicle_type=record.vehicle_type,
        )
    return ClaimResponse.from_record(record, reference_image)
