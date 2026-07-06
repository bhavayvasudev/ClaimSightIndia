"""Pricing graph node — wraps the existing
`app.services.cost_model.pricing_service.summarize_claim_costs`, never
reimplements pricing logic. Idempotent: skips if `pricing_assessment` is
already populated (the normal case, computed by the existing
`claim_service.analyze_claim` flow before this graph runs)."""

from __future__ import annotations

from app.graph.workflow_state import ClaimWorkflowState
from app.observability.timing import timed_node
from app.schemas.claim_state import PartDamageAssessment, VisionAssessment
from app.services.cost_model import summarize_claim_costs


@timed_node("pricing")
async def pricing_node(state: ClaimWorkflowState) -> dict:
    if state.get("pricing_assessment") is not None:
        return {}

    ai_assessment = state.get("ai_assessment")
    if not ai_assessment:
        return {}

    raw_parts = ai_assessment.get("damaged_parts") or []
    try:
        damaged_parts = [PartDamageAssessment.model_validate(p) for p in raw_parts]
    except Exception as exc:
        return {"errors": [f"Pricing skipped: damaged_parts failed validation ({exc})"]}

    vision = VisionAssessment(damaged_parts=damaged_parts)
    cost_summary = summarize_claim_costs(
        vehicle_type=state["vehicle_type"], damaged_parts=vision.damaged_parts
    )
    return {"pricing_assessment": cost_summary.model_dump(mode="json")}
