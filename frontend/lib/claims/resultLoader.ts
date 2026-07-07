/**
 * Loads everything the claim result page needs — claim, timeline, report —
 * with the same reliability contract the analysis runner established:
 * a transient failure is never surfaced as a terminal error on the first
 * blip.
 *
 * Why this exists: the page previously fired all three requests in one
 * `Promise.all` with zero retries, so a single dropped connection or 5xx
 * (e.g. landing moments after a reconciled analysis, while the abandoned
 * analyze request is still finishing its post-analysis workflow
 * server-side) threw the entire page into a terminal "Connection problem"
 * state — for a claim that was already complete. That was the reachable
 * production path behind "analysis works, then the report page says it
 * couldn't connect".
 *
 * Contract:
 * - The claim itself is the critical resource: transient failures
 *   (network drop, 429, 5xx) are retried with a short backoff, bounded by
 *   `attempts`. Definitive answers (401/403/404) return immediately.
 * - Timeline and report are enhancements: if they fail transiently while
 *   the claim loads, the page renders anyway (`degraded: true`) and the
 *   caller refetches quietly — never a full-page error.
 * - Non-ApiError throws propagate: programming errors must never be
 *   disguised as connectivity problems.
 *
 * Framework-free and dependency-injected, like analysisRunner, so every
 * production failure sequence is unit-testable.
 */

import { ApiError, userFacingMessage } from "@/lib/api";
import { logClaimFlow, type ClaimFlowEvent } from "./diagnostics";

export const DEFAULT_LOAD_ATTEMPTS = 4;
export const DEFAULT_LOAD_RETRY_DELAY_MS = 1200;

export interface ClaimBundle<C, T, R> {
  claim: C;
  timeline: T | null;
  report: R | null;
  /** True when timeline/report weren't available yet — the caller should
   * render the claim and refetch the rest quietly. */
  degraded: boolean;
}

export type BundleFailureKind = "auth" | "forbidden" | "not_found" | "unreachable";

export type BundleOutcome<C, T, R> =
  | { ok: true; bundle: ClaimBundle<C, T, R> }
  | { ok: false; kind: BundleFailureKind; message: string; status: number | null };

export interface LoadClaimBundleOptions<C, T, R> {
  claimId: string;
  fetchClaim: () => Promise<C>;
  fetchTimeline: () => Promise<T>;
  fetchReport: () => Promise<R>;
  /** Total tries for the critical claim fetch (1 = no retries). */
  attempts?: number;
  retryDelayMs?: number;
  /** Injectable for tests; defaults to setTimeout. */
  sleep?: (ms: number) => Promise<void>;
  log?: (event: ClaimFlowEvent) => void;
}

const defaultSleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

const UNREACHABLE_MESSAGE =
  "We couldn't load this claim right now. It's saved and unaffected — try again in a moment.";

/** null = transient (retry); otherwise a definitive failure to surface. */
function classifyClaimError(error: unknown): BundleFailureKind | null {
  if (!(error instanceof ApiError)) throw error;
  if (error.status === 401) return "auth";
  if (error.status === 403) return "forbidden";
  if (error.status === 404) return "not_found";
  return null;
}

export async function loadClaimBundle<C, T, R>(
  options: LoadClaimBundleOptions<C, T, R>
): Promise<BundleOutcome<C, T, R>> {
  const {
    claimId,
    fetchClaim,
    fetchTimeline,
    fetchReport,
    attempts = DEFAULT_LOAD_ATTEMPTS,
    retryDelayMs = DEFAULT_LOAD_RETRY_DELAY_MS,
    sleep = defaultSleep,
    log = logClaimFlow,
  } = options;

  let lastClaimError: ApiError | null = null;
  const startedAt = Date.now();
  log({ phase: "result:load_started", claimId });

  for (let attempt = 1; attempt <= Math.max(1, attempts); attempt++) {
    if (attempt > 1) {
      // Linear backoff: enough breathing room for a mid-write window or a
      // recovering connection without keeping the user staring at a
      // spinner for long.
      await sleep(retryDelayMs * (attempt - 1));
    }

    const [claimResult, timelineResult, reportResult] = await Promise.allSettled([
      fetchClaim(),
      fetchTimeline(),
      fetchReport(),
    ]);

    if (claimResult.status === "rejected") {
      const kind = classifyClaimError(claimResult.reason); // non-ApiError rethrows
      const error = claimResult.reason as ApiError;
      log({
        phase: "result:claim_fetch_failed",
        claimId,
        attempt,
        httpStatus: error.status,
        errorClass: error.name,
      });
      if (kind) {
        return { ok: false, kind, message: userFacingMessage(error), status: error.status };
      }
      lastClaimError = error;
      continue;
    }

    // Claim in hand: the page can render. Timeline/report failures only
    // degrade it. Non-ApiError rejections still propagate as bugs.
    for (const settled of [timelineResult, reportResult]) {
      if (settled.status === "rejected" && !(settled.reason instanceof ApiError)) {
        throw settled.reason;
      }
    }

    const timeline = timelineResult.status === "fulfilled" ? timelineResult.value : null;
    const report = reportResult.status === "fulfilled" ? reportResult.value : null;
    const degraded = timeline === null || report === null;
    if (degraded) {
      log({
        phase: "result:degraded",
        claimId,
        attempt,
        httpStatus:
          timelineResult.status === "rejected"
            ? (timelineResult.reason as ApiError).status
            : reportResult.status === "rejected"
              ? (reportResult.reason as ApiError).status
              : null,
      });
    }

    log({
      phase: "result:load_completed",
      claimId,
      attempt,
      // "degraded" here means the report/timeline weren't ready yet even
      // though the claim was — the report-readiness gap, measured.
      target: degraded ? "degraded" : "complete",
      durationMs: Date.now() - startedAt,
    });
    return { ok: true, bundle: { claim: claimResult.value, timeline, report, degraded } };
  }

  log({
    phase: "result:unreachable",
    claimId,
    httpStatus: lastClaimError?.status ?? null,
    errorClass: lastClaimError?.name ?? null,
    durationMs: Date.now() - startedAt,
  });
  return {
    ok: false,
    kind: "unreachable",
    message: UNREACHABLE_MESSAGE,
    status: lastClaimError?.status ?? null,
  };
}
