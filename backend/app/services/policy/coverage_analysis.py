"""Coverage analysis (Task 3): combines damage assessment + policy
retrieval + structured policy metadata into coverage-oriented findings.

Language rules — see `app/schemas/policy_state.py` module docstring.
ClaimSight interprets retrieved policy wording for triage; it never says
"claim approved/rejected" or "insurer will pay". Every part-level finding
only reasons from clauses actually retrieved for that part — there is no
path here that sends the full policy document to an LLM "blind" (see
`app/services/rag/retrieval.py`).

Classification is a deterministic keyword heuristic over the *retrieved*
excerpts (not the whole document) so the result is reproducible and
testable without any LLM/network dependency. This mirrors the same
"deterministic first, LLM-refinement optional" shape as
`app/services/policy/structured_extraction.py`, kept intentionally simple
here since MVP retrieval + classification is already a meaningful
improvement over "no policy analysis at all".
"""

from __future__ import annotations

from typing import List, Optional

from app.schemas.policy_state import (
    CoverageAnalysisResult,
    CoverageStatus,
    PartCoverageAssessment,
    PolicyStructuredData,
    RetrievedClause,
    VehicleMatchStatus,
)
from app.services.rag.retrieval import build_query_text, retrieve_relevant_clauses

_EXCLUSION_TERMS = (
    "excluded", "exclusion", "not covered", "not liable", "no liability",
    "shall not cover", "shall not be liable", "consequential loss",
)
_COVERAGE_TERMS = (
    "own damage", "accidental damage", "collision", "shall indemnify",
    "shall pay", "covered", "own-damage",
)


def _classify_clauses(clauses: List[RetrievedClause]) -> tuple[CoverageStatus, str]:
    if not clauses:
        return (
            CoverageStatus.MANUAL_REVIEW,
            "No relevant policy clause was retrieved with sufficient confidence.",
        )

    combined = " ".join(c.excerpt.lower() for c in clauses)
    has_exclusion = any(term in combined for term in _EXCLUSION_TERMS)
    has_coverage = any(term in combined for term in _COVERAGE_TERMS)

    if has_exclusion:
        return (
            CoverageStatus.POTENTIAL_EXCLUSION,
            "Retrieved policy wording includes exclusion language relevant to this part.",
        )
    if has_coverage:
        return (
            CoverageStatus.LIKELY_COVERED,
            "Retrieved policy wording includes own-damage/accidental-damage coverage language.",
        )
    return (
        CoverageStatus.UNCLEAR,
        "Retrieved policy wording does not clearly confirm or exclude coverage for this part.",
    )


def _vehicle_match(
    structured: PolicyStructuredData,
    *,
    vehicle_make: Optional[str],
    vehicle_model: Optional[str],
) -> VehicleMatchStatus:
    if not structured.vehicle_make and not structured.vehicle_model:
        return VehicleMatchStatus.UNKNOWN

    def _norm(v: Optional[str]) -> Optional[str]:
        return v.strip().lower() if v else None

    make_mismatch = (
        structured.vehicle_make is not None
        and vehicle_make is not None
        and _norm(structured.vehicle_make) != _norm(vehicle_make)
    )
    model_mismatch = (
        structured.vehicle_model is not None
        and vehicle_model is not None
        and _norm(structured.vehicle_model) != _norm(vehicle_model)
    )
    if make_mismatch or model_mismatch:
        return VehicleMatchStatus.MISMATCH
    return VehicleMatchStatus.MATCH


def analyze_coverage(
    *,
    damaged_parts: List[dict],
    vehicle_type: str,
    vehicle_make: Optional[str],
    vehicle_model: Optional[str],
    structured: PolicyStructuredData,
    chunks: list,
) -> CoverageAnalysisResult:
    """`damaged_parts` are plain dicts shaped like `PartDamageAssessment`
    (as stored in `ClaimRecord.ai_assessment["damaged_parts"]`). Only
    `Accepted` parts get a coverage finding — a part still under manual
    inspection has no confirmed recommended action to reason about yet."""

    part_assessments: List[PartCoverageAssessment] = []

    for part in damaged_parts:
        if part.get("status") != "Accepted":
            continue
        query = build_query_text(
            part=part.get("part"),
            severity=part.get("severity"),
            recommended_action=part.get("recommended_action"),
            vehicle_type=vehicle_type,
        )
        clauses = retrieve_relevant_clauses(chunks, query)
        status, reason = _classify_clauses(clauses)
        part_assessments.append(
            PartCoverageAssessment(
                part=part["part"], coverage_status=status, reason=reason, relevant_clauses=clauses
            )
        )

    vehicle_match = _vehicle_match(structured, vehicle_make=vehicle_make, vehicle_model=vehicle_model)

    warnings: List[str] = []
    if vehicle_match == VehicleMatchStatus.MISMATCH:
        warnings.append(
            "Vehicle make/model on the claim does not match the vehicle recorded on the policy document."
        )

    if not part_assessments:
        overall = CoverageStatus.MANUAL_REVIEW
        summary = "No accepted damaged parts are available yet to assess against the policy."
    elif any(p.coverage_status == CoverageStatus.POTENTIAL_EXCLUSION for p in part_assessments):
        overall = CoverageStatus.POTENTIAL_EXCLUSION
        excluded = sum(1 for p in part_assessments if p.coverage_status == CoverageStatus.POTENTIAL_EXCLUSION)
        summary = (
            f"Potential exclusion language was found for {excluded} of {len(part_assessments)} "
            "assessed part(s). Manual policy review is recommended."
        )
    elif all(p.coverage_status == CoverageStatus.LIKELY_COVERED for p in part_assessments):
        overall = CoverageStatus.LIKELY_COVERED
        summary = (
            f"Retrieved policy wording suggests likely coverage for all {len(part_assessments)} "
            "assessed part(s) under own-damage/accidental-damage terms."
        )
    elif any(p.coverage_status == CoverageStatus.MANUAL_REVIEW for p in part_assessments):
        overall = CoverageStatus.MANUAL_REVIEW
        summary = "One or more parts could not be matched to a policy clause with confidence."
    else:
        overall = CoverageStatus.UNCLEAR
        summary = "Coverage could not be clearly confirmed from the retrieved policy wording."

    return CoverageAnalysisResult(
        overall_status=overall,
        summary=summary,
        vehicle_match=vehicle_match,
        part_assessments=part_assessments,
        deductible_inr=structured.deductible_inr,
        idv_inr=structured.idv_inr,
        warnings=warnings,
    )
