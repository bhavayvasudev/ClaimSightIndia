"""Vehicle validation + damage assessment graph node.

Wraps the existing, tested `AIServiceClient` — never reimplements YOLO
inference, vehicle-presence validation, or multi-image merging (those all
live in the ai-service, called exactly the same way
`app/services/claim_service.py` already calls it). Idempotent by
construction: when `state["ai_assessment"]` is already populated (the
normal case — `POST /claims/{id}/analyze` already ran the real assessment
before this graph is invoked), this node does no work and no I/O at all,
so re-running the workflow (e.g. after a policy finishes processing)
never re-triggers expensive model inference.
"""

from __future__ import annotations

from typing import Callable

from app.graph.workflow_state import ClaimWorkflowState
from app.observability.timing import timed_node
from app.services.ai_client import AIServiceClient, AIServiceError


def make_damage_assessment_node(ai_client: AIServiceClient) -> Callable:
    @timed_node("damage_assessment")
    async def node(state: ClaimWorkflowState) -> dict:
        if state.get("ai_assessment") is not None:
            return {}

        images = state.get("images")
        if not images:
            return {"errors": ["No damage assessment available and no images provided."]}

        try:
            raw_response = await ai_client.analyze_claim(images)
        except AIServiceError as exc:
            return {"errors": [f"Damage assessment failed: {exc}"]}

        claim_analysis = raw_response.get("claim_analysis")
        if not isinstance(claim_analysis, dict):
            return {"errors": ["Damage assessment returned no claim_analysis."]}

        return {"ai_assessment": claim_analysis}

    return node
