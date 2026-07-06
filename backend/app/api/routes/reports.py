"""Unified claim report, timeline, and PDF export endpoints (Tasks 6/7/11).

Deliberately read-only and cheap: these render from whatever is already
persisted on `ClaimRecord`/`PolicyDocumentRecord` (set by `analyze_claim`
and `upload_policy`, which are the two points that actually invoke the
LangGraph workflow — see those routes). Polling one of these endpoints
never re-runs retrieval, the risk engine, or any inference.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.models.user import UserRecord
from app.db.policy_repository import PolicyDocumentRepository
from app.db.repository import ClaimRepository
from app.db.session import get_db
from app.db.vehicle_reference_repository import VehicleReferenceImageRepository
from app.schemas.policy_state import TimelineStage, UnifiedClaimReport
from app.services.report.pdf_export import generate_claim_report_pdf
from app.services.report.report_service import build_unified_report
from app.services.report.timeline_service import build_timeline
from app.services.vehicle_reference import resolve_vehicle_reference_image

router = APIRouter(prefix="/claims", tags=["reports"])


async def _load_claim_and_policy(claim_id: str, db: AsyncSession, current_user: UserRecord):
    claim_repo = ClaimRepository(db)
    claim = await claim_repo.get_by_claim_id_for_user(claim_id, current_user.id)
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found.")

    policy_repo = PolicyDocumentRepository(db)
    policy_doc = await policy_repo.get_by_claim_id(claim.id)
    return claim, policy_doc


async def _build_report(claim, policy_doc, db: AsyncSession) -> UnifiedClaimReport:
    reference_image_url = None
    if claim.vehicle_make and claim.vehicle_model:
        reference_repo = VehicleReferenceImageRepository(db)
        reference = await resolve_vehicle_reference_image(
            reference_repo,
            make=claim.vehicle_make,
            model=claim.vehicle_model,
            year=claim.vehicle_year,
            vehicle_type=claim.vehicle_type,
        )
        reference_image_url = reference.image_url if reference else None

    return build_unified_report(
        claim_id=claim.claim_id,
        vehicle_type=claim.vehicle_type,
        vehicle_make=claim.vehicle_make,
        vehicle_model=claim.vehicle_model,
        vehicle_variant=claim.vehicle_variant,
        vehicle_year=claim.vehicle_year,
        reference_image_url=reference_image_url,
        ai_assessment=claim.ai_assessment,
        pricing_assessment=claim.pricing_assessment,
        policy_status=policy_doc.status if policy_doc else None,
        policy_structured_data=policy_doc.structured_data if policy_doc else None,
        coverage_analysis=claim.coverage_analysis,
        risk_assessment=claim.risk_assessment or {"risk_level": "insufficient_data", "signals": []},
    )


@router.get("/{claim_id}/report", response_model=UnifiedClaimReport)
async def get_claim_report(
    claim_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user),
) -> UnifiedClaimReport:
    claim, policy_doc = await _load_claim_and_policy(claim_id, db, current_user)
    return await _build_report(claim, policy_doc, db)


@router.get("/{claim_id}/timeline")
async def get_claim_timeline(
    claim_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user),
) -> dict:
    claim, policy_doc = await _load_claim_and_policy(claim_id, db, current_user)
    stages = build_timeline(claim, policy_doc)
    return {"stages": [s.model_dump(mode="json") for s in stages]}


@router.get("/{claim_id}/report/pdf")
async def get_claim_report_pdf(
    claim_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user),
) -> Response:
    claim, policy_doc = await _load_claim_and_policy(claim_id, db, current_user)
    report = await _build_report(claim, policy_doc, db)
    timeline: list[TimelineStage] = build_timeline(claim, policy_doc)

    pdf_bytes = generate_claim_report_pdf(
        report,
        timeline,
        claim_status=claim.status,
        ai_assessment=claim.ai_assessment,
        pricing_assessment=claim.pricing_assessment,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{claim.claim_id}-report.pdf"'},
    )
