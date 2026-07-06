"""Final report generation graph node — wraps
`app.services.report.report_service.build_unified_report`. Always runs,
never fails: every input is already optional-safe (see that module)."""

from __future__ import annotations

from app.graph.workflow_state import ClaimWorkflowState
from app.observability.timing import timed_node
from app.services.report.report_service import build_unified_report


@timed_node("report_generation")
async def report_generation_node(state: ClaimWorkflowState) -> dict:
    report = build_unified_report(
        claim_id=state["claim_id"],
        vehicle_type=state["vehicle_type"],
        vehicle_make=state.get("vehicle_make"),
        vehicle_model=state.get("vehicle_model"),
        vehicle_year=state.get("vehicle_year"),
        reference_image_url=None,
        ai_assessment=state.get("ai_assessment"),
        pricing_assessment=state.get("pricing_assessment"),
        policy_status=state.get("policy_status"),
        policy_structured_data=state.get("policy_structured_data"),
        coverage_analysis=state.get("coverage_analysis"),
        risk_assessment=state.get("risk_assessment") or {"risk_level": "insufficient_data", "signals": []},
    )
    return {"report": report.model_dump(mode="json")}
