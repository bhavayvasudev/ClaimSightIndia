"""
Central shared state for the ClaimSight India LangGraph supervisor graph.

Every agent node reads from and writes to a single `ClaimState` instance.
Nodes never invent their own local state shape — they read the fields they
need off `ClaimState` and return a partial update (a dict of the fields they
changed). LangGraph merges that partial update back into the state.

Design rules baked into this file:

1. Every per-agent output is `Optional` and defaults to `None`. A node that
   fails (bad OCR, LLM timeout, malformed PDF) must not crash the graph —
   it should record an `AgentError` and leave its own output field `None`.
   The Report Agent and the API layer are responsible for rendering
   "insufficient data" gracefully instead of crashing on a `None`.
2. Money is stored as whole-rupee `int`, never `float` or `str`. Floats lose
   precision on arithmetic (deductible math, payout math) and strings can't
   be computed on. Display strings (e.g. "₹30,000 - ₹45,000") are derived
   on demand via `format_inr()` / model properties, never stored twice.
3. `agent_runs` and `errors` are LangGraph "fan-in" fields: multiple nodes
   can run concurrently (e.g. Vehicle Verification + Policy Agent + Vision
   Agent all read independent inputs and can execute in parallel) and each
   appends its own record. They use the `operator.add` reducer so concurrent
   writes accumulate instead of overwriting each other. Every other field
   is single-writer (exactly one node ever sets it), so it uses LangGraph's
   default "last write wins" merge behavior.
4. This file is intentionally the *only* place ClaimState-related Pydantic
   models live. Splitting VehicleDetails/PolicyDetails/etc. into separate
   files would mirror the agent boundaries, but for a solo one-month build
   the win isn't worth the import overhead — split it later only if this
   file becomes unwieldy.
"""

from __future__ import annotations

import operator
import re
import uuid
from datetime import date, datetime, timezone
from enum import Enum
from typing import Annotated, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Enums — fixed vocabularies shared by every agent and by the XGBoost model
# ---------------------------------------------------------------------------


class ClaimStatus(str, Enum):
    """Pipeline stage. The supervisor's conditional edges route on this."""

    INTAKE = "intake"
    VEHICLE_VERIFICATION = "vehicle_verification"
    POLICY_LOOKUP = "policy_lookup"
    VISION_ANALYSIS = "vision_analysis"
    COST_ESTIMATION = "cost_estimation"
    FRAUD_CHECK = "fraud_check"
    AWAITING_HUMAN_REVIEW = "awaiting_human_review"
    REPORT_GENERATION = "report_generation"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentName(str, Enum):
    SUPERVISOR = "supervisor"
    VEHICLE_VERIFICATION = "vehicle_verification_agent"
    POLICY = "policy_agent"
    VISION = "vision_agent"
    COST_ESTIMATION = "cost_estimation_agent"
    FRAUD_DETECTION = "fraud_detection_agent"
    REPORT = "report_agent"
    HUMAN_REVIEW = "human_review"


