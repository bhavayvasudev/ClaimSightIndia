"""Request/response schemas for the claim API routes
(`app/api/routes/claims.py`).

Kept separate from `claim_state.py`, which is the LangGraph supervisor's
internal graph-state contract (see that module's docstring rule 4) — these
are the stable, frontend-facing shapes for the currently-implemented
create -> analyze -> retrieve flow, and are free to evolve independently
of the graph's internal state once the supervisor is wired up.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models.claim import ClaimRecord
from app.db.models.vehicle_reference import VehicleReferenceImageRecord
from app.schemas.claim_state import VehicleCategory
from app.schemas.dashboard_api import VehicleReferenceImage

# A car's manufacture year predates any policy this system prices, and the
# upper bound allows next model-year vehicles that dealers routinely sell
# ahead of the calendar year rolling over.
MIN_VEHICLE_YEAR = 1980


def _max_vehicle_year() -> int:
    return datetime.now(timezone.utc).year + 1


class ClaimCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vehicle_type: VehicleCategory = Field(
        description="Vehicle category, used for category-aware repair-cost pricing"
    )
    # max_length matches the `String(64)` columns in db/models/claim.py —
    # rejecting oversized values here beats a truncated silent mismatch or
    # a DB-level error surfacing later as an opaque 500.
    vehicle_make: str = Field(description="Vehicle manufacturer, e.g. Hyundai", max_length=64)
    vehicle_model: str = Field(description="Vehicle model, e.g. Verna", max_length=64)
    vehicle_variant: Optional[str] = Field(
        default=None,
        description="Optional trim/variant, e.g. Blackstorm — see app/services/vehicle_catalog.py",
        max_length=64,
    )
    vehicle_year: int = Field(description="Manufacture year")
    incident_date: Optional[date] = Field(
        default=None,
        description=(
            "Optional accident/incident date. Powers the risk engine's policy-period "
            "cross-check (app/services/risk/risk_engine.py) — left unset, that check "
            "is simply skipped rather than guessed at."
        ),
    )

    # No user_id field: claim ownership is derived server-side from the
    # authenticated bearer token (see app.core.security.get_current_user),
    # never from a client-supplied value — a client could otherwise claim
    # ownership as any user by just setting a different number.

    @field_validator("vehicle_make", "vehicle_model")
    @classmethod
    def _trim_and_require_nonblank(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("must not be blank")
        return trimmed

    @field_validator("vehicle_variant")
    @classmethod
    def _trim_optional_variant(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @field_validator("vehicle_year")
    @classmethod
    def _validate_year_range(cls, value: int) -> int:
        max_year = _max_vehicle_year()
        if not (MIN_VEHICLE_YEAR <= value <= max_year):
            raise ValueError(f"must be between {MIN_VEHICLE_YEAR} and {max_year}")
        return value

    @field_validator("incident_date")
    @classmethod
    def _validate_incident_date_not_future(cls, value: Optional[date]) -> Optional[date]:
        if value is not None and value > datetime.now(timezone.utc).date():
            raise ValueError("must not be in the future")
        return value


class ClaimResponse(BaseModel):
    id: str = Field(description="Public claim id, e.g. CLM-ABC123DEF456")
    status: str
    vehicle_type: str
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_variant: Optional[str] = None
    vehicle_year: Optional[int] = None
    incident_date: Optional[date] = None
    user_id: Optional[int] = Field(
        default=None, description="Owning user's backend id, if the claim was created while signed in"
    )
    ai_assessment: Optional[dict] = Field(
        default=None, description="Merged ai-service output used for this claim's analysis"
    )
    pricing_assessment: Optional[dict] = Field(
        default=None, description="ClaimCostSummary rollup priced from ai_assessment + vehicle_type"
    )
    coverage_analysis: Optional[dict] = Field(
        default=None, description="CoverageAnalysisResult, once a processed policy + damage assessment exist"
    )
    risk_assessment: Optional[dict] = Field(
        default=None, description="RiskAssessment — present once the claim workflow has run at least once"
    )
    vehicle_reference_image: Optional[VehicleReferenceImage] = Field(
        default=None,
        description=(
            "Generic reference image of this vehicle's make/model/category — never the "
            "claimant's photographed vehicle. See app/services/vehicle_reference.py."
        ),
    )
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(
        cls,
        record: ClaimRecord,
        reference_image: Optional[VehicleReferenceImageRecord] = None,
    ) -> "ClaimResponse":
        return cls(
            id=record.claim_id,
            status=record.status,
            vehicle_type=record.vehicle_type,
            vehicle_make=record.vehicle_make,
            vehicle_model=record.vehicle_model,
            vehicle_variant=record.vehicle_variant,
            vehicle_year=record.vehicle_year,
            incident_date=record.incident_date,
            user_id=record.user_id,
            ai_assessment=record.ai_assessment,
            pricing_assessment=record.pricing_assessment,
            coverage_analysis=record.coverage_analysis,
            risk_assessment=record.risk_assessment,
            vehicle_reference_image=(
                VehicleReferenceImage.from_record(reference_image) if reference_image else None
            ),
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
