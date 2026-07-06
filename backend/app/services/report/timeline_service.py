"""Claim progress timeline (Task 7). Derives every stage's status from
actual persisted state — no fake progress percentages, and a skipped
optional stage (no policy uploaded) is `not_available`, never rendered as
a failure.
"""

from __future__ import annotations

from typing import List, Optional

from app.db.models.claim import ClaimRecord, ClaimRecordStatus
from app.db.models.policy_document import PolicyDocumentRecord, PolicyDocumentStatus
from app.schemas.policy_state import TimelineStage, TimelineStageStatus


def build_timeline(record: ClaimRecord, policy_doc: Optional[PolicyDocumentRecord]) -> List[TimelineStage]:
    stages: List[TimelineStage] = []

    stages.append(
        TimelineStage(
            key="claim_created",
            label="Claim Created",
            status=TimelineStageStatus.COMPLETE,
            occurred_at=record.created_at,
        )
    )

    has_assessment = record.ai_assessment is not None
    is_failed = record.status == ClaimRecordStatus.FAILED.value
    is_analyzing = record.status == ClaimRecordStatus.ANALYZING.value

    if has_assessment:
        assessment_status = TimelineStageStatus.COMPLETE
    elif is_analyzing:
        assessment_status = TimelineStageStatus.IN_PROGRESS
    elif is_failed:
        assessment_status = TimelineStageStatus.NEEDS_ATTENTION
    else:
        assessment_status = TimelineStageStatus.NOT_STARTED

    stages.append(
        TimelineStage(
            key="vehicle_images_validated",
            label="Vehicle Images Validated",
            status=assessment_status,
            occurred_at=record.updated_at if has_assessment else None,
        )
    )
    stages.append(
        TimelineStage(
            key="damage_assessment_complete",
            label="Damage Assessment Complete",
            status=assessment_status,
            occurred_at=record.updated_at if has_assessment else None,
        )
    )

    pricing_status = (
        TimelineStageStatus.COMPLETE if record.pricing_assessment is not None else TimelineStageStatus.NOT_STARTED
    )
    stages.append(
        TimelineStage(
            key="pricing_complete",
            label="Pricing Complete",
            status=pricing_status,
            occurred_at=record.updated_at if record.pricing_assessment is not None else None,
        )
    )

    if policy_doc is None:
        policy_stage_status = TimelineStageStatus.NOT_AVAILABLE
        policy_detail = "No policy document has been uploaded for this claim."
    elif policy_doc.status in (PolicyDocumentStatus.UPLOADED.value, PolicyDocumentStatus.PROCESSING.value):
        policy_stage_status = TimelineStageStatus.IN_PROGRESS
        policy_detail = "Policy document is being processed."
    elif policy_doc.status == PolicyDocumentStatus.FAILED.value:
        policy_stage_status = TimelineStageStatus.NEEDS_ATTENTION
        policy_detail = policy_doc.error_message or "Policy processing failed."
    else:
        policy_stage_status = TimelineStageStatus.COMPLETE
        policy_detail = None

    stages.append(
        TimelineStage(
            key="policy_processed",
            label="Policy Processed",
            status=policy_stage_status,
            detail=policy_detail,
            occurred_at=policy_doc.updated_at if policy_doc else None,
        )
    )

    if record.coverage_analysis is not None:
        coverage_status = TimelineStageStatus.COMPLETE
    elif policy_doc is None or policy_doc.status == PolicyDocumentStatus.FAILED.value:
        coverage_status = TimelineStageStatus.NOT_AVAILABLE
    else:
        coverage_status = TimelineStageStatus.NOT_STARTED

    stages.append(
        TimelineStage(
            key="coverage_analysis_complete",
            label="Coverage Analysis Complete",
            status=coverage_status,
            occurred_at=record.report_generated_at if record.coverage_analysis is not None else None,
        )
    )

    risk_status = (
        TimelineStageStatus.COMPLETE if record.risk_assessment is not None else TimelineStageStatus.NOT_STARTED
    )
    stages.append(
        TimelineStage(
            key="risk_review_complete",
            label="Risk Review Complete",
            status=risk_status,
            occurred_at=record.report_generated_at if record.risk_assessment is not None else None,
        )
    )

    report_status = (
        TimelineStageStatus.COMPLETE if record.report_generated_at is not None else TimelineStageStatus.NOT_STARTED
    )
    stages.append(
        TimelineStage(
            key="report_ready",
            label="Report Ready",
            status=report_status,
            occurred_at=record.report_generated_at,
        )
    )

    return stages
