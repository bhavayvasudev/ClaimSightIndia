/**
 * Ordering and failure-isolation tests for the confirmed-success →
 * report-page handoff. The invariants under test:
 * - the preparation state is committed and painted BEFORE any navigation
 *   work (prefetch/push) starts;
 * - the transition stays up for the full bounded bridge, then navigates;
 * - nothing after a confirmed success (prefetch failure, push throw) can
 *   escape as an error — a confirmed success is terminal.
 */

import { describe, expect, it } from "vitest";
import { runSuccessTransition } from "./successTransition";

const noopLog = () => {};

function makeHarness() {
  const order: string[] = [];
  return {
    order,
    base: {
      claimId: "CLM-TEST",
      markPrepared: () => order.push("markPrepared"),
      paint: () => {
        order.push("paint");
        return Promise.resolve();
      },
      prefetch: () => order.push("prefetch"),
      navigate: () => order.push("navigate"),
      sleep: (ms: number) => {
        order.push(`sleep:${ms}`);
        return Promise.resolve();
      },
      bridgeMs: 1600,
      log: noopLog,
    },
  };
}

describe("runSuccessTransition", () => {
  it("paints the preparation state before prefetch, holds the bridge, then navigates", async () => {
    const { order, base } = makeHarness();
    await runSuccessTransition(base);
    expect(order).toEqual(["markPrepared", "paint", "prefetch", "sleep:1600", "navigate"]);
  });

  it("never calls navigate before the preparation state has painted", async () => {
    const { order, base } = makeHarness();
    let painted = false;
    await runSuccessTransition({
      ...base,
      paint: () => {
        painted = true;
        return Promise.resolve();
      },
      navigate: () => {
        expect(painted).toBe(true);
        order.push("navigate");
      },
    });
    expect(order).toContain("navigate");
  });

  it("a synchronous prefetch throw is swallowed and navigation still happens", async () => {
    const { order, base } = makeHarness();
    const events: string[] = [];
    await runSuccessTransition({
      ...base,
      prefetch: () => {
        throw new Error("prefetch exploded");
      },
      log: (e) => events.push(e.phase),
    });
    expect(order).toContain("navigate");
    expect(events).toContain("transition:prefetch_failed");
  });

  it("a rejected prefetch promise is swallowed and navigation still happens", async () => {
    const { order, base } = makeHarness();
    await runSuccessTransition({
      ...base,
      prefetch: () => Promise.reject(new Error("route fetch failed")),
    });
    // Let the rejection's catch handler run.
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(order).toContain("navigate");
  });

  it("falls back to a hard navigation when navigate throws — success never becomes an error", async () => {
    const { base } = makeHarness();
    let fellBack = false;
    await expect(
      runSuccessTransition({
        ...base,
        navigate: () => {
          throw new Error("router.push failed");
        },
        fallbackNavigate: () => {
          fellBack = true;
        },
      })
    ).resolves.toBeUndefined();
    expect(fellBack).toBe(true);
  });

  it("resolves even when both navigation paths throw", async () => {
    const { base } = makeHarness();
    await expect(
      runSuccessTransition({
        ...base,
        navigate: () => {
          throw new Error("push failed");
        },
        fallbackNavigate: () => {
          throw new Error("assign failed");
        },
      })
    ).resolves.toBeUndefined();
  });

  it("works without a prefetch or fallback (both optional)", async () => {
    const { order, base } = makeHarness();
    await runSuccessTransition({ ...base, prefetch: undefined, fallbackNavigate: undefined });
    expect(order).toEqual(["markPrepared", "paint", "sleep:1600", "navigate"]);
  });
});
