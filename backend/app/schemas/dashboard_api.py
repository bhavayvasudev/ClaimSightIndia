"""Response schemas for the authenticated claim-history list
(`GET /claims`, `app/api/routes/claims.py`).

Deliberately a leaner shape than `ClaimResponse` (`app/schemas/claim_api.py`)
— the dashboard renders a grid of cards, not a full assessment detail page,
so this omits the full `ai_assessment`/`pricing_assessment` payloads in
favor of small pre-aggregated summary counts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.db.models.claim import ClaimRecord
from app.db.models.vehicle_reference import VehicleReferenceImageRecord


class VehicleReferenceImage(BaseModel):
    """A generic reference illustration of this vehicle's make/model/category
    — NOT the claimant's photographed vehicle and NOT claim evidence. See
    `app/services/vehicle_reference.py` module docstring."""

    url: str
    source: str
    match_confidence: float

    @classmethod
    def from_record(cls, record: VehicleReferenceImageRecord) -> "VehicleReferenceImage":
        return cls(url=record.image_url, source=record.source, match_confidence=record.match_confidence)


class ClaimSummary(BaseModel):
    damaged_parts: int = Field(default=0, description="Count of damaged parts found, if analysis has run")
    review_required: int = Field(default=0, description="Of damaged_parts, how many need manual review")
    total_min_inr: Optional[int] = Field(
        default=None, description="None until at least one part has a confident priced estimate"
    )
    total_max_inr: Optional[int] = None


class ClaimListItem(BaseModel):
    id: str
    status: str
    vehicle_type: str
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_year: Optional[int] = None
    vehicle_reference_image: Optional[VehicleReferenceImage] = None
    created_at: datetime
    summary: ClaimSummary

    # Restrained dashboard-card indicators (Task 9) — never the full policy
    # summary or every risk signal, just enough to know whether to open the
    # claim for detail. See app/api/routes/claims.py:list_claims.
    has_policy: bool = False
    policy_ready: bool = False
    needs_manual_review: bool = False

    @classmethod
    def from_record(
        cls,
        record: ClaimRecord,
        reference_image: Optional[VehicleReferenceImageRecord],
        policy_document=None,
    ) -> "ClaimListItem":
        damaged_parts = 0
        review_required = 0
        if record.ai_assessment:
            parts = record.ai_assessment.get("damaged_parts") or []
            damaged_parts = len(parts)
            review_required = sum(1 for p in parts if p.get("status") == "Review Required")

        total_min_inr: Optional[int] = None
        total_max_inr: Optional[int] = None
        if record.pricing_assessment and record.pricing_assessment.get("parts_priced"):
            total_min_inr = record.pricing_assessment.get("total_min_inr")
            total_max_inr = record.pricing_assessment.get("total_max_inr")

        needs_manual_review = record.status == "review_required"
        if record.risk_assessment and record.risk_assessment.get("risk_level") in ("medium", "high"):
            needs_manual_review = True
        if record.coverage_analysis and record.coverage_analysis.get("overall_status") in (
            "potential_exclusion",
            "manual_review",
        ):
            needs_manual_review = True

        return cls(
            id=record.claim_id,
            status=record.status,
            vehicle_type=record.vehicle_type,
            vehicle_make=record.vehicle_make,
            vehicle_model=record.vehicle_model,
            vehicle_year=record.vehicle_year,
            vehicle_reference_image=(
                VehicleReferenceImage.from_record(reference_image) if reference_image else None
            ),
            created_at=record.created_at,
            summary=ClaimSummary(
                damaged_parts=damaged_parts,
                review_required=review_required,
                total_min_inr=total_min_inr,
                total_max_inr=total_max_inr,
            ),
            has_policy=policy_document is not None,
            policy_ready=bool(policy_document and policy_document.status == "processed"),
            needs_manual_review=needs_manual_review,
        )


class ClaimListResponse(BaseModel):
    items: list[ClaimListItem]
