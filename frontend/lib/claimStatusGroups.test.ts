import { describe, expect, it } from "vitest";

import { claimsForFilter, STATUS_GROUP } from "./claimStatusGroups";
import type { ClaimStatus } from "./api/types";

const claim = (id: string, status: ClaimStatus) => ({ id, status });

const ITEMS = [
  claim("intake-1", "intake"),
  claim("analyzing-1", "analyzing"),
  claim("review-1", "review_required"),
  claim("complete-1", "analysis_complete"),
  claim("failed-1", "failed"),
  claim("failed-2", "failed"),
];

const ids = (items: { id: string }[]) => items.map((item) => item.id);

describe("claimsForFilter", () => {
  it("excludes failed claims from the default feed", () => {
    expect(ids(claimsForFilter(ITEMS, "all"))).toEqual([
      "intake-1",
      "analyzing-1",
      "review-1",
      "complete-1",
    ]);
  });

  it("shows only failed claims in the Failed tab", () => {
    expect(ids(claimsForFilter(ITEMS, "failed"))).toEqual(["failed-1", "failed-2"]);
  });

  it("keeps failed claims out of Active, Under Review and Completed", () => {
    expect(ids(claimsForFilter(ITEMS, "active"))).toEqual(["intake-1", "analyzing-1"]);
    expect(ids(claimsForFilter(ITEMS, "under_review"))).toEqual(["review-1"]);
    expect(ids(claimsForFilter(ITEMS, "completed"))).toEqual(["complete-1"]);
  });

  it("covers every backend status in the grouping map", () => {
    // Compile-time Record<ClaimStatus, ...> already enforces this; the
    // runtime assertion documents the contract for future statuses.
    expect(Object.keys(STATUS_GROUP).sort()).toEqual(
      ["analysis_complete", "analyzing", "failed", "intake", "review_required"].sort(),
    );
  });
});
