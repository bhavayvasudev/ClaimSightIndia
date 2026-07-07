/**
 * Error-normalization tests for the API client, plus an end-to-end run of
 * the analyze → abort → reconcile-by-polling flow over a stubbed `fetch`.
 * These pin down the exact transport behaviours production depends on:
 * - an AbortController abort surfaces as ApiError status 0 (ambiguous),
 *   never as a raw DOMException that would bypass reconciliation;
 * - a proxy-generated HTML 504 (non-JSON body) normalizes to ApiError 504;
 * - reconciliation polls are fresh requests — they never carry the
 *   analyze call's already-aborted signal.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "./errors";
import { analyzeClaim, getClaim } from "./client";
import { runClaimAnalysis } from "@/lib/claims/analysisRunner";

const realFetch = globalThis.fetch;

function pngFile(): File {
  return new File([new Uint8Array([137, 80, 78, 71])], "damage.png", { type: "image/png" });
}

function abortError(): DOMException {
  return new DOMException("The operation was aborted.", "AbortError");
}

/** fetch stub that never resolves but rejects with AbortError on abort —
 * how a real fetch behaves when our timeout controller fires. */
function hangingFetch(init?: RequestInit): Promise<Response> {
  return new Promise((_, reject) => {
    const signal = init?.signal;
    if (!signal) return; // hang forever
    if (signal.aborted) return reject(abortError());
    signal.addEventListener("abort", () => reject(abortError()));
  });
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

beforeEach(() => {
  // The client logs technical detail via console.error outside production
  // builds — keep test output clean without asserting on it.
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  globalThis.fetch = realFetch;
  vi.restoreAllMocks();
});

describe("analyzeClaim error normalization", () => {
  it("normalizes the timeout abort into ApiError status 0 — the ambiguous class reconciliation handles", async () => {
    globalThis.fetch = ((_input: unknown, init?: RequestInit) =>
      hangingFetch(init)) as typeof fetch;

    await expect(
      analyzeClaim("CLM-TEST", [pngFile()], "token", { timeoutMs: 10 })
    ).rejects.toMatchObject({ name: "ApiError", status: 0 });
  });

  it("normalizes a proxy-generated HTML 504 (non-JSON body) into ApiError 504", async () => {
    globalThis.fetch = (() =>
      Promise.resolve(
        new Response("<html><body>504 Gateway Time-out</body></html>", {
          status: 504,
          headers: { "content-type": "text/html" },
        })
      )) as typeof fetch;

    const error = await analyzeClaim("CLM-TEST", [pngFile()], "token").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    if (error instanceof ApiError) {
      expect(error.status).toBe(504);
      expect(error.detail).toBeUndefined(); // HTML body yields no detail, and no throw
    }
  });

  it("normalizes a network-level TypeError (Failed to fetch / ERR_NETWORK) into ApiError status 0", async () => {
    globalThis.fetch = (() => Promise.reject(new TypeError("Failed to fetch"))) as typeof fetch;
    await expect(getClaim("CLM-TEST", "token")).rejects.toMatchObject({
      name: "ApiError",
      status: 0,
    });
  });
});

describe("analyze → abort → reconcile, end to end over stubbed fetch", () => {
  it("aborted POST reconciles to success via fresh, signal-free polls despite one transient poll failure", async () => {
    const pollSignals: Array<AbortSignal | null | undefined> = [];
    let call = 0;

    globalThis.fetch = ((input: unknown, init?: RequestInit) => {
      call += 1;
      const url = String(input);
      if (init?.method === "POST") {
        // The analyze POST: hangs until the client's own timeout aborts it.
        return hangingFetch(init);
      }
      expect(url).toContain("/claims/CLM-TEST");
      pollSignals.push(init?.signal);
      if (call === 2) {
        // First poll: the network is still recovering — a transient drop.
        return Promise.reject(new TypeError("Failed to fetch"));
      }
      if (call === 3) {
        return Promise.resolve(jsonResponse({ id: "CLM-TEST", status: "analyzing" }));
      }
      return Promise.resolve(jsonResponse({ id: "CLM-TEST", status: "analysis_complete" }));
    }) as typeof fetch;

    const outcome = await runClaimAnalysis({
      analyze: () => analyzeClaim("CLM-TEST", [pngFile()], "token", { timeoutMs: 10 }),
      fetchClaim: () => getClaim("CLM-TEST", "token"),
      claimId: "CLM-TEST",
      sleep: () => Promise.resolve(),
      log: () => {},
    });

    expect(outcome.ok).toBe(true);
    if (outcome.ok) {
      expect(outcome.via).toBe("poll");
      expect(outcome.claim.status).toBe("analysis_complete");
    }
    // Every reconciliation poll was a fresh request: no poll ever carried
    // the analyze call's (aborted) signal.
    expect(pollSignals.length).toBeGreaterThanOrEqual(2);
    for (const signal of pollSignals) {
      expect(signal ?? undefined).toBeUndefined();
    }
  });
});
