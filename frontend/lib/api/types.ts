/**
 * Types for the application-backend claim API.
 *
 * Mirrors `backend/app/schemas/claim_api.py` (`ClaimCreateRequest`,
 * `ClaimResponse`) plus the nested shapes that actually flow through
 * `ai_assessment`/`pricing_assessment`, sourced from
 * `backend/app/schemas/claim_state.py` (`PartDamageAssessment`,
 * `ClaimCostSummary`, `PartCostEstimate`) and `backend/app/db/models/claim.py`
 * (`ClaimRecordStatus`).
 *
 * NOTE: in the actual generated OpenAPI schema, `ClaimResponse.ai_assessment`
 * and `.pricing_assessment` are typed as opaque `object | null`
 * (`additionalProperties: true`) — FastAPI can't derive their nested shape
 * because the route returns them as plain `dict`, not the Pydantic models
 * above. The types below are hand-mirrored from those Pydantic models
 * (verified against a live `/claims/{id}/analyze` response), not generated
 * from the schema. See the integration report for this gap.
 */

export type VehicleCategory =
  | "Hatchback"
  | "Sedan"
  | "SUV"
  | "Luxury Car"
  | "Bus"
  | "Truck"
  | "Commercial Vehicle";

export const VEHICLE_CATEGORIES: VehicleCategory[] = [
  "Hatchback",
  "Sedan",
  "SUV",
  "Luxury Car",
  "Bus",
  "Truck",
  "Commercial Vehicle",
];

/** `ClaimRecordStatus` values (`backend/app/db/models/claim.py`). */
export type ClaimStatus = "intake" | "analyzing" | "analysis_complete" | "review_required" | "failed";

/** `PartSeverity` (`backend/app/schemas/claim_state.py`). */
export type PartSeverity = "Minor" | "Moderate" | "Severe" | "Uncertain";

/** `PartAssessmentStatus`. This is the primary user-facing signal — prefer
 * it over raw confidence numbers when deciding what to show a claimant. */
export type PartAssessmentStatus = "Accepted" | "Review Required";

/** `RecommendedAction`. */
export type RecommendedAction =
  | "Repair"
  | "Repair + Repaint"
  | "Replace"
  | "Replace / Major Repair"
  | "Manual Inspection";

/**
 * One damaged part, 1:1 with the ai-service's per-part JSON
 * (`PartDamageAssessment`). `damage_confidence`/`part_confidence` and the
 * `max_*_seen` aggregates are raw model confidence — kept in the type for
 * future admin/debug/explainability views, but deliberately not surfaced
 * prominently in the normal claimant-facing report (use `status` instead).
 */
export interface PartDamageAssessment {
  part: string;
  severity: PartSeverity;
  damage_percentage: number;
  damage_confidence: number;
  part_confidence: number;
  status: PartAssessmentStatus;
  recommended_action: RecommendedAction;
  detected_in_images: string[];
  observation_count: number;
  max_damage_confidence_seen: number | null;
  max_part_confidence_seen: number | null;
}

export interface AiAssessmentSummary {
  total_parts: number;
  accepted: number;
  review_required: number;
}

/** The merged `claim_analysis` object from ai-service's `/analyze-claim`,
 * stored verbatim as `ClaimResponse.ai_assessment`. */
export interface AiAssessment {
  damaged_parts: PartDamageAssessment[];
  summary: AiAssessmentSummary;
}

/** `PartCostEstimate`. Never rendered as ₹0 — a `null` entry in
 * `PricingAssessment.per_part` means "Manual Inspection Required", not zero cost. */
export interface PartCostEstimate {
  min_inr: number;
  max_inr: number;
  currency: "INR";
  vehicle_category: string;
  basis: string;
  label: string;
}

/** `ClaimCostSummary`, stored as `ClaimResponse.pricing_assessment`. */
export interface PricingAssessment {
  per_part: Record<string, PartCostEstimate | null>;
  total_min_inr: number;
  total_max_inr: number;
  currency: "INR";
  parts_priced: number;
  parts_pending_manual_inspection: number;
}

