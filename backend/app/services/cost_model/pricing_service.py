"""
Pricing service — the only place claim repair-cost estimates are computed.

Public interface:
    estimate_cost(vehicle_type, part_name, severity, recommended_action)
        -> PartCostEstimate | None
    summarize_claim_costs(vehicle_type, damaged_parts) -> ClaimCostSummary

Deliberately separate from ai-service (computer-vision inference, which
stays inference-only) and from claim_state.py (pure data contracts). The
vision pipeline decides *what* is damaged and *what action* is
recommended; this module decides what that should preliminarily cost,
given a vehicle category. See docs/decision_log.md for the reasoning.
"""

from __future__ import annotations

from typing import List, Optional

from app.schemas.claim_state import (
    ClaimCostSummary,
    PartAssessmentStatus,
    PartCostEstimate,
    PartDamageAssessment,
    RecommendedAction,
)
from app.services.cost_model.pricing_config import (
    CATEGORY_MULTIPLIERS,
    PART_GROUP_BASE_RANGES,
    resolve_part_group,
)

PRICING_BASIS = "category_heuristic_v0"


def estimate_cost(
    vehicle_type: str,
    part_name: str,
    severity: str,
    recommended_action: str,
) -> Optional[PartCostEstimate]:
    """Preliminary, heuristic repair-cost range for one damaged part.

    Returns `None` for `Manual Inspection` — a part under manual review
    must never receive a confident cost figure (see MANUAL REVIEW AND
    PRICING rule).

    `severity` is accepted for a future per-severity pricing curve (e.g.
    Moderate vs Severe within the same action) but doesn't vary price
    within a single recommended_action bucket yet — the ai-service's
    get_repair_action already folds severity into the action choice, so
    action is the primary cost driver for MVP.
    """

    if recommended_action == RecommendedAction.MANUAL_INSPECTION.value:
        return None

    multiplier = CATEGORY_MULTIPLIERS.get(vehicle_type)

    if multiplier is None:
        raise ValueError(f"Unknown vehicle_type for pricing: {vehicle_type!r}")

    part_group = resolve_part_group(part_name)
    group_ranges = PART_GROUP_BASE_RANGES[part_group]

    base_range = group_ranges.get(recommended_action)

    if base_range is None:
        # A part group without an explicit range for this action (e.g. a
        # light-group part recommended for "Repair + Repaint", which
        # ai-service's rule engine never actually produces) falls back to
        # the generic bucket rather than raising — pricing must degrade
        # gracefully, never block a report.
        base_range = PART_GROUP_BASE_RANGES["generic"].get(
            recommended_action, PART_GROUP_BASE_RANGES["generic"]["Repair"]
        )

    return PartCostEstimate(
        min_inr=round(base_range.min_inr * multiplier),
        max_inr=round(base_range.max_inr * multiplier),
        vehicle_category=vehicle_type,
        basis=PRICING_BASIS,
    )


def summarize_claim_costs(
    vehicle_type: str,
    damaged_parts: List[PartDamageAssessment],
) -> ClaimCostSummary:
    """Applies `estimate_cost` across every damaged part in a claim and
    rolls the results into a claim-level summary.

    Parts that aren't `Accepted` (i.e. still Review Required) are priced as
    `None` regardless of what estimate_cost would otherwise return — a
    belt-and-suspenders check alongside estimate_cost's own Manual
    Inspection guard, since status and recommended_action are set
    independently upstream. See MANUAL REVIEW AND PRICING rule.
    """

    per_part: dict[str, Optional[PartCostEstimate]] = {}
    total_min = 0
    total_max = 0
    priced = 0
    pending = 0

    for part in damaged_parts:
        if part.status != PartAssessmentStatus.ACCEPTED:
            per_part[part.part] = None
            pending += 1
            continue

        estimate = estimate_cost(
            vehicle_type=vehicle_type,
            part_name=part.part,
            severity=part.severity.value,
            recommended_action=part.recommended_action.value,
        )
        per_part[part.part] = estimate

        if estimate is None:
            pending += 1
        else:
            priced += 1
            total_min += estimate.min_inr
            total_max += estimate.max_inr

    return ClaimCostSummary(
        per_part=per_part,
        total_min_inr=total_min,
        total_max_inr=total_max,
        parts_priced=priced,
        parts_pending_manual_inspection=pending,
    )