class AgentRunStatus(str, Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class SeverityLevel(str, Enum):
    """Values match the exact display strings so `.value` prints correctly
    in the report without a separate lookup table."""

    MINOR = "Minor"
    MODERATE = "Moderate"
    SEVERE = "Severe"
    TOTAL_LOSS = "Total Loss"


# Ordering for "worst damage wins" aggregation — not the enum's declaration
# order, so keep this explicit rather than relying on Enum iteration order.
_SEVERITY_RANK = {
    SeverityLevel.MINOR: 0,
    SeverityLevel.MODERATE: 1,
    SeverityLevel.SEVERE: 2,
    SeverityLevel.TOTAL_LOSS: 3,
}


class DamageType(str, Enum):
    """Fixed taxonomy. The Vision Agent must map whatever the HF model
    outputs onto one of these — an open vocabulary would make DamageType
    useless as an XGBoost categorical feature for cost estimation."""

    DENT = "Dent"
    SCRATCH = "Scratch"
    BROKEN_WINDSHIELD = "Broken Windshield"
    BUMPER_DAMAGE = "Bumper Damage"
    FLOOD_DAMAGE = "Flood Damage"
    OTHER = "Other"


class PolicyType(str, Enum):
    THIRD_PARTY = "Third-Party"
    COMPREHENSIVE = "Comprehensive"
    STANDALONE_OD = "Standalone Own-Damage"


class FraudRisk(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class ReviewStatus(str, Enum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


# ---------------------------------------------------------------------------
# Small formatting helper — Indian digit grouping (lakh/crore), not Western
# thousands grouping. "₹1234567" should render "₹12,34,567", not "₹1,234,567".
# ---------------------------------------------------------------------------


def format_inr(amount: int) -> str:
    sign = "-" if amount < 0 else ""
    s = str(abs(amount))
    if len(s) <= 3:
        grouped = s
    else:
        last3, rest = s[-3:], s[:-3]
        parts: list[str] = []
        while len(rest) > 2:
            parts.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            parts.insert(0, rest)
        grouped = ",".join(parts) + "," + last3
    return f"{sign}₹{grouped}"


# ---------------------------------------------------------------------------
# Intake — what the API layer hands to the graph to seed a new ClaimState
# ---------------------------------------------------------------------------


class ClaimIntakeInput(BaseModel):
    """Raw inputs as submitted through the FastAPI upload endpoints. Files
    are referenced by storage id (already persisted by `services/storage.py`)
    rather than embedded as bytes — keeps ClaimState small and serializable
    for Langfuse tracing and checkpointing."""

    model_config = ConfigDict(extra="forbid")

    vehicle_image_id: str = Field(description="Storage id of the number-plate photo")
    damage_image_ids: List[str] = Field(
        default_factory=list, description="Storage ids of the vehicle damage photos"
    )
    policy_pdf_id: str = Field(description="Storage id of the uploaded policy PDF")
    incident_description: str = Field(
        min_length=1, description="Free-text accident description from the claimant"
    )
    incident_date: Optional[date] = None
    incident_location: Optional[str] = Field(
        default=None, description="Free-text location, used for the weather cross-check"
    )
    policyholder_name: Optional[str] = None


# ---------------------------------------------------------------------------
# Vehicle Verification Agent output
# ---------------------------------------------------------------------------

# Subset of RTO state codes. Extend as real claims surface new prefixes —
# an incomplete map degrades to `state=None`, it never raises.
_RTO_STATE_CODES: dict[str, str] = {
    "AP": "Andhra Pradesh", "AR": "Arunachal Pradesh", "AS": "Assam",
    "BR": "Bihar", "CG": "Chhattisgarh", "GA": "Goa", "GJ": "Gujarat",
    "HR": "Haryana", "HP": "Himachal Pradesh", "JH": "Jharkhand",
    "KA": "Karnataka", "KL": "Kerala", "MP": "Madhya Pradesh",
    "MH": "Maharashtra", "MN": "Manipur", "ML": "Meghalaya", "MZ": "Mizoram",
    "NL": "Nagaland", "OD": "Odisha", "PB": "Punjab", "RJ": "Rajasthan",
    "SK": "Sikkim", "TN": "Tamil Nadu", "TS": "Telangana", "TR": "Tripura",
    "UP": "Uttar Pradesh", "UK": "Uttarakhand", "WB": "West Bengal",
    "DL": "Delhi", "JK": "Jammu and Kashmir", "LA": "Ladakh",
    "CH": "Chandigarh", "PY": "Puducherry",
}

_REG_NUMBER_RE = re.compile(r"^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}$")
_BH_SERIES_RE = re.compile(r"^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$")


class VehicleDetails(BaseModel):
    registration_number: Optional[str] = Field(
        default=None, description="Normalized plate, e.g. MH12AB1234"
    )
    state: Optional[str] = Field(default=None, description="Derived from the plate prefix")
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    manufacture_year: Optional[int] = Field(
        default=None, description="Used to compute vehicle age for the cost model"
    )
    ocr_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    raw_ocr_text: Optional[str] = None

    @field_validator("registration_number")
    @classmethod
    def _normalize_registration(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        normalized = re.sub(r"[\s\-]", "", v).upper()
        if not (_REG_NUMBER_RE.match(normalized) or _BH_SERIES_RE.match(normalized)):
            # Don't raise — OCR output on a damaged/blurry plate is often
            # malformed. Keep the raw value for a human to review rather
            # than failing the whole agent.
            return normalized
        return normalized

    @property
    def vehicle_age_years(self) -> Optional[int]:
        if self.manufacture_year is None:
            return None
        return max(datetime.now(timezone.utc).year - self.manufacture_year, 0)

    @model_validator(mode="after")
    def _derive_state(self) -> "VehicleDetails":
        if self.state is None and self.registration_number and len(self.registration_number) >= 2:
            prefix = self.registration_number[:2]
            self.state = _RTO_STATE_CODES.get(prefix)
        return self


# ---------------------------------------------------------------------------
# Policy Agent output (RAG over the uploaded policy PDF)
# ---------------------------------------------------------------------------


class PolicyDetails(BaseModel):
    covered: bool = Field(description="Whether this incident type is covered at all")
    policy_type: Optional[PolicyType] = None
    idv_inr: Optional[int] = Field(default=None, description="Insured Declared Value, whole rupees")
    deductible_inr: Optional[int] = Field(default=None, description="Compulsory + voluntary deductible")
    zero_dep: bool = Field(default=False, description="Zero-depreciation add-on present")
    exclusions: List[str] = Field(default_factory=list)
    coverage_notes: Optional[str] = Field(
        default=None, description="Short justification, e.g. which clause was matched"
    )
    source_chunks: List[str] = Field(
        default_factory=list, description="Retrieved policy-doc chunk ids used to answer, for citation"
    )

    @property
    def deductible_display(self) -> Optional[str]:
        return None if self.deductible_inr is None else format_inr(self.deductible_inr)

    @property
    def idv_display(self) -> Optional[str]:
        return None if self.idv_inr is None else format_inr(self.idv_inr)


# ---------------------------------------------------------------------------
# Vision Agent output (damage detection over uploaded photos)
# ---------------------------------------------------------------------------


class DamageDetection(BaseModel):
    damage_type: DamageType
    severity: SeverityLevel
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    source_image_id: Optional[str] = None
    bounding_box: Optional[List[float]] = Field(
        default=None, description="[x1, y1, x2, y2] normalized 0-1, if the model provides one"
    )


class VisionAssessment(BaseModel):
    detections: List[DamageDetection] = Field(default_factory=list)
    overall_severity: Optional[SeverityLevel] = None
    damage_summary: Optional[str] = Field(
        default=None, description="Human-readable summary for the report, e.g. 'Windshield crack, hood dents'"
    )

    @model_validator(mode="after")
    def _derive_overall_severity(self) -> "VisionAssessment":
        if self.overall_severity is None and self.detections:
            worst = max(self.detections, key=lambda d: _SEVERITY_RANK[d.severity])
            self.overall_severity = worst.severity
        return self


# ---------------------------------------------------------------------------
# Cost Estimation Agent output (XGBoost regression)
# ---------------------------------------------------------------------------


class CostEstimate(BaseModel):
    low_inr: int = Field(ge=0)
    high_inr: int = Field(ge=0)
    currency: Literal["INR"] = "INR"
    basis: Optional[str] = Field(
        default=None, description="e.g. 'XGBoost v0.3, features: age/type/severity/vehicle_type'"
    )
    model_version: Optional[str] = None

    @model_validator(mode="after")
    def _check_range(self) -> "CostEstimate":
        if self.high_inr < self.low_inr:
            raise ValueError("high_inr must be >= low_inr")
        return self

    @property
    def display_range(self) -> str:
        return f"{format_inr(self.low_inr)} - {format_inr(self.high_inr)}"


# ---------------------------------------------------------------------------
# Fraud Detection Agent output
# ---------------------------------------------------------------------------


class WeatherCheckResult(BaseModel):
    location: str
    checked_date: date
    condition: Optional[str] = None
    matches_claim: Optional[bool] = Field(
        default=None, description="None = inconclusive, e.g. weather API had no data for the date/location"
    )
    source: str = "weather_api"


class FraudAssessment(BaseModel):
    fraud_risk: FraudRisk
    fraud_reasons: List[str] = Field(default_factory=list)
    weather_check: Optional[WeatherCheckResult] = None


# ---------------------------------------------------------------------------
# Report Agent output
# ---------------------------------------------------------------------------


class ClaimTriageReport(BaseModel):
    vehicle_summary: str = Field(description="e.g. 'Hyundai Creta (2022)'")
    detected_damage: List[str] = Field(default_factory=list)
    severity: Optional[SeverityLevel] = None
    coverage_status: str
    estimated_cost_display: str
    fraud_risk: FraudRisk
    recommendation: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_markdown(self) -> str:
        damage_lines = "\n".join(f"* {d}" for d in self.detected_damage) or "* None detected"
        return (
            "MOTOR INSURANCE CLAIM TRIAGE REPORT\n\n"
            f"Vehicle:\n{self.vehicle_summary}\n\n"
            f"Detected Damage:\n{damage_lines}\n\n"
            f"Severity:\n{self.severity.value if self.severity else 'Unknown'}\n\n"
            f"Coverage:\n{self.coverage_status}\n\n"
            f"Estimated Cost:\n{self.estimated_cost_display}\n\n"
            f"Fraud Risk:\n{self.fraud_risk.value}\n\n"
            f"Recommendation:\n{self.recommendation}\n"
        )


# ---------------------------------------------------------------------------
# Cross-cutting: error tracking, execution metrics, human review
# ---------------------------------------------------------------------------


class AgentError(BaseModel):
    agent: AgentName
    message: str
    is_recoverable: bool = Field(
        default=True, description="False means the claim cannot proceed without a human"
    )
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_exception: Optional[str] = None


class AgentRun(BaseModel):
    """One execution record per node invocation. Feeds Langfuse (token
    usage, cost per claim), the evaluation framework (latency, cost
    measurement), and the API layer's per-agent status display."""

    agent: AgentName
    status: AgentRunStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
    langfuse_observation_id: Optional[str] = None

    @property
    def latency_ms(self) -> Optional[int]:
        if self.completed_at is None:
            return None
        return int((self.completed_at - self.started_at).total_seconds() * 1000)


class HumanReviewCheckpoint(BaseModel):
    status: ReviewStatus = ReviewStatus.NOT_REQUIRED
    reason: Optional[str] = Field(
        default=None, description="Why review was triggered, e.g. 'High fraud risk'"
    )
    reviewer_id: Optional[str] = None
    notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# ClaimState — the graph state passed to every LangGraph node
# ---------------------------------------------------------------------------


class ClaimState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    claim_id: str
    status: ClaimStatus = ClaimStatus.INTAKE
    created_at: datetime
    updated_at: datetime

    intake: ClaimIntakeInput

    # Per-agent outputs. Optional + None default: a failed agent leaves its
    # slot empty instead of crashing the graph. See module docstring rule 1.
    vehicle: Optional[VehicleDetails] = None
    policy: Optional[PolicyDetails] = None
    vision: Optional[VisionAssessment] = None
    cost: Optional[CostEstimate] = None
    fraud: Optional[FraudAssessment] = None
    report: Optional[ClaimTriageReport] = None

    human_review: HumanReviewCheckpoint = Field(default_factory=HumanReviewCheckpoint)

    # Fan-in fields: multiple nodes append concurrently, so they use the
    # operator.add reducer instead of last-write-wins. See module docstring
    # rule 3.
    agent_runs: Annotated[List[AgentRun], operator.add] = Field(default_factory=list)
    errors: Annotated[List[AgentError], operator.add] = Field(default_factory=list)

    langfuse_trace_id: Optional[str] = None

    @classmethod
    def new(cls, intake: ClaimIntakeInput) -> "ClaimState":
        now = datetime.now(timezone.utc)
        return cls(
            claim_id=f"CLM-{uuid.uuid4().hex[:12].upper()}",
            created_at=now,
            updated_at=now,
            intake=intake,
        )

    @property
    def total_latency_ms(self) -> int:
        return sum(r.latency_ms or 0 for r in self.agent_runs)

    @property
    def total_cost_usd(self) -> float:
        return sum(r.estimated_cost_usd or 0.0 for r in self.agent_runs)

    @property
    def has_blocking_errors(self) -> bool:
        return any(not e.is_recoverable for e in self.errors)

    @property
    def needs_human_review(self) -> bool:
        """Trigger conditions for the human-review checkpoint. The
        supervisor checks this after the Fraud Detection node before
        routing to Report Generation."""
        if self.has_blocking_errors:
            return True
        if self.fraud and self.fraud.fraud_risk == FraudRisk.HIGH:
            return True
        if self.vision and self.vision.overall_severity == SeverityLevel.TOTAL_LOSS:
            return True
        return False
