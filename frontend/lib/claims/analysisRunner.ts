/**
 * Drives one claim-analysis attempt end to end and reconciles ambiguous
 * outcomes against real claim state.
 *
 * Why this exists: the analyze call is one long browser → backend POST
 * whose response can be lost even when the analysis itself succeeds — a
 * cold AI service pushes total time past a proxy/browser timeout, the
 * connection dies, and the backend still finishes and commits. Treating
 * that lost response as "couldn't connect" (what the intake form used to
 * do) shows the user a failure for a claim that completed. So a transient
 * POST failure here never surfaces directly: the runner switches to
 * polling `GET /claims/{id}` and only reports what the claim's actual
 * status says — success, a real `failed` state, or "still processing"
 * once the polling budget is spent.
 *
 * Deliberately framework-free and dependency-injected (analyze/fetch/
 * sleep) so the exact production failure sequences are unit-testable
 * without a DOM, network, or real timers.
 */

import { ApiError, userFacingMessage } from "@/lib/api";
import type { ClaimResponse } from "@/lib/api";

/** How long the initial POST may run before the runner stops waiting on
 * it and reconciles via polling instead. Kept under typical edge-proxy
 * kill windows (~100s) so we leave on our own terms, with claim state
 * polling, instead of receiving an opaque CORS-less proxy error. */
export const ANALYZE_REQUEST_TIMEOUT_MS = 90_000;

export const DEFAULT_POLL_INTERVAL_MS = 4_000;
/** Total reconciliation budget after a lost response — generous enough
 * for an AI-service cold start (30–120s) plus the analysis itself. */
export const DEFAULT_POLL_TIMEOUT_MS = 240_000;

/** Claim statuses that carry a completed, presentable assessment. */
const COMPLETED_STATUSES = new Set(["analysis_complete", "review_required"]);

export type AnalysisRunPhase =
  /** The analyze POST is in flight. */
  | "requesting"
  /** The POST outcome was ambiguous (network drop, gateway timeout, 5xx);
   * polling real claim status to find out what actually happened. */
  | "reconciling";

export type AnalysisFailureKind =
  /** Deliberate request rejection (bad images, rate limit) — the user can
   * fix the input or simply retry; the claim is untouched. */
  | "rejected"
  /** Session has no usable backend token — only a fresh sign-in repairs it. */
  | "auth"
  /** Claim doesn't exist or isn't the caller's — retrying can't help. */
  | "not_found"
  /** The analysis itself genuinely failed server-side (claim status
   * `failed`). Retrying re-runs inference — a real, safe retry. */
  | "analysis_failed"
  /** The backend is still working past the polling budget. Not a failure
   * of the claim — it stays valid and the claim page keeps checking. */
  | "still_processing"
  /** Never obtained any claim state — the service is truly unreachable. */
  | "unreachable";

export interface AnalysisFailure {
  kind: AnalysisFailureKind;
  /** Safe to render — either a mapped `userFacingMessage` or fixed copy. */
  message: string;
  /** HTTP status of the original error, when one existed. */
  status: number | null;
}

export type AnalysisOutcome =
  | { ok: true; claim: ClaimResponse; via: "response" | "poll" }
  | { ok: false; failure: AnalysisFailure };

export interface RunClaimAnalysisOptions {
  /** Performs the analyze POST (already bound to claim id/images/token). */
  analyze: () => Promise<ClaimResponse>;
  /** Fetches current claim state (already bound to claim id/token). */
  fetchClaim: () => Promise<ClaimResponse>;
  /** Phase transitions for the UI. Never fires after the run resolves. */
  onPhase?: (phase: AnalysisRunPhase) => void;
  pollIntervalMs?: number;
  pollTimeoutMs?: number;
  /** Injectable for tests; defaults to setTimeout. */
  sleep?: (ms: number) => Promise<void>;
}

const defaultSleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

const STILL_PROCESSING_MESSAGE =
  "Your claim is taking longer than usual to process. It's saved and still being analyzed — check back in a moment.";
const UNREACHABLE_MESSAGE =
  "We couldn't reach the ClaimSight service. Check your connection and retry — your claim details are saved.";
