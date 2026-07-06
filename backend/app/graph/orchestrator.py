"""Entry point that gathers a claim's current state from the database,
runs the compiled `ClaimWorkflowState` graph (`app/graph/build.py`), and
persists the results back onto `ClaimRecord`.

Idempotent / retry-safe by construction: this only ever reads/updates the
existing `ClaimRecord`/`PolicyDocumentRecord` rows for `claim_id` — it
never creates a new claim, so calling it again (e.g. once after analyze,
again after a policy finishes processing) never duplicates anything, and
a mid-run failure leaves the previous persisted `coverage_analysis`/
`risk_assessment` untouched rather than half-overwritten (the graph
result is only written back after the whole run completes).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from app.db.models.claim import ClaimRecord
from app.db.models.review_item import ReviewItemSource
from app.db.policy_repository import PolicyDocumentRepository
from app.db.repository import ClaimRepository
from app.db.review_repository import ReviewItemRepository
from app.graph.build import build_claim_workflow_graph
from app.graph.workflow_state import ClaimWorkflowState
from app.observability.context import bind_claim_id
from app.observability.timing import timed_block
from app.schemas.policy_state import CoverageStatus, RiskSignalSeverity
from app.services.ai_client import AIServiceClient

logger = logging.getLogger(__name__)


def _initial_state(record: ClaimRecord, policy_doc, policy_chunks) -> ClaimWorkflowState:
    state: ClaimWorkflowState = {
        "claim_id": record.claim_id,
        "vehicle_type": record.vehicle_type,
        "vehicle_make": record.vehicle_make,
        "vehicle_model": record.vehicle_model,
        "vehicle_year": record.vehicle_year,
        "incident_date": record.incident_date.isoformat() if record.incident_date else None,
        "ai_assessment": record.ai_assessment,
        "image_hashes": record.image_hashes,
        "pricing_assessment": record.pricing_assessment,
        "policy_status": policy_doc.status if policy_doc else None,
        "policy_structured_data": policy_doc.structured_data if policy_doc else None,
        "policy_chunks": policy_chunks or None,
        "errors": [],
    }
    return state


async def _rebuild_review_queue(review_repo: ReviewItemRepository, record: ClaimRecord, result: ClaimWorkflowState) -> None:
    items: list[tuple[Optional[str], str, str]] = []

    for part in (result.get("ai_assessment") or {}).get("damaged_parts") or []:
        if part.get("status") == "Review Required":
            items.append(
                (
                    part.get("part"),
                    "Damage assessment could not confidently classify this part.",
                    ReviewItemSource.DAMAGE_ASSESSMENT.value,
                )
            )

    coverage = result.get("coverage_analysis") or {}
    for part_assessment in coverage.get("part_assessments") or []:
        if part_assessment.get("coverage_status") in (
            CoverageStatus.POTENTIAL_EXCLUSION.value,
            CoverageStatus.MANUAL_REVIEW.value,
        ):
            items.append(
                (
                    part_assessment.get("part"),
                    part_assessment.get("reason", "Coverage could not be confidently determined."),
                    ReviewItemSource.POLICY_ANALYSIS.value,
                )
            )

    risk = result.get("risk_assessment") or {}
    for signal in risk.get("signals") or []:
        if signal.get("severity") in (RiskSignalSeverity.WARNING.value, RiskSignalSeverity.HIGH.value):
            items.append((None, signal.get("description", "Risk signal raised."), ReviewItemSource.RISK_SIGNAL.value))

    await review_repo.replace_open_items_for_claim(record.id, items)


async def run_claim_workflow(
    claim_repo: ClaimRepository,
    policy_repo: PolicyDocumentRepository,
    review_repo: ReviewItemRepository,
    ai_client: AIServiceClient,
    record: ClaimRecord,
) -> ClaimRecord:
    with bind_claim_id(record.claim_id):
        policy_doc = await policy_repo.get_by_claim_id(record.id)
        policy_chunks = await policy_repo.get_chunks(policy_doc.id) if policy_doc else []

        state = _initial_state(record, policy_doc, policy_chunks)

        graph = build_claim_workflow_graph(ai_client)
        with timed_block("claim_workflow_total"):
            result: ClaimWorkflowState = await graph.ainvoke(state)

        if result.get("errors"):
            logger.warning("claim_workflow completed with node errors: %s", result["errors"])

        record.coverage_analysis = result.get("coverage_analysis")
        record.risk_assessment = result.get("risk_assessment") or {"risk_level": "insufficient_data", "signals": []}
        record.report_generated_at = datetime.now(timezone.utc)
        record = await claim_repo.save(record)

        await _rebuild_review_queue(review_repo, record, result)

    return record
