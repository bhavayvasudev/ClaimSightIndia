"""Typed state for the claim workflow orchestration graph (Task 5).

Deliberately separate from `app/schemas/claim_state.py`'s `ClaimState` —
that file's docstring (rule 4) reserves it as the API-facing contract for
a not-yet-built intake shape (`vehicle_image_id`/`policy_pdf_id`/etc.)
that doesn't match how claims are actually created today (separate
`POST /claims` + `POST /claims/{id}/analyze` + this batch's new
`POST /claims/{id}/policy`). Repurposing it here would either break its
documented intent or require bending the real flow to fit an aspirational
shape. `ClaimWorkflowState` is the typed state for the graph that
actually runs, over the actual persisted `ClaimRecord` shape.

A `TypedDict` (not a dict-of-anything) — every field the graph reads or
writes is declared here once. `errors` uses the `operator.add` reducer
since node failures should accumulate (a node's own failure must not
erase another node's error), even though this graph's nodes currently run
sequentially rather than fanned out in parallel.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, List, Optional, TypedDict


class ClaimWorkflowState(TypedDict, total=False):
    # Intake
    claim_id: str
    vehicle_type: str
    vehicle_make: Optional[str]
    vehicle_model: Optional[str]
    vehicle_year: Optional[int]
    incident_date: Optional[str]  # ISO date string, JSON-safe in graph state

    # Vehicle validation + damage assessment. `images` is only present when
    # the graph itself must run analysis (see `nodes/damage_assessment.py`)
    # — the normal call path already has `ai_assessment` populated by the
    # existing, tested `claim_service.analyze_claim` flow and this node
    # skips its own work entirely in that case (no rerun of expensive
    # inference).
    images: Optional[List[Any]]  # List[ImagePayload] tuples, when present
    ai_assessment: Optional[dict]
    image_hashes: Optional[List[str]]

    # Pricing
    pricing_assessment: Optional[dict]

    # Policy processing (already run by app/services/policy/service.py at
    # upload time — this graph only ever reads the result, never re-runs
    # extraction/OCR/structuring itself)
    policy_status: Optional[str]  # PolicyDocumentStatus value, or None if no policy
    policy_structured_data: Optional[dict]
    policy_chunks: Optional[List[Any]]  # PolicyChunkRecord rows, injected by the orchestrator

    # Policy retrieval + coverage analysis
    coverage_analysis: Optional[dict]

    # Risk signals
    risk_assessment: Optional[dict]

    # Final report
    report: Optional[dict]

    errors: Annotated[List[str], operator.add]