const ANALYSIS_FAILED_MESSAGE =
  "The assessment couldn't be completed for these photos. You can retry the analysis.";

function classifyImmediate(error: unknown): AnalysisFailure | null {
  if (!(error instanceof ApiError)) {
    // Programming errors must never masquerade as connectivity problems.
    throw error;
  }
  if (error.status === 401) {
    return { kind: "auth", message: userFacingMessage(error), status: 401 };
  }
  if (error.status === 403 || error.status === 404) {
    return { kind: "not_found", message: userFacingMessage(error), status: error.status };
  }
  // Deliberate rejections: the backend evaluated the request and said no.
  // Includes structured 422s (vehicle_not_detected, corrupted_image, …)
  // and 429 rate limiting. The claim was not analyzed; polling would only
  // re-read the pre-existing status, so surface these directly.
  if (error.status === 400 || error.status === 413 || error.status === 422 || error.status === 429) {
    return { kind: "rejected", message: userFacingMessage(error), status: error.status };
  }
  // Everything else (status 0 network/abort, 500/502/503/504 gateways) is
  // ambiguous — the analysis may have succeeded or still be running.
  return null;
}

/**
 * Runs one analysis attempt: POST, then — only if the POST outcome is
 * ambiguous — reconcile against polled claim status until a definitive
 * state or the polling budget is reached. Resolves exactly once; a
 * success can never be followed by an error.
 */
export async function runClaimAnalysis(options: RunClaimAnalysisOptions): Promise<AnalysisOutcome> {
  const {
    analyze,
    fetchClaim,
    onPhase,
    pollIntervalMs = DEFAULT_POLL_INTERVAL_MS,
    pollTimeoutMs = DEFAULT_POLL_TIMEOUT_MS,
    sleep = defaultSleep,
  } = options;

  onPhase?.("requesting");

  let requestError: ApiError;
  try {
    const claim = await analyze();
    return { ok: true, claim, via: "response" };
  } catch (err) {
    const immediate = classifyImmediate(err);
    if (immediate) return { ok: false, failure: immediate };
    requestError = err as ApiError;
  }

  onPhase?.("reconciling");

  const maxPolls = Math.max(1, Math.floor(pollTimeoutMs / pollIntervalMs));
  // Consecutive sightings of a claim that never entered `analyzing`: the
  // analyze request evidently never reached the backend, so keeping the
  // user waiting the full budget would be dishonest. Two sightings (not
  // one) tolerates reading a replica an instant before the
  // status=analyzing write lands.
  let notStartedSightings = 0;
  let sawAnyClaimState = false;

  for (let attempt = 0; attempt < maxPolls; attempt++) {
    await sleep(pollIntervalMs);

    let claim: ClaimResponse;
    try {
      claim = await fetchClaim();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        return { ok: false, failure: { kind: "auth", message: userFacingMessage(err), status: 401 } };
      }
      if (err instanceof ApiError && err.status === 404) {
        return { ok: false, failure: { kind: "not_found", message: userFacingMessage(err), status: 404 } };
      }
      // Transient poll failure — the network may still be recovering.
      continue;
    }

    sawAnyClaimState = true;

    if (COMPLETED_STATUSES.has(claim.status)) {
      return { ok: true, claim, via: "poll" };
    }
    if (claim.status === "failed") {
      return {
        ok: false,
        failure: { kind: "analysis_failed", message: ANALYSIS_FAILED_MESSAGE, status: requestError.status || null },
      };
    }
    if (claim.status === "analyzing") {
      notStartedSightings = 0;
      continue;
    }
    // `intake` (or any pre-analysis status): the analyze POST may never
    // have started server-side.
    notStartedSightings += 1;
    if (notStartedSightings >= 2) {
      return {
        ok: false,
        failure: {
          kind: "unreachable",
          message: UNREACHABLE_MESSAGE,
          status: requestError.status || null,
        },
      };
    }
  }

  if (!sawAnyClaimState) {
    return {
      ok: false,
      failure: { kind: "unreachable", message: UNREACHABLE_MESSAGE, status: requestError.status || null },
    };
  }
  return {
    ok: false,
    failure: { kind: "still_processing", message: STILL_PROCESSING_MESSAGE, status: null },
  };
}
