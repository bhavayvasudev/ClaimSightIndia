"""Persisted claim record for the current create -> analyze -> retrieve
flow.

Normalized columns vs JSONB — deliberate split, not an accident:
  * `vehicle_type`/`vehicle_make`/`vehicle_model`/`vehicle_year` and
    `status` are normalized columns. They're fixed-shape, always present
    (or simple optionals) straight from intake, and are exactly what a
    claims dashboard would filter/sort/index on (e.g. "all SUV claims
    pending review"). Normalizing costs nothing here and buys queryability.
  * `ai_assessment` (the merged ai-service output) and `pricing_assessment`
    (the `ClaimCostSummary` rollup) are JSONB. Both are nested,
    variable-length structures (a list of parts, each with its own nested
    cost estimate) that already have a tested Pydantic contract
    (`PartDamageAssessment`, `ClaimCostSummary` in `app/schemas/claim_state.py`).
    Splitting them into a `claim_parts` table now would be relational
    complexity this MVP doesn't need yet — nothing queries "all claims
    with a damaged bumper" today. Revisit if/when that becomes a real
    requirement.

No `registration_number` column: the current intake flow
(`ClaimIntakeInput`) never collects one — it's OCR-derived by the
not-yet-built Vehicle Verification agent. Adding it now would be a column
nothing writes to.
"""

import enum
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ClaimRecordStatus(str, enum.Enum):
    """Lifecycle of the currently-implemented create -> analyze -> retrieve
    flow. Deliberately separate from `claim_state.ClaimStatus`, which
    tracks the (not-yet-wired-up) full LangGraph supervisor's pipeline
    stages — the two will likely converge once the graph is live, but
    conflating them now would force this simple flow through stages
    (policy_lookup, fraud_check, ...) it doesn't perform yet."""

    INTAKE = "intake"
    ANALYZING = "analyzing"
    ANALYSIS_COMPLETE = "analysis_complete"
    REVIEW_REQUIRED = "review_required"
    FAILED = "failed"


def _jsonb_or_json() -> JSON:
    # Postgres gets real JSONB; any other dialect (SQLite in tests) falls
    # back to SQLAlchemy's generic JSON so persistence tests don't need a
    # live Postgres instance.
    return JSON().with_variant(JSONB(), "postgresql")


class ClaimRecord(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claim_id: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)

    vehicle_type: Mapped[str] = mapped_column(String(32), nullable=False)
    vehicle_make: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vehicle_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vehicle_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Optional trim/variant name (e.g. "Blackstorm" for an MG Astor) picked
    # from `app/services/vehicle_catalog.py`'s per-model variant list — see
    # that module's docstring. Always None for claims created before this
    # column existed; nothing treats it as required.
    vehicle_variant: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Optional, claimant-submitted at intake. Only present when the
    # frontend collects it — absent for older claims. The risk engine's
    # POLICY_DATE_INCONSISTENCY check is skipped entirely (never invented)
    # when this is None; see app/services/risk/risk_engine.py.
    incident_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Nullable: pre-auth claims (and today's unauthenticated test-suite
    # requests) have no owner. New claims from the real, signed-in flow
    # always populate this from the frontend's session-derived user id.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ClaimRecordStatus.INTAKE.value
    )

    ai_assessment: Mapped[dict | None] = mapped_column(_jsonb_or_json(), nullable=True)
    pricing_assessment: Mapped[dict | None] = mapped_column(_jsonb_or_json(), nullable=True)

    # Per-image sha256 hashes computed at analyze time (never the image
    # bytes themselves) — the only input the risk engine's exact-duplicate
    # signal needs (app/services/risk/risk_engine.py). Cheap to store,
    # avoids persisting actual claim photos anywhere.
    image_hashes: Mapped[dict | None] = mapped_column(_jsonb_or_json(), nullable=True)

    # CoverageAnalysisResult (app/schemas/policy_state.py) — None until a
    # processed policy + a completed damage assessment both exist.
    coverage_analysis: Mapped[dict | None] = mapped_column(_jsonb_or_json(), nullable=True)
    # RiskAssessment (app/schemas/policy_state.py) — computed from whatever
    # evidence currently exists; never None once the workflow has run at
    # least once, since the risk engine always produces at least an
    # "insufficient_data" result rather than skipping.
    risk_assessment: Mapped[dict | None] = mapped_column(_jsonb_or_json(), nullable=True)

    report_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
