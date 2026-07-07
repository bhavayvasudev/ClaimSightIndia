/**
 * Unit tests for the analysis runner, targeting the exact production
 * failure pattern: the analyze POST's response is lost (proxy kill,
 * gateway timeout, cold AI service) while the backend completes and
 * commits — which must reconcile to success, never "couldn't connect".
 */

import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api/errors";
import type { ClaimResponse } from "@/lib/api/types";
import { runClaimAnalysis, type AnalysisRunPhase } from "./analysisRunner";

const instantSleep = () => Promise.resolve();

function claimWithStatus(status: ClaimResponse["status"]): ClaimResponse {
  return { id: "CLM-TEST", status } as ClaimResponse;
}

/** fetchClaim stub that walks through `states` and repeats the last one. */
function claimSequence(states: Array<ClaimResponse["status"] | Error>) {
  let call = 0;
  return Object.assign(
    () => {
      const state = states[Math.min(call, states.length - 1)];
      call += 1;
      if (state instanceof Error) return Promise.reject(state);
      return Promise.resolve(claimWithStatus(state));
    },
    { calls: () => call }
  );
}

const networkError = () => new ApiError("Unable to reach the ClaimSight service.", 0);
const gatewayTimeout = () => new ApiError("Request failed", 504, "AI service timed out.");

