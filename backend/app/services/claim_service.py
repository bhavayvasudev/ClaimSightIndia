"""Orchestrates the claim-analysis flow: intake -> analyze -> price -> store.

Deliberately framework-free (no FastAPI imports) so it's testable and
reusable independent of the route layer. Routes (`app/api/routes/claims.py`)
stay thin request/response mapping over these two functions.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import List

from pydantic import ValidationError

from app.db.models.claim import ClaimRecord, ClaimRecordStatus
from app.db.repository import ClaimRepository
from app.schemas.claim_state import (
    PartAssessmentStatus,
    PartDamageAssessment,
    VisionAssessment,
    generate_claim_id,
)
from app.services.ai_client import AIServiceClient, AIServiceError, AIServiceInvalidResponse, ImagePayload
from app.services.cost_model import summarize_claim_costs


logger = logging.getLogger(__name__)


class ClaimNotFoundError(Exception):
    """Raised when a claim_id doesn't match any persisted claim."""


def _parse_damaged_parts(claim_analysis: object) -> List[PartDamageAssessment]:
    """Validates the ai-service's `claim_analysis` object against our
    schema. Anything that doesn't match raises `AIServiceInvalidResponse`
    — the boundary the route layer maps to a clean 502, never a raw
    traceback."""

    if not isinstance(claim_analysis, dict):
        raise AIServiceInvalidResponse("claim_analysis was not an object")

    raw_parts = claim_analysis.get("damaged_parts")
    if not isinstance(raw_parts, list):
        raise AIServiceInvalidResponse("claim_analysis.damaged_parts was not a list")

    try:
        return [PartDamageAssessment.model_validate(p) for p in raw_parts]
    except ValidationError as exc:
        raise AIServiceInvalidResponse(
            "a damaged_parts entry failed schema validation"
        ) from exc


async def create_claim(
    repo: ClaimRepository,
    *,
    vehicle_type: str,
    vehicle_make: str | None,
    vehicle_model: str | None,
    vehicle_year: int | None,
    vehicle_variant: str | None = None,
    user_id: int | None = None,
    incident_date=None,
) -> ClaimRecord:
    return await repo.create(
        claim_id=generate_claim_id(),
        vehicle_type=vehicle_type,
        vehicle_make=vehicle_make,
        vehicle_model=vehicle_model,
        vehicle_variant=vehicle_variant,
        vehicle_year=vehicle_year,
        user_id=user_id,
        incident_date=incident_date,
    )


#: Statuses that carry a completed, priced assessment — the only states an
#: idempotent re-analyze may short-circuit to (see `analyze_claim`).
_COMPLETED_STATUSES = frozenset(
    {ClaimRecordStatus.ANALYSIS_COMPLETE.value, ClaimRecordStatus.REVIEW_REQUIRED.value}
)


async def analyze_claim(
    repo: ClaimRepository,
    ai_client: AIServiceClient,
    *,
    claim_id: str,
    images: List[ImagePayload],
    user_id: int,
) -> tuple[ClaimRecord, bool]:
    """Runs the full analyze step for an existing claim: sets status to
    `analyzing`, calls the ai-service, prices the merged assessment, and
    stores both the exact AI assessment used for pricing and the pricing
    result. Leaves the claim `failed` (never partially updated) if the
    ai-service call or response validation fails.

    Returns `(record, reused_existing_result)`. Idempotent for retries: a
    claim that already holds a completed assessment for byte-identical
    images (matched via the stored sha256 `image_hashes`) is returned
    as-is with `reused_existing_result=True` — no second inference run, no
    re-priced or re-written rows. This is what makes the frontend's
    retry-after-timeout safe: the first attempt may have committed
    server-side even though the browser never saw the response.

    Ownership-aware by construction: `get_by_claim_id_for_user` returns
    None both for a nonexistent claim_id and for one owned by a different
    user, so a caller can never distinguish "not found" from "not yours".
    """

    record = await repo.get_by_claim_id_for_user(claim_id, user_id)
    if record is None:
        raise ClaimNotFoundError(claim_id)

    submitted_hashes = [hashlib.sha256(content).hexdigest() for _, content, _ in images]
    if (
        record.status in _COMPLETED_STATUSES
        and record.ai_assessment is not None
        and record.image_hashes == submitted_hashes
    ):
        logger.info("analyze_reused_existing_result status=%s", record.status)
        return record, True

    record.status = ClaimRecordStatus.ANALYZING.value
    status_write_start = time.perf_counter()
    record = await repo.save(record)
    logger.info(
        "claim_status_analyzing duration_ms=%d",
        int((time.perf_counter() - status_write_start) * 1000),
    )

    logger.info("ai_request_started images=%d", len(images))
    ai_start = time.perf_counter()
    try:
        raw_response = await ai_client.analyze_claim(images)
        logger.info(
            "ai_request_completed ai_request_duration_ms=%d",
            int((time.perf_counter() - ai_start) * 1000),
        )
        claim_analysis = raw_response["claim_analysis"]
        damaged_parts = _parse_damaged_parts(claim_analysis)
    except AIServiceError as exc:
        logger.warning(
            "ai_request_failed_or_timed_out ai_request_duration_ms=%d error=%s",
            int((time.perf_counter() - ai_start) * 1000),
            type(exc).__name__,
        )
        record.status = ClaimRecordStatus.FAILED.value
        await repo.save(record)
        logger.info("claim_terminal_status_set status=%s", record.status)
        raise

    vision = VisionAssessment(damaged_parts=damaged_parts)
    cost_summary = summarize_claim_costs(
        vehicle_type=record.vehicle_type, damaged_parts=vision.damaged_parts
    )

    # Preserve Review Required results — a claim is only analysis_complete
    # if every part was confidently accepted. Any part still needing a
    # human look keeps the whole claim in review_required, never silently
    # downgraded to complete.
    any_review_required = any(
        part.status == PartAssessmentStatus.REVIEW_REQUIRED for part in vision.damaged_parts
    )
    record.status = (
        ClaimRecordStatus.REVIEW_REQUIRED.value
        if any_review_required
        else ClaimRecordStatus.ANALYSIS_COMPLETE.value
    )

    # Store the exact merged AI assessment that was priced, not a
    # re-derived copy — `claim_analysis` as received, verbatim.
    record.ai_assessment = claim_analysis
    record.pricing_assessment = cost_summary.model_dump(mode="json")

    # sha256 of each submitted image's bytes (never the bytes themselves)
    # — the only input the risk engine's exact-duplicate-image signal
    # needs (app/services/risk/risk_engine.py), and the key the
    # idempotency short-circuit above matches retries against.
    record.image_hashes = submitted_hashes

    logger.info("analysis_persistence_started")
    commit_start = time.perf_counter()
    record = await repo.save(record)
    logger.info(
        "analysis_db_commit_completed duration_ms=%d",
        int((time.perf_counter() - commit_start) * 1000),
    )
    logger.info("claim_terminal_status_set status=%s", record.status)
    return record, False
