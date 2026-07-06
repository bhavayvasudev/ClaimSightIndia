import type { ClaimStatus } from "./api/types";

export type StatusGroup = "active" | "under_review" | "completed" | "failed";

/**
 * Coarse grouping for the dashboard's status summary bar. Mirrors
 * `backend/app/db/models/claim.py`'s `ClaimRecordStatus` exactly —
 * `intake`/`analyzing` are both still "in progress" from a claimant's
 * point of view, so both group under Active. This is purely a display
 * grouping; the underlying `ClaimStatus` is still what every other part
 * of the UI (badges, detail page) keys off.
 */
export const STATUS_GROUP: Record<ClaimStatus, StatusGroup> = {
  intake: "active",
  analyzing: "active",
  analysis_complete: "completed",
  review_required: "under_review",
  failed: "failed",
};

export const STATUS_GROUP_LABEL: Record<StatusGroup, string> = {
  active: "Active",
  under_review: "Under Review",
  completed: "Completed",
  failed: "Failed",
};

export const STATUS_GROUP_ORDER: StatusGroup[] = ["active", "under_review", "completed", "failed"];