export interface ClaimResponse {
  id: string;
  status: ClaimStatus;
  vehicle_type: VehicleCategory;
  vehicle_make: string | null;
  vehicle_model: string | null;
  vehicle_variant: string | null;
  vehicle_year: number | null;
  incident_date: string | null;
  user_id: number | null;
  ai_assessment: AiAssessment | null;
  pricing_assessment: PricingAssessment | null;
  coverage_analysis: CoverageAnalysisResult | null;
  risk_assessment: RiskAssessment | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Policy RAG / coverage analysis / risk signals / unified report (mirrors
// backend/app/schemas/policy_state.py)
// ---------------------------------------------------------------------------

export type CoverageStatus = "likely_covered" | "unclear" | "potential_exclusion" | "manual_review";
export type VehicleMatchStatus = "match" | "mismatch" | "unknown";

export interface RetrievedClause {
  page: number | null;
  section: string | null;
  excerpt: string;
  score: number;
}

export interface PartCoverageAssessment {
  part: string;
  coverage_status: CoverageStatus;
  reason: string;
  relevant_clauses: RetrievedClause[];
}

export interface CoverageAnalysisResult {
  overall_status: CoverageStatus;
  summary: string;
  vehicle_match: VehicleMatchStatus;
  part_assessments: PartCoverageAssessment[];
  deductible_inr: number | null;
  idv_inr: number | null;
  warnings: string[];
  generated_at: string;
}

export type RiskLevel = "low" | "medium" | "high" | "insufficient_data";
export type RiskSignalSeverity = "info" | "warning" | "high";

export interface RiskSignal {
  code: string;
  severity: RiskSignalSeverity;
  description: string;
}

export interface RiskAssessment {
  risk_level: RiskLevel;
  signals: RiskSignal[];
  generated_at: string;
}

export type PolicyAnalysisState = "not_available" | "processing" | "ready" | "needs_attention" | "failed";

export interface UnifiedClaimReport {
  claim_id: string;
  vehicle: {
    make: string | null;
    model: string | null;
    variant: string | null;
    year: number | null;
    category: string;
    reference_image_url: string | null;
  };
  damage: {
    damaged_parts: number;
    accepted: number;
    review_required: number;
    overall_severity: string | null;
    recommended_actions: string[];
  };
  pricing: {
    total_min_inr: number | null;
    total_max_inr: number | null;
    parts_priced: number;
    parts_pending_manual_inspection: number;
  };
  policy: {
    state: PolicyAnalysisState;
    coverage: CoverageAnalysisResult | null;
    deductible_inr: number | null;
    idv_inr: number | null;
    exclusions: string[];
    policy_type: "Third-Party" | "Comprehensive" | "Standalone Own-Damage" | null;
    insurer_name: string | null;
    policy_number_masked: string | null;
    coverage_start: string | null;
    coverage_end: string | null;
    policy_vehicle_make: string | null;
    policy_vehicle_model: string | null;
    policy_vehicle_year: number | null;
  };
  risk: RiskAssessment;
  summary: string;
  generated_at: string;
}

export type TimelineStageStatus = "complete" | "in_progress" | "not_started" | "not_available" | "needs_attention";

export interface TimelineStage {
  key: string;
  label: string;
  status: TimelineStageStatus;
  detail: string | null;
  occurred_at: string | null;
}

export interface TimelineResponse {
  stages: TimelineStage[];
}

export type PolicyDocumentStatus = "uploaded" | "processing" | "processed" | "failed";

export interface PolicyDocumentResponse {
  status: PolicyDocumentStatus;
  filename: string;
  extraction_method: string | null;
  page_count: number | null;
  structured_data: {
    policy_type: string | null;
    policy_number: string | null;
    insurer_name: string | null;
    coverage_start: string | null;
    coverage_end: string | null;
    idv_inr: number | null;
    deductible_inr: number | null;
    zero_dep: boolean;
    add_ons: string[];
    exclusions: string[];
    vehicle_make: string | null;
    vehicle_model: string | null;
    vehicle_year: number | null;
    registration_number: string | null;
  } | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Notifications (mirrors backend/app/schemas/notification_api.py)
// ---------------------------------------------------------------------------

export interface NotificationItem {
  id: number;
  claim_id: string | null;
  type: string;
  title: string;
  body: string;
  read: boolean;
  created_at: string;
}

export interface NotificationListResponse {
  items: NotificationItem[];
  unread_count: number;
}

export interface CreateClaimInput {
  vehicle_type: VehicleCategory;
  vehicle_make: string;
  vehicle_model: string;
  vehicle_variant?: string;
  vehicle_year: number;
  // No user_id: the backend derives claim ownership from the
  // Authorization bearer token (see lib/api/client.ts's authHeaders),
  // never from a client-supplied value.
}

// ---------------------------------------------------------------------------
// Vehicle catalog (mirrors backend/app/services/vehicle_catalog.py)
// ---------------------------------------------------------------------------

export type CatalogStatus = "active" | "historical" | "discontinued";

export interface VehicleManufacturer {
  id: string;
  name: string;
  status: CatalogStatus;
}

export interface VehicleCatalogModel {
  id: string;
  name: string;
  category: VehicleCategory;
  status: CatalogStatus;
  aliases: string[];
  variants: string[];
}

/**
 * Mirrors `backend/app/schemas/dashboard_api.py`'s `VehicleReferenceImage`.
 *
 * A generic illustration of this vehicle's make/model/category — NEVER
 * the claimant's actual photographed vehicle, and never claim evidence.
 * `match_confidence` reflects how specific the match actually is (a
 * category-level fallback is always < 0.5); never render this as if it
 * depicts the claimant's real car.
 */
export interface VehicleReferenceImage {
  url: string;
  source: string;
  match_confidence: number;
}

/** Mirrors `ClaimSummary` — pre-aggregated counts derived from a claim's
 * stored `ai_assessment`/`pricing_assessment`, not raw AI payloads. */
export interface ClaimListItemSummary {
  damaged_parts: number;
  review_required: number;
  total_min_inr: number | null;
  total_max_inr: number | null;
}

/** Mirrors `ClaimListItem` — the lean shape `GET /claims` returns for the
 * dashboard's claim-history grid. */
export interface ClaimListItem {
  id: string;
  status: ClaimStatus;
  vehicle_type: VehicleCategory;
  vehicle_make: string | null;
  vehicle_model: string | null;
  vehicle_year: number | null;
  vehicle_reference_image: VehicleReferenceImage | null;
  created_at: string;
  summary: ClaimListItemSummary;
  has_policy: boolean;
  policy_ready: boolean;
  needs_manual_review: boolean;
}

export interface ClaimListResponse {
  items: ClaimListItem[];
}
