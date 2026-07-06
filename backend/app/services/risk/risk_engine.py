"""Risk Signal Engine (Task 4) — MVP, deterministic, rule-based.

Language rules (binding): every signal is described as a neutral
"Risk Signal" — "Inconsistency Detected", "Manual Review Recommended",
"Insufficient Data". This module never labels a person a fraudster,
scammer, or criminal, and never asserts fraud has occurred — only that
something is worth a human looking at. See
`app/schemas/policy_state.py` module docstring.

Every signal below is backed by data this project actually collects.
`POLICY_CLAIM_IDENTITY_INCONSISTENCY` is declared in
`RiskSignalCode` (schema) but intentionally NOT produced by
`assess_risk()` yet — there is no claimant-identity field collected at
claim intake (no policyholder name, no registration number) to compare
against anything extracted from the policy, and fabricating a comparison
with no real inputs on one side would violate "only signals supported by
actual available project data". See the final batch report's "genuine
remaining work" section.

`risk_level` is a deterministic rollup over signal severities — never an
LLM-scored number:
  * no damaged-parts assessment exists yet at all -> insufficient_data
  * any HIGH severity signal -> high
  * any WARNING severity signal (no HIGH) -> medium
  * checks ran, found nothing -> low
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from app.schemas.policy_state import (
    PolicyStructuredData,
    RiskAssessment,
    RiskLevel,
    RiskSignal,
    RiskSignalCode,
    RiskSignalSeverity,
)

# Large-enough gap between a part's merged confidence and the max
# single-observation confidence seen across images to call the
# cross-image evidence "strongly contradictory" rather than ordinary
# observation-to-observation noise.
_INCONSISTENCY_CONFIDENCE_GAP = 0.35


def _norm(value: Optional[str]) -> Optional[str]:
    return value.strip().lower() if value else None


def _check_vehicle_mismatch(
    *,
    vehicle_make: Optional[str],
    vehicle_model: Optional[str],
    vehicle_year: Optional[int],
    structured: Optional[PolicyStructuredData],
) -> List[RiskSignal]:
    if structured is None:
        return []

    mismatched_fields = []
    if structured.vehicle_make and vehicle_make and _norm(structured.vehicle_make) != _norm(vehicle_make):
        mismatched_fields.append("make")
    if structured.vehicle_model and vehicle_model and _norm(structured.vehicle_model) != _norm(vehicle_model):
        mismatched_fields.append("model")
    if structured.vehicle_year and vehicle_year and structured.vehicle_year != vehicle_year:
        mismatched_fields.append("year")

    if not mismatched_fields:
        return []

    return [
        RiskSignal(
            code=RiskSignalCode.VEHICLE_MODEL_MISMATCH,
            severity=RiskSignalSeverity.WARNING,
            description=(
                "Vehicle "
                + "/".join(mismatched_fields)
                + " entered for the claim does not match the vehicle recorded on the policy document."
            ),
        )
    ]


def _check_policy_date_inconsistency(
    *, incident_date: Optional[date], structured: Optional[PolicyStructuredData]
) -> List[RiskSignal]:
    # No incident date collected -> the check is skipped entirely, never
    # invented (see module docstring / Task 4 instructions).
    if incident_date is None or structured is None:
        return []
    if structured.coverage_start is None or structured.coverage_end is None:
        return []

    if incident_date < structured.coverage_start or incident_date > structured.coverage_end:
        return [
            RiskSignal(
                code=RiskSignalCode.POLICY_DATE_INCONSISTENCY,
                severity=RiskSignalSeverity.HIGH,
                description=(
                    "The incident date falls outside the policy's recorded coverage period."
                ),
            )
        ]
    return []


def _check_duplicate_images(image_hashes: Optional[List[str]]) -> List[RiskSignal]:
    if not image_hashes or len(image_hashes) < 2:
        return []
    seen = set()
    duplicates = 0
    for h in image_hashes:
        if h in seen:
            duplicates += 1
        seen.add(h)
    if duplicates == 0:
        return []
    return [
        RiskSignal(
            code=RiskSignalCode.DUPLICATE_IMAGE_DETECTED,
            severity=RiskSignalSeverity.WARNING,
            description=(
                f"{duplicates} submitted image(s) are exact byte-for-byte duplicates of another "
                "image in the same claim."
            ),
        )
    ]


def _check_inconsistent_visual_assessment(damaged_parts: List[dict]) -> List[RiskSignal]:
    inconsistent_parts = []
    for part in damaged_parts:
        observation_count = part.get("observation_count", 1)
        max_conf = part.get("max_damage_confidence_seen")
        conf = part.get("damage_confidence")
        if observation_count and observation_count > 1 and max_conf is not None and conf is not None:
            if abs(max_conf - conf) > _INCONSISTENCY_CONFIDENCE_GAP:
                inconsistent_parts.append(part.get("part", "an assessed part"))

    if not inconsistent_parts:
        return []

    return [
        RiskSignal(
            code=RiskSignalCode.INCONSISTENT_VISUAL_ASSESSMENT,
            severity=RiskSignalSeverity.WARNING,
            description=(
                "Inconsistent visual assessment across submitted images for: "
                + ", ".join(inconsistent_parts)
            ),
        )
    ]


def assess_risk(
    *,
    vehicle_make: Optional[str],
    vehicle_model: Optional[str],
    vehicle_year: Optional[int],
    incident_date: Optional[date],
    damaged_parts: List[dict],
    image_hashes: Optional[List[str]],
    structured: Optional[PolicyStructuredData],
) -> RiskAssessment:
    if not damaged_parts:
        return RiskAssessment(risk_level=RiskLevel.INSUFFICIENT_DATA, signals=[])

    signals: List[RiskSignal] = []
    signals.extend(
        _check_vehicle_mismatch(
            vehicle_make=vehicle_make,
            vehicle_model=vehicle_model,
            vehicle_year=vehicle_year,
            structured=structured,
        )
    )
    signals.extend(_check_policy_date_inconsistency(incident_date=incident_date, structured=structured))
    signals.extend(_check_duplicate_images(image_hashes))
    signals.extend(_check_inconsistent_visual_assessment(damaged_parts))

    if any(s.severity == RiskSignalSeverity.HIGH for s in signals):
        level = RiskLevel.HIGH
    elif any(s.severity == RiskSignalSeverity.WARNING for s in signals):
        level = RiskLevel.MEDIUM
    else:
        level = RiskLevel.LOW

    return RiskAssessment(risk_level=level, signals=signals)
