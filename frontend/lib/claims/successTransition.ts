/**
 * Sequences the confirmed-success → report-page handoff.
 *
 * Invariants this exists to guarantee (each has a test):
 * 1. The "preparing your report" state is committed AND painted before any
 *    navigation work starts — `markPrepared` runs first, then `paint`
 *    resolves after a double requestAnimationFrame, so React has flushed
 *    and the browser has drawn the frame. `router.push` can never win a
 *    race against the preparation visual.
 * 2. Nothing after a confirmed success can surface as an analysis error:
 *    prefetch failures are swallowed (prefetch is an optimization), and a
 *    navigate() throw falls back to a hard navigation instead of
 *    propagating into the caller's error handling.
 * 3. The bridge is short and bounded (`bridgeMs`) — a transition window
 *    for visual continuity, never an open-ended or long artificial delay.
 *
 * Framework-free and dependency-injected so the exact ordering is
 * unit-testable without a DOM or a Next.js router.
 */

import { logClaimFlow, type ClaimFlowEvent } from "./diagnostics";

export interface SuccessTransitionOptions {
  claimId: string;
  /** Commits the UI to its "prepared/success" state (setState calls). */
  markPrepared: () => void;
  /** Resolves once the prepared state has actually been painted.
   * Defaults to a double requestAnimationFrame; resolves immediately in
   * non-browser environments. */
  paint?: () => Promise<void>;
  /** Route warm-up. Fire-and-forget: a rejection or throw is logged and
   * swallowed — prefetch failing must never become a user-facing error. */
  prefetch?: () => unknown;
  /** Starts the actual navigation (router.push). */
  navigate: () => void;
  /** Last-resort navigation (e.g. window.location.assign) if `navigate`
   * throws — the user still reaches their completed report. */
  fallbackNavigate?: () => void;
  /** How long the success/preparing visual holds before navigation. */
  bridgeMs: number;
  /** Injectable for tests; defaults to setTimeout. */
  sleep?: (ms: number) => Promise<void>;
  log?: (event: ClaimFlowEvent) => void;
}

const defaultSleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/** Double rAF: the first fires just before the next paint, the second
 * after that paint has been committed — the standard "this frame is on
 * screen now" signal. */
const defaultPaint = () =>
  new Promise<void>((resolve) => {
    if (typeof requestAnimationFrame !== "function") {
      resolve();
      return;
    }
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
  });

/** Never rejects — every failure path inside ends in a navigation attempt
 * or a logged, swallowed error. */
export async function runSuccessTransition(options: SuccessTransitionOptions): Promise<void> {
  const {
    claimId,
    markPrepared,
    paint = defaultPaint,
    prefetch,
    navigate,
    fallbackNavigate,
    bridgeMs,
    sleep = defaultSleep,
    log = logClaimFlow,
  } = options;

  markPrepared();
  await paint();

  if (prefetch) {
    try {
      const result = prefetch();
      // App Router's prefetch is sync-void today, but tolerate a promise.
      if (result instanceof Promise) {
        result.catch((err: unknown) => {
          log({ phase: "transition:prefetch_failed", claimId, errorClass: errName(err) });
        });
      }
    } catch (err) {
      log({ phase: "transition:prefetch_failed", claimId, errorClass: errName(err) });
    }
  }

  await sleep(bridgeMs);

  try {
    navigate();
    log({ phase: "transition:navigated", claimId, target: `/claims/${claimId}` });
  } catch (err) {
    log({ phase: "transition:navigate_failed", claimId, errorClass: errName(err) });
    try {
      fallbackNavigate?.();
    } catch {
      // Both navigations failing leaves the success state on screen —
      // still never an error, and the claim page link remains reachable.
    }
  }
}

function errName(err: unknown): string {
  return err instanceof Error ? err.name : typeof err;
}
