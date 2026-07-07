/**
 * Tests for the claim result page's bundle loader — the fix for the
 * production path where a single transient failure among the page's three
 * initial requests became a terminal "Connection problem" for an
 * already-completed claim.
 */

import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api";
import { loadClaimBundle } from "./resultLoader";

const instantSleep = () => Promise.resolve();
const noopLog = () => {};

const CLAIM = { id: "CLM-TEST", status: "analysis_complete" };
const TIMELINE = { stages: [{ key: "intake" }] };
const REPORT = { summary: "ok" };

const networkError = () => new ApiError("Unable to reach the ClaimSight service.", 0);

/** Returns a fetcher that walks `results` and repeats the last entry. */
function sequence<T>(results: Array<T | Error>) {
  let call = 0;
  return Object.assign(
    () => {
      const result = results[Math.min(call, results.length - 1)];
      call += 1;
      if (result instanceof Error) return Promise.reject(result);
      return Promise.resolve(result);
    },
    { calls: () => call }
  );
}

function baseOptions() {
  return {
    claimId: "CLM-TEST",
    fetchClaim: () => Promise.resolve(CLAIM),
    fetchTimeline: () => Promise.resolve(TIMELINE),
    fetchReport: () => Promise.resolve(REPORT),
    sleep: instantSleep,
    log: noopLog,
  };
}

describe("loadClaimBundle", () => {
  it("returns the full bundle when everything loads", async () => {
    const outcome = await loadClaimBundle(baseOptions());
    expect(outcome).toEqual({
      ok: true,
      bundle: { claim: CLAIM, timeline: TIMELINE, report: REPORT, degraded: false },
    });
  });

  it("retries a transient claim failure instead of surfacing a connection error", async () => {
    // The production symptom: one blip on first load → terminal error.
    const fetchClaim = sequence<typeof CLAIM>([networkError(), CLAIM]);
    const outcome = await loadClaimBundle({ ...baseOptions(), fetchClaim });
    expect(outcome.ok).toBe(true);
    expect(fetchClaim.calls()).toBe(2);
  });

  it("renders degraded (claim without report) when the report transiently fails, never a full-page error", async () => {
    const outcome = await loadClaimBundle({
      ...baseOptions(),
      fetchReport: () => Promise.reject(new ApiError("Request failed", 500)),
    });
    expect(outcome.ok).toBe(true);
    if (outcome.ok) {
      expect(outcome.bundle.claim).toEqual(CLAIM);
      expect(outcome.bundle.timeline).toEqual(TIMELINE);
      expect(outcome.bundle.report).toBeNull();
      expect(outcome.bundle.degraded).toBe(true);
    }
  });

  it("classifies 401/403/404 immediately without retrying", async () => {
    for (const [status, kind] of [
      [401, "auth"],
      [403, "forbidden"],
      [404, "not_found"],
    ] as const) {
      const fetchClaim = sequence<typeof CLAIM>([new ApiError("Request failed", status)]);
      const outcome = await loadClaimBundle({ ...baseOptions(), fetchClaim });
      expect(outcome.ok).toBe(false);
      if (!outcome.ok) {
        expect(outcome.kind).toBe(kind);
        expect(outcome.status).toBe(status);
      }
      expect(fetchClaim.calls()).toBe(1);
    }
  });

  it("reports a truthful unreachable failure only after exhausting bounded retries", async () => {
    const fetchClaim = sequence<typeof CLAIM>([networkError()]);
    const sleeps: number[] = [];
    const outcome = await loadClaimBundle({
      ...baseOptions(),
      fetchClaim,
      attempts: 3,
      retryDelayMs: 100,
      sleep: (ms) => {
        sleeps.push(ms);
        return Promise.resolve();
      },
    });
    expect(outcome.ok).toBe(false);
    if (!outcome.ok) {
      expect(outcome.kind).toBe("unreachable");
      expect(outcome.status).toBe(0);
      // The message is honest about what happened and what's safe.
      expect(outcome.message).toMatch(/saved|try again/i);
    }
    expect(fetchClaim.calls()).toBe(3);
    expect(sleeps).toEqual([100, 200]); // linear backoff between attempts
  });

  it("recovers when the claim succeeds on a later attempt after mixed failures", async () => {
    const fetchClaim = sequence<typeof CLAIM>([
      new ApiError("Request failed", 502),
      new ApiError("Request failed", 500),
      CLAIM,
    ]);
    const outcome = await loadClaimBundle({ ...baseOptions(), fetchClaim });
    expect(outcome.ok).toBe(true);
    expect(fetchClaim.calls()).toBe(3);
  });

  it("rethrows non-API errors instead of disguising bugs as connectivity problems", async () => {
    await expect(
      loadClaimBundle({
        ...baseOptions(),
        fetchClaim: () => Promise.reject(new TypeError("undefined is not a function")),
      })
    ).rejects.toThrow(TypeError);

    await expect(
      loadClaimBundle({
        ...baseOptions(),
        fetchTimeline: () => Promise.reject(new TypeError("boom")),
      })
    ).rejects.toThrow(TypeError);
  });

  it("attempts=1 (silent refresh mode) never retries and never throws for transient failures", async () => {
    const fetchClaim = sequence<typeof CLAIM>([networkError()]);
    const outcome = await loadClaimBundle({ ...baseOptions(), fetchClaim, attempts: 1 });
    expect(outcome.ok).toBe(false);
    if (!outcome.ok) expect(outcome.kind).toBe("unreachable");
    expect(fetchClaim.calls()).toBe(1);
  });
});
