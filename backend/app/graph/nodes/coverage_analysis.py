"""Policy retrieval + coverage analysis graph node.

Conceptually two stages ("Policy Retrieval" then "Coverage Analysis" in
the workflow diagram) collapsed into one node here because
`app.services.policy.coverage_analysis.analyze_coverage` already performs
the retrieval internally, per damaged part (see that module — it never
sends the full policy document to anything, only retrieved excerpts).
Splitting retrieval into its own node would mean either passing retrieved
chunks back out of the graph (awkward — they're per-part, not claim-wide)
or duplicating the retrieval call; consuming it as one unit here is the
simpler, equally real option.

Conditional by construction: only runs real retrieval+classification when
`state["policy_status"] == "processed"` and chunks exist. Any other
policy state (`None`/"uploaded"/"processing"/"failed") leaves
`coverage_analysis` unset — the report-generation node maps that straight
through to the correct `PolicyAnalysisState` (not_available/processing/
failed) without this node ever guessing at a result. Damage/pricing
results are untouched either way (see module docstring rule: policy
failure must never take down the rest of the claim).
"""

from __future__ import annotations

from app.graph.workflow_state import ClaimWorkflowState
from app.observability.timing import timed_node
from app.schemas.policy_state import PolicyStructuredData
from app.services.policy.coverage_analysis import analyze_coverage


@timed_node("policy_retrieval_and_coverage_analysis")
async def coverage_analysis_node(state: ClaimWorkflowState) -> dict:
    if state.get("policy_status") != "processed":
        return {}

    chunks = state.get("policy_chunks") or []
    ai_assessment = state.get("ai_assessment") or {}
    damaged_parts = ai_assessment.get("damaged_parts") or []
    structured_raw = state.get("policy_structured_data")

    if not damaged_parts or not structured_raw:
        return {}

    structured = PolicyStructuredData.model_validate(structured_raw)
    result = analyze_coverage(
        damaged_parts=damaged_parts,
        vehicle_type=state["vehicle_type"],
        vehicle_make=state.get("vehicle_make"),
        vehicle_model=state.get("vehicle_model"),
        structured=structured,
        chunks=chunks,
    )
    return {"coverage_analysis": result.model_dump(mode="json")}
