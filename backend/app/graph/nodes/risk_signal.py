"""Risk signal graph node — wraps
`app.services.risk.risk_engine.assess_risk`. Always runs (unlike the
policy branch, risk assessment must produce a result — at minimum
`insufficient_data` — from whatever evidence currently exists, never skip
outright)."""

from __future__ import annotations

from datetime import date as date_type

from app.graph.workflow_state import ClaimWorkflowState
from app.observability.timing import timed_node
from app.schemas.policy_state import PolicyStructuredData
from app.services.risk.risk_engine import assess_risk


@timed_node("risk_signal_analysis")
async def risk_signal_node(state: ClaimWorkflowState) -> dict:
    ai_assessment = state.get("ai_assessment") or {}
    damaged_parts = ai_assessment.get("damaged_parts") or []

    structured_raw = state.get("policy_structured_data")
    structured = PolicyStructuredData.model_validate(structured_raw) if structured_raw else None

    incident_date_str = state.get("incident_date")
    incident_date = date_type.fromisoformat(incident_date_str) if incident_date_str else None

    result = assess_risk(
        vehicle_make=state.get("vehicle_make"),
        vehicle_model=state.get("vehicle_model"),
        vehicle_year=state.get("vehicle_year"),
        incident_date=incident_date,
        damaged_parts=damaged_parts,
        image_hashes=state.get("image_hashes"),
        structured=structured,
    )
    return {"risk_assessment": result.model_dump(mode="json")}
