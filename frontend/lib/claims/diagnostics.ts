/**
 * Structured diagnostic logging for the claim analysis → report flow.
 *
 * Production has shown failures that unit tests didn't reproduce, so the
 * flow now narrates itself: every phase transition, poll result, retry,
 * and navigation target is logged as one structured line that can be read
 * straight off the browser console (or a remote-logging hook later).
 *
 * Safety contract: only the fields typed below are ever logged — claim id,
 * phase names, HTTP statuses, error class names, claim statuses, attempt
 * counters, and route targets. Never tokens, cookies, user data, image
 * data, or raw backend error bodies.
 */

export interface ClaimFlowEvent {
  /** Where in the flow this event happened, e.g. "analysis:reconciling". */
  phase: string;
  claimId?: string | null;
  httpStatus?: number | null;
  /** Constructor name of a thrown error, e.g. "ApiError" | "TypeError". */
  errorClass?: string | null;
  /** Claim status as reported by the backend, e.g. "analyzing". */
  claimStatus?: string | null;
  /** 1-based attempt/poll counter, where applicable. */
  attempt?: number;
  /** Navigation target or outcome kind, e.g. "/claims/CLM-…" | "still_processing". */
  target?: string | null;
  /** Elapsed wall-clock milliseconds for the phase this event closes. */
  durationMs?: number;
  /** For status-0 failures: the underlying fetch rejection's error name —
   * "AbortError" (our own timeout fired) vs "TypeError" (network drop).
   * Never message text, only the constructor name. */
  abortReason?: string | null;
}

export function logClaimFlow(event: ClaimFlowEvent): void {
  try {
    // console.info (not error/warn): these are breadcrumbs, not alerts —
    // and they must never trip "fail on console.error" tooling.
    console.info("[claimsight:flow]", JSON.stringify(event));
  } catch {
    // Logging must never break the flow it observes.
  }
}