describe("runClaimAnalysis", () => {
  it("returns the response directly when the analyze call succeeds, however slowly", async () => {
    const outcome = await runClaimAnalysis({
      analyze: () => Promise.resolve(claimWithStatus("analysis_complete")),
      fetchClaim: () => Promise.reject(new Error("must not poll on direct success")),
      sleep: instantSleep,
    });
    expect(outcome).toEqual({ ok: true, claim: claimWithStatus("analysis_complete"), via: "response" });
  });

  it("reconciles a lost response (network drop) into success once the backend commits", async () => {
    // The production bug: POST dies at the proxy, backend finishes anyway.
    const fetchClaim = claimSequence(["analyzing", "analyzing", "analysis_complete"]);
    const phases: AnalysisRunPhase[] = [];

    const outcome = await runClaimAnalysis({
      analyze: () => Promise.reject(networkError()),
      fetchClaim,
      onPhase: (p) => phases.push(p),
      sleep: instantSleep,
    });

    expect(outcome).toEqual({ ok: true, claim: claimWithStatus("analysis_complete"), via: "poll" });
    expect(phases).toEqual(["requesting", "reconciling"]);
    expect(fetchClaim.calls()).toBe(3);
  });

  it("reconciles a 504 gateway timeout into success when polling finds review_required", async () => {
    const outcome = await runClaimAnalysis({
      analyze: () => Promise.reject(gatewayTimeout()),
      fetchClaim: claimSequence(["analyzing", "review_required"]),
      sleep: instantSleep,
    });
    expect(outcome.ok).toBe(true);
    if (outcome.ok) expect(outcome.claim.status).toBe("review_required");
  });

  it("tolerates transient poll failures while the network recovers", async () => {
    const fetchClaim = claimSequence([
      networkError(),
      networkError(),
      "analyzing",
      "analysis_complete",
    ]);
    const outcome = await runClaimAnalysis({
      analyze: () => Promise.reject(networkError()),
      fetchClaim,
      sleep: instantSleep,
    });
    expect(outcome.ok).toBe(true);
  });

  it("surfaces a genuine server-side analysis failure as recoverable, not a connection error", async () => {
    const outcome = await runClaimAnalysis({
      analyze: () => Promise.reject(new ApiError("Request failed", 503)),
      fetchClaim: claimSequence(["failed"]),
      sleep: instantSleep,
    });
    expect(outcome.ok).toBe(false);
    if (!outcome.ok) {
      expect(outcome.failure.kind).toBe("analysis_failed");
      expect(outcome.failure.message).not.toMatch(/connect|reach/i);
    }
  });

  it("fails fast on deliberate rejections (422) without polling", async () => {
    let polled = false;
    const outcome = await runClaimAnalysis({
      analyze: () =>
        Promise.reject(
          new ApiError("Request failed", 422, undefined, {
            error_code: "vehicle_not_detected",
            message: "no vehicle",
            invalid_filenames: ["cat.jpg"],
          })
        ),
      fetchClaim: () => {
        polled = true;
        return Promise.resolve(claimWithStatus("intake"));
      },
      sleep: instantSleep,
    });
    expect(polled).toBe(false);
    expect(outcome.ok).toBe(false);
    if (!outcome.ok) {
      expect(outcome.failure.kind).toBe("rejected");
      expect(outcome.failure.message).toContain("cat.jpg");
    }
  });

  it("classifies 401 as auth and 404 as not_found without polling", async () => {
    const auth = await runClaimAnalysis({
      analyze: () => Promise.reject(new ApiError("Request failed", 401)),
      fetchClaim: () => Promise.reject(new Error("must not poll")),
      sleep: instantSleep,
    });
    expect(!auth.ok && auth.failure.kind).toBe("auth");

    const missing = await runClaimAnalysis({
      analyze: () => Promise.reject(new ApiError("Request failed", 404)),
      fetchClaim: () => Promise.reject(new Error("must not poll")),
      sleep: instantSleep,
    });
    expect(!missing.ok && missing.failure.kind).toBe("not_found");
  });

  it("reports still_processing (a wait state, not a failure) when the budget ends mid-analysis", async () => {
    const fetchClaim = claimSequence(["analyzing"]);
    const outcome = await runClaimAnalysis({
      analyze: () => Promise.reject(networkError()),
      fetchClaim,
      pollIntervalMs: 10,
      pollTimeoutMs: 50,
      sleep: instantSleep,
    });
    expect(outcome.ok).toBe(false);
    if (!outcome.ok) {
      expect(outcome.failure.kind).toBe("still_processing");
      expect(outcome.failure.message).not.toMatch(/connect|reach|fail/i);
    }
    expect(fetchClaim.calls()).toBe(5); // bounded by the budget
  });

  it("reports unreachable when the claim never even entered analysis", async () => {
    const outcome = await runClaimAnalysis({
      analyze: () => Promise.reject(networkError()),
      fetchClaim: claimSequence(["intake", "intake"]),
      sleep: instantSleep,
    });
    expect(!outcome.ok && outcome.failure.kind).toBe("unreachable");
  });

  it("reports unreachable when no claim state is ever obtainable", async () => {
    const outcome = await runClaimAnalysis({
      analyze: () => Promise.reject(networkError()),
      fetchClaim: () => Promise.reject(networkError()),
      pollIntervalMs: 10,
      pollTimeoutMs: 40,
      sleep: instantSleep,
    });
    expect(!outcome.ok && outcome.failure.kind).toBe("unreachable");
  });

  it("resolves exactly once — success is terminal and emits no further phases", async () => {
    const phases: AnalysisRunPhase[] = [];
    const fetchClaim = claimSequence(["analysis_complete"]);
    const outcome = await runClaimAnalysis({
      analyze: () => Promise.reject(networkError()),
      fetchClaim,
      onPhase: (p) => phases.push(p),
      sleep: instantSleep,
    });
    expect(outcome.ok).toBe(true);
    // One successful poll ended the run: no extra polls, no extra phases.
    expect(fetchClaim.calls()).toBe(1);
    expect(phases).toEqual(["requesting", "reconciling"]);
  });

  it("rethrows non-API errors instead of disguising bugs as connectivity problems", async () => {
    await expect(
      runClaimAnalysis({
        analyze: () => Promise.reject(new TypeError("undefined is not a function")),
        fetchClaim: () => Promise.resolve(claimWithStatus("analyzing")),
        sleep: instantSleep,
      })
    ).rejects.toThrow(TypeError);
  });
});
