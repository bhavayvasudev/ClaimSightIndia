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
import { logClaimFlow, type ClaimFlowEvent } from "./diagnostics";

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
  /** For diagnostics only — never used for requests. */
  claimId?: string;
  log?: (event: ClaimFlowEvent) => void;
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
    claimId,
    log = logClaimFlow,
  } = options;

  // Wall-clock timing for the diagnostics lines only — never drives any
  // decision in the flow itself.
  const startedAt = Date.now();
  const elapsedMs = () => Date.now() - startedAt;

  onPhase?.("requesting");
  log({ phase: "analysis:started", claimId });

  let requestError: ApiError;
  try {
    const claim = await analyze();
    log({
      phase: "analysis:outcome",
      claimId,
      target: "ok:response",
      claimStatus: claim.status,
      durationMs: elapsedMs(),
    });
    return { ok: true, claim, via: "response" };
  } catch (err) {
    const immediate = classifyImmediate(err);
    if (immediate) {
      log({
        phase: "analysis:outcome",
        claimId,
        target: immediate.kind,
        httpStatus: immediate.status,
        durationMs: elapsedMs(),
      });
      return { ok: false, failure: immediate };
    }
    requestError = err as ApiError;
    log({
      phase: "analysis:request_ambiguous",
      claimId,
      httpStatus: requestError.status,
      errorClass: requestError.name,
      // For status 0 the client preserves the underlying fetch rejection's
      // name in `detail`: "AbortError" = our 90s timeout fired,
      // "TypeError" = genuine network/connection drop.
      abortReason: requestError.status === 0 ? (requestError.detail ?? null) : null,
      durationMs: elapsedMs(),
    });
  }

  onPhase?.("reconciling");
  log({ phase: "analysis:reconciling_started", claimId, durationMs: elapsedMs() });

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
        log({ phase: "analysis:outcome", claimId, target: "auth", attempt: attempt + 1 });
        return { ok: false, failure: { kind: "auth", message: userFacingMessage(err), status: 401 } };
      }
      if (err instanceof ApiError && err.status === 404) {
        log({ phase: "analysis:outcome", claimId, target: "not_found", attempt: attempt + 1 });
        return { ok: false, failure: { kind: "not_found", message: userFacingMessage(err), status: 404 } };
      }
      // Transient poll failure — the network may still be recovering.
      log({
        phase: "analysis:poll_error",
        claimId,
        attempt: attempt + 1,
        httpStatus: err instanceof ApiError ? err.status : null,
        errorClass: err instanceof Error ? err.name : typeof err,
      });
      continue;
    }

    sawAnyClaimState = true;
    log({ phase: "analysis:poll", claimId, attempt: attempt + 1, claimStatus: claim.status });

    if (COMPLETED_STATUSES.has(claim.status)) {
      log({
        phase: "analysis:outcome",
        claimId,
        target: "ok:poll",
        claimStatus: claim.status,
        attempt: attempt + 1,
        durationMs: elapsedMs(),
      });
      return { ok: true, claim, via: "poll" };
    }
    if (claim.status === "failed") {
      log({ phase: "analysis:outcome", claimId, target: "analysis_failed", durationMs: elapsedMs() });
      return {
        ok: false,
        failure: { kind: "analysis_failed", message: ANALYSIS_FAILED_MESSAGE, status: requestError.status || null },
      };
    }
    if (claim.status === "intake") {
      // Pre-analysis status: the analyze POST may never have started
      // server-side (e.g. the upload itself was cut off mid-transfer).
      notStartedSightings += 1;
      if (notStartedSightings >= 2) {
        log({
          phase: "analysis:outcome",
          claimId,
          target: "unreachable:never_started",
          durationMs: elapsedMs(),
        });
        return {
          ok: false,
          failure: {
            kind: "unreachable",
            message: UNREACHABLE_MESSAGE,
            status: requestError.status || null,
          },
        };
      }
      continue;
    }
    // "analyzing" — or a status this build doesn't know yet. An unknown
    // status still proves the claim exists and has progressed past
    // intake, so keep polling rather than guessing at a failure; the
    // budget bounds how long that can last either way.
    if (claim.status !== "analyzing") {
      log({ phase: "analysis:unknown_status", claimId, claimStatus: claim.status, attempt: attempt + 1 });
    }
    notStartedSightings = 0;
  }

  if (!sawAnyClaimState) {
    log({ phase: "analysis:outcome", claimId, target: "unreachable:no_state", durationMs: elapsedMs() });
    return {
      ok: false,
      failure: { kind: "unreachable", message: UNREACHABLE_MESSAGE, status: requestError.status || null },
    };
  }
  log({ phase: "analysis:outcome", claimId, target: "still_processing", durationMs: elapsedMs() });
  return {
    ok: false,
    failure: { kind: "still_processing", message: STILL_PROCESSING_MESSAGE, status: null },
  };
}
