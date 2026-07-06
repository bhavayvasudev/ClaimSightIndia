"""Typed contracts for the policy pipeline, RAG retrieval, coverage
analysis, risk signals, and the unified claim report (Tasks 2-6).

Language rules (binding for every field that renders as user-facing text
in this module and everywhere it's consumed):

  * Coverage status is always one of "likely_covered" / "unclear" /
    "potential_exclusion" / "manual_review" — never "approved", "rejected",
    "insurer will pay", or "guaranteed". ClaimSight interprets policy text
    for triage; it is not the insurer's final adjudication.
  * Risk findings are always neutral: "risk signal", "inconsistency
    detected", "manual review recommended", "insufficient data". Never a
    person-directed label ("fraudster", "scammer", "criminal") — see
    `app/services/risk/risk_engine.py` module docstring.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Structured policy extraction (populates PolicyDocumentRecord.structured_data)
# ---------------------------------------------------------------------------


class PolicyType(str, Enum):
    THIRD_PARTY = "Third-Party"
    COMPREHENSIVE = "Comprehensive"
    STANDALONE_OD = "Standalone Own-Damage"


class PolicyStructuredData(BaseModel):
    """Fields pulled from the uploaded policy document. Every field is
    genuinely optional — a field the extractor couldn't find with
    confidence stays `None` rather than being guessed at (see
    `app/services/policy/structured_extraction.py`)."""

    policy_type: Optional[PolicyType] = None
    policy_number: Optional[str] = None
    insurer_name: Optional[str] = None

    coverage_start: Optional[date] = None
    coverage_end: Optional[date] = None

    idv_inr: Optional[int] = Field(default=None, description="Insured Declared Value, whole rupees")
    deductible_inr: Optional[int] = None
    zero_dep: bool = False
    add_ons: List[str] = Field(default_factory=list)
    exclusions: List[str] = Field(default_factory=list)

    # Vehicle metadata as printed on the policy schedule, used for the
    # cross-check both coverage analysis and the risk engine perform
    # against the claim's own claimant-submitted vehicle fields.
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_year: Optional[int] = None
    registration_number: Optional[str] = None

    extraction_method: Optional[str] = Field(
        default=None, description="'llm' or 'heuristic' — see structured_extraction.py"
    )
    fields_found: int = Field(
        default=0, description="Count of non-null fields above, used as a rough confidence signal"
    )


# ---------------------------------------------------------------------------
# RAG retrieval
# ---------------------------------------------------------------------------


class RetrievedClause(BaseModel):
    """One retrieved policy chunk, cited back to its source."""

    page: Optional[int] = None
    section: Optional[str] = None
    excerpt: str
    score: float = Field(description="Cosine similarity to the query, 0-1")


# ---------------------------------------------------------------------------
# Coverage analysis (Task 3)
# ---------------------------------------------------------------------------


class CoverageStatus(str, Enum):
    LIKELY_COVERED = "likely_covered"
    UNCLEAR = "unclear"
    POTENTIAL_EXCLUSION = "potential_exclusion"
    MANUAL_REVIEW = "manual_review"


class VehicleMatchStatus(str, Enum):
    MATCH = "match"
    MISMATCH = "mismatch"
    UNKNOWN = "unknown"


class PartCoverageAssessment(BaseModel):
    part: str
    coverage_status: CoverageStatus
    reason: str
    relevant_clauses: List[RetrievedClause] = Field(default_factory=list)


class CoverageAnalysisResult(BaseModel):
    overall_status: CoverageStatus
    summary: str
    vehicle_match: VehicleMatchStatus = VehicleMatchStatus.UNKNOWN
    part_assessments: List[PartCoverageAssessment] = Field(default_factory=list)
    deductible_inr: Optional[int] = None
    idv_inr: Optional[int] = None
    warnings: List[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Risk signal engine (Task 4)
# ---------------------------------------------------------------------------


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    INSUFFICIENT_DATA = "insufficient_data"


class RiskSignalSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"


class RiskSignalCode(str, Enum):
    VEHICLE_MODEL_MISMATCH = "VEHICLE_MODEL_MISMATCH"
    VEHICLE_REGISTRATION_MISMATCH = "VEHICLE_REGISTRATION_MISMATCH"
    POLICY_DATE_INCONSISTENCY = "POLICY_DATE_INCONSISTENCY"
    DUPLICATE_IMAGE_DETECTED = "DUPLICATE_IMAGE_DETECTED"
    POLICY_CLAIM_IDENTITY_INCONSISTENCY = "POLICY_CLAIM_IDENTITY_INCONSISTENCY"
    INCONSISTENT_VISUAL_ASSESSMENT = "INCONSISTENT_VISUAL_ASSESSMENT"


class RiskSignal(BaseModel):
    code: RiskSignalCode
    severity: RiskSignalSeverity
    description: str


class RiskAssessment(BaseModel):
    risk_level: RiskLevel
    signals: List[RiskSignal] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Unified claim report (Task 6)
# ---------------------------------------------------------------------------


class PolicyAnalysisState(str, Enum):
    NOT_AVAILABLE = "not_available"
    PROCESSING = "processing"
    READY = "ready"
    NEEDS_ATTENTION = "needs_attention"
    FAILED = "failed"


class ReportVehicleInfo(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    variant: Optional[str] = None
    year: Optional[int] = None
    category: str
    reference_image_url: Optional[str] = None


class ReportDamageInfo(BaseModel):
    damaged_parts: int = 0
    accepted: int = 0
    review_required: int = 0
    overall_severity: Optional[str] = None
    recommended_actions: List[str] = Field(default_factory=list)


class ReportPricingInfo(BaseModel):
    total_min_inr: Optional[int] = None
    total_max_inr: Optional[int] = None
    parts_priced: int = 0
    parts_pending_manual_inspection: int = 0


class ReportPolicyInfo(BaseModel):
    state: PolicyAnalysisState
    coverage: Optional[CoverageAnalysisResult] = None
    deductible_inr: Optional[int] = None
    idv_inr: Optional[int] = None
    exclusions: List[str] = Field(default_factory=list)

    # Structured extraction fields (Task 3 — surfaced from
    # `PolicyDocumentRecord.structured_data`, never invented; each stays
    # `None`/absent if the extractor didn't find it). `policy_number` is
    # masked here — this is the claim-report view, the same surface a
    # shared/exported report could reach, so the full number never appears
    # in it even though the claimant's own upload response has it.
    policy_type: Optional[PolicyType] = None
    insurer_name: Optional[str] = None
    policy_number_masked: Optional[str] = None
    coverage_start: Optional[date] = None
    coverage_end: Optional[date] = None
    policy_vehicle_make: Optional[str] = None
    policy_vehicle_model: Optional[str] = None
    policy_vehicle_year: Optional[int] = None


class UnifiedClaimReport(BaseModel):
    claim_id: str
    vehicle: ReportVehicleInfo
    damage: ReportDamageInfo
    pricing: ReportPricingInfo
    policy: ReportPolicyInfo
    risk: RiskAssessment
    summary: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Claim timeline (Task 7)
# ---------------------------------------------------------------------------


class TimelineStageStatus(str, Enum):
    COMPLETE = "complete"
    IN_PROGRESS = "in_progress"
    NOT_STARTED = "not_started"
    NOT_AVAILABLE = "not_available"
    NEEDS_ATTENTION = "needs_attention"


class TimelineStage(BaseModel):
    key: str
    label: str
    status: TimelineStageStatus
    detail: Optional[str] = None
    occurred_at: Optional[datetime] = None
