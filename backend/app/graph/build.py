"""Builds the claim workflow LangGraph (Task 5).

    Claim Intake
          |
    Vehicle Validation + Damage Assessment  (skips if already done)
          |
    Pricing                                 (skips if already done)
          |
    [conditional: policy processed w/ chunks?]
      yes -> Policy Retrieval + Coverage Analysis -> Risk Signal Analysis
      no  -> Risk Signal Analysis directly (coverage_analysis stays unset;
             report_generation maps the claim's actual policy_status to
             not_available/processing/failed — never guessed at)
          |
    Final Report Generation
          |
         END

Every node wraps a real, already-tested piece of this codebase (the
ai-service client, the pricing service, the RAG-backed coverage
analyzer, the risk engine, the report builder) — none of them
reimplement that logic. See each node module's docstring.
"""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END, StateGraph

from app.graph.nodes.coverage_analysis import coverage_analysis_node
from app.graph.nodes.damage_assessment import make_damage_assessment_node
from app.graph.nodes.pricing import pricing_node
from app.graph.nodes.report_generation import report_generation_node
from app.graph.nodes.risk_signal import risk_signal_node
from app.graph.workflow_state import ClaimWorkflowState
from app.services.ai_client import AIServiceClient


def _route_policy_branch(state: ClaimWorkflowState) -> Literal["analyze_coverage", "skip_coverage"]:
    if state.get("policy_status") == "processed" and state.get("policy_chunks"):
        return "analyze_coverage"
    return "skip_coverage"


def build_claim_workflow_graph(ai_client: AIServiceClient):
    graph = StateGraph(ClaimWorkflowState)

    graph.add_node("damage_assessment", make_damage_assessment_node(ai_client))
    graph.add_node("pricing", pricing_node)
    graph.add_node("coverage_analysis", coverage_analysis_node)
    graph.add_node("risk_signal", risk_signal_node)
    graph.add_node("report_generation", report_generation_node)

    graph.set_entry_point("damage_assessment")
    graph.add_edge("damage_assessment", "pricing")
    graph.add_conditional_edges(
        "pricing",
        _route_policy_branch,
        {"analyze_coverage": "coverage_analysis", "skip_coverage": "risk_signal"},
    )
    graph.add_edge("coverage_analysis", "risk_signal")
    graph.add_edge("risk_signal", "report_generation")
    graph.add_edge("report_generation", END)

    return graph.compile()
