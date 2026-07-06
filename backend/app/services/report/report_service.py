"""Unified claim report builder (Task 6).

Pure aggregation over data this project already persists (`ai_assessment`,
`pricing_assessment`, policy `structured_data`, `coverage_analysis`,
`risk_assessment`) — never re-runs inference, never invents a field that
isn't backed by one of those. The `summary` is templated from real counts,
not an LLM-written paragraph (see Task 6 instructions).
"""

from __future__ import annotations

from typing import List, Optional

from app.schemas.claim_state import PartDamageAssessment, VisionAssessment
from app.schemas.policy_state import (
    CoverageAnalysisResult,
    CoverageStatus,
    PolicyAnalysisState,
    PolicyStructuredData,
    ReportDamageInfo,
    ReportPolicyInfo,
    ReportPricingInfo,
    ReportVehicleInfo,
    RiskAssessment,
    RiskLevel,
    UnifiedClaimReport,
)

_NEEDS_ATTENTION_STATUSES = {
    CoverageStatus.POTENTIAL_EXCLUSION,
    CoverageStatus.MANUAL_REVIEW,
    CoverageStatus.UNCLEAR,
}


def _mask_policy_number(policy_number: Optional[str]) -> Optional[str]:
    """Keeps only the last 4 characters visible — enough for a claimant to
    recognize their own policy, never enough to be useful if this report
    were ever viewed by anyone else. Short values (<=4 chars) are masked
    entirely rather than shown in full."""
    if not policy_number:
        return None
    visible = policy_number[-4:] if len(policy_number) > 4 else ""
    return "•" * (len(policy_number) - len(visible)) + visible


def _policy_state(policy_status: Optional[str], coverage: Optional[CoverageAnalysisResult]) -> PolicyAnalysisState:
    if policy_status is None:
        return PolicyAnalysisState.NOT_AVAILABLE
    if policy_status in ("uploaded", "processing"):
        return PolicyAnalysisState.PROCESSING
    if policy_status == "failed":
        return PolicyAnalysisState.FAILED
    if policy_status == "processed":
        if coverage is not None and coverage.overall_status in _NEEDS_ATTENTION_STATUSES:
            return PolicyAnalysisState.NEEDS_ATTENTION
        return PolicyAnalysisState.READY
    return PolicyAnalysisState.NOT_AVAILABLE


def _build_summary(
    *,
    damage: ReportDamageInfo,
    pricing: ReportPricingInfo,
    policy_state: PolicyAnalysisState,
    coverage: Optional[CoverageAnalysisResult],
    risk: RiskAssessment,
) -> str:
    sentences: List[str] = []

    if damage.damaged_parts > 0:
        sentence = f"Damage assessment identified {damage.damaged_parts} affected part(s)."
        if damage.review_required > 0:
            sentence += (
                f" {damage.accepted} were automatically assessed and {damage.review_required} "
                "require manual inspection."
            )
        sentences.append(sentence)
    else:
        sentences.append("No damage assessment has been completed yet.")

    if pricing.parts_priced > 0:
        sentences.append(
            f"The current repair estimate covers {pricing.parts_priced} assessed part(s)."
        )

    if policy_state == PolicyAnalysisState.NOT_AVAILABLE:
        sentences.append("No policy document has been attached to this claim.")
    elif policy_state == PolicyAnalysisState.PROCESSING:
        sentences.append("Policy analysis is still processing.")
    elif policy_state == PolicyAnalysisState.FAILED:
        sentences.append("Policy analysis could not be completed for the uploaded document.")
    elif coverage is not None:
        sentences.append(coverage.summary)

    if risk.risk_level == RiskLevel.INSUFFICIENT_DATA:
        pass  # No claim to make yet — omit rather than assert "no risk".
    elif risk.risk_level == RiskLevel.LOW:
        sentences.append("No risk inconsistencies were detected.")
    else:
        sentences.append(
            f"{len(risk.signals)} risk signal(s) were raised and are recommended for review."
        )

    return " ".join(sentences)


def build_unified_report(
    *,
    claim_id: str,
    vehicle_type: str,
    vehicle_make: Optional[str],
    vehicle_model: Optional[str],
    vehicle_year: Optional[int],
    reference_image_url: Optional[str],
    vehicle_variant: Optional[str] = None,
    ai_assessment: Optional[dict],
    pricing_assessment: Optional[dict],
    policy_status: Optional[str],
    policy_structured_data: Optional[dict],
    coverage_analysis: Optional[dict],
    risk_assessment: dict,
) -> UnifiedClaimReport:
    damaged_parts_raw = (ai_assessment or {}).get("damaged_parts") or []
    damaged_parts = [PartDamageAssessment.model_validate(p) for p in damaged_parts_raw]
    vision = VisionAssessment(damaged_parts=damaged_parts)

    accepted = sum(1 for p in damaged_parts if p.status.value == "Accepted")
    review_required = sum(1 for p in damaged_parts if p.status.value == "Review Required")
    recommended_actions = sorted(
        {p.recommended_action.value for p in damaged_parts if p.status.value == "Accepted"}
    )

    damage = ReportDamageInfo(
        damaged_parts=len(damaged_parts),
        accepted=accepted,
        review_required=review_required,
        overall_severity=vision.overall_severity.value if vision.overall_severity else None,
        recommended_actions=recommended_actions,
    )

    pricing = ReportPricingInfo(
        total_min_inr=(pricing_assessment or {}).get("total_min_inr") if pricing_assessment else None,
        total_max_inr=(pricing_assessment or {}).get("total_max_inr") if pricing_assessment else None,
        parts_priced=(pricing_assessment or {}).get("parts_priced", 0) if pricing_assessment else 0,
        parts_pending_manual_inspection=(
            (pricing_assessment or {}).get("parts_pending_manual_inspection", 0)
            if pricing_assessment
            else 0
        ),
    )

    coverage_result = (
        CoverageAnalysisResult.model_validate(coverage_analysis) if coverage_analysis else None
    )
    structured = (
        PolicyStructuredData.model_validate(policy_structured_data) if policy_structured_data else None
    )
    policy_state = _policy_state(policy_status, coverage_result)

    policy_info = ReportPolicyInfo(
        state=policy_state,
        coverage=coverage_result,
        deductible_inr=structured.deductible_inr if structured else None,
        idv_inr=structured.idv_inr if structured else None,
        exclusions=structured.exclusions if structured else [],
        policy_type=structured.policy_type if structured else None,
        insurer_name=structured.insurer_name if structured else None,
        policy_number_masked=_mask_policy_number(structured.policy_number) if structured else None,
        coverage_start=structured.coverage_start if structured else None,
        coverage_end=structured.coverage_end if structured else None,
        policy_vehicle_make=structured.vehicle_make if structured else None,
        policy_vehicle_model=structured.vehicle_model if structured else None,
        policy_vehicle_year=structured.vehicle_year if structured else None,
    )

    risk = RiskAssessment.model_validate(risk_assessment)

    summary = _build_summary(
        damage=damage, pricing=pricing, policy_state=policy_state, coverage=coverage_result, risk=risk
    )

    return UnifiedClaimReport(
        claim_id=claim_id,
        vehicle=ReportVehicleInfo(
            make=vehicle_make,
            model=vehicle_model,
            variant=vehicle_variant,
            year=vehicle_year,
            category=vehicle_type,
            reference_image_url=reference_image_url,
        ),
        damage=damage,
        pricing=pricing,
        policy=policy_info,
        risk=risk,
        summary=summary,
    )
