"""LangGraph claim workflow tests (Task 5): full successful flow, the
no-policy branch, the policy-processing-failure branch, the
RAG/no-relevant-chunk branch, an AI-service failure, and that node errors
are tracked in state without crashing the graph."""

from __future__ import annotations

import httpx
import pytest

from app.graph.build import build_claim_workflow_graph
from app.services.ai_client import AIServiceClient
from app.services.rag.embeddings import embed_text

pytestmark = pytest.mark.asyncio

ACCEPTED_AI_ASSESSMENT = {
    "damaged_parts": [
        {
            "part": "Front bumper",
            "severity": "Moderate",
            "damage_percentage": 20.0,
            "damage_confidence": 0.8,
            "part_confidence": 0.9,
            "status": "Accepted",
            "recommended_action": "Repair",
            "detected_in_images": ["front.jpg"],
            "observation_count": 1,
            "max_damage_confidence_seen": 0.8,
            "max_part_confidence_seen": 0.9,
        }
    ],
    "summary": {"total_parts": 1, "accepted": 1, "review_required": 0},
}


class _FakeChunk:
    def __init__(self, id_, page, section, text):
        self.id = id_
        self.page_number = page
        self.section = section
        self.text = text
        self.embedding = embed_text(text)


def _base_state(**overrides) -> dict:
    state = {
        "claim_id": "CLM-TEST0000001",
        "vehicle_type": "Sedan",
        "vehicle_make": "Hyundai",
        "vehicle_model": "Verna",
        "vehicle_year": 2021,
        "incident_date": None,
        "ai_assessment": ACCEPTED_AI_ASSESSMENT,
        "image_hashes": ["hash-1"],
        "pricing_assessment": {
            "per_part": {"Front bumper": {"min_inr": 2500, "max_inr": 7000, "currency": "INR", "vehicle_category": "Sedan", "basis": "category_heuristic_v0", "label": "Preliminary Cost Estimate"}},
            "total_min_inr": 2500,
            "total_max_inr": 7000,
            "currency": "INR",
            "parts_priced": 1,
            "parts_pending_manual_inspection": 0,
        },
        "policy_status": None,
        "policy_structured_data": None,
        "policy_chunks": None,
        "errors": [],
    }
    state.update(overrides)
    return state


def _never_called_ai_client() -> AIServiceClient:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("ai-service should never be called when ai_assessment already exists")

    return AIServiceClient(transport=httpx.MockTransport(handler))


async def test_full_successful_flow_with_processed_policy():
    ai_client = _never_called_ai_client()
    graph = build_claim_workflow_graph(ai_client)

    chunks = [_FakeChunk(1, 4, "Own Damage Coverage", "own damage accidental damage coverage applies to the front bumper")]
    state = _base_state(
        policy_status="processed",
        policy_structured_data={"vehicle_make": "Hyundai", "vehicle_model": "Verna"},
        policy_chunks=chunks,
    )

    result = await graph.ainvoke(state)

    assert result["coverage_analysis"] is not None
    assert result["coverage_analysis"]["overall_status"] == "likely_covered"
    assert result["risk_assessment"]["risk_level"] == "low"
    assert result["report"]["policy"]["state"] == "ready"
    assert result["report"]["damage"]["damaged_parts"] == 1
    assert result["report"]["pricing"]["total_min_inr"] == 2500


async def test_no_policy_branch_skips_coverage_but_keeps_damage_and_pricing():
    ai_client = _never_called_ai_client()
    graph = build_claim_workflow_graph(ai_client)

    result = await graph.ainvoke(_base_state(policy_status=None))

    assert result.get("coverage_analysis") is None
    assert result["report"]["policy"]["state"] == "not_available"
    # Damage + pricing survive untouched regardless of policy branch.
    assert result["report"]["damage"]["damaged_parts"] == 1
    assert result["report"]["pricing"]["parts_priced"] == 1
    assert result["risk_assessment"]["risk_level"] == "low"


async def test_policy_processing_failure_branch_keeps_claim_alive():
    ai_client = _never_called_ai_client()
    graph = build_claim_workflow_graph(ai_client)

    result = await graph.ainvoke(
        _base_state(policy_status="failed", policy_structured_data=None, policy_chunks=None)
    )

    assert result.get("coverage_analysis") is None
    assert result["report"]["policy"]["state"] == "failed"
    assert result["report"]["damage"]["damaged_parts"] == 1
    assert result["report"]["pricing"]["parts_priced"] == 1


async def test_rag_no_relevant_chunks_branch_still_produces_report():
    ai_client = _never_called_ai_client()
    graph = build_claim_workflow_graph(ai_client)

    # Policy processed, but retrieval found nothing usable — chunks list
    # is empty, which routes straight past coverage_analysis.
    result = await graph.ainvoke(
        _base_state(policy_status="processed", policy_structured_data={}, policy_chunks=[])
    )

    assert result.get("coverage_analysis") is None
    assert result["report"] is not None
    assert result["risk_assessment"] is not None


async def test_ai_service_failure_when_no_prior_assessment_exists():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    ai_client = AIServiceClient(transport=httpx.MockTransport(handler))
    graph = build_claim_workflow_graph(ai_client)

    state = _base_state(ai_assessment=None, pricing_assessment=None, images=[("front.jpg", b"fake", "image/jpeg")])
    result = await graph.ainvoke(state)

    assert result["ai_assessment"] is None
    assert any("Damage assessment failed" in e for e in result["errors"])
    # The graph must not crash — risk/report still get produced, just with
    # no evidence to work from.
    assert result["risk_assessment"]["risk_level"] == "insufficient_data"
    assert result["report"]["damage"]["damaged_parts"] == 0


async def test_missing_ai_assessment_and_no_images_records_error_not_crash():
    ai_client = _never_called_ai_client()
    graph = build_claim_workflow_graph(ai_client)

    state = _base_state(ai_assessment=None, pricing_assessment=None)
    result = await graph.ainvoke(state)

    assert any("No damage assessment available" in e for e in result["errors"])
    assert result["report"] is not None


async def test_damage_assessment_node_skips_rerun_when_already_present():
    # ai_client is wired to raise if called at all — proves the node
    # short-circuits without any I/O when ai_assessment is already set.
    ai_client = _never_called_ai_client()
    graph = build_claim_workflow_graph(ai_client)

    result = await graph.ainvoke(_base_state())
    assert result["ai_assessment"] == ACCEPTED_AI_ASSESSMENT
