import { describe, expect, it } from "vitest";
import {
  ANALYSIS_STAGES,
  INITIAL_STAGE_PROGRESS,
  advanceStage,
  completeStages,
  stageHoldMs,
} from "./analysisStages";

describe("analysis stage progression", () => {
  it("advances strictly forward, one stage at a time, and never regresses", () => {
    let progress = INITIAL_STAGE_PROGRESS;
    const seen: number[] = [progress.activeIndex];
    for (let i = 0; i < ANALYSIS_STAGES.length * 3; i++) {
      progress = advanceStage(progress);
      seen.push(progress.activeIndex);
    }
    for (let i = 1; i < seen.length; i++) {
      expect(seen[i]).toBeGreaterThanOrEqual(seen[i - 1]);
      expect(seen[i] - seen[i - 1]).toBeLessThanOrEqual(1);
    }
  });

  it("holds at the final stage on timer ticks and never claims completion", () => {
    let progress = INITIAL_STAGE_PROGRESS;
    for (let i = 0; i < ANALYSIS_STAGES.length * 3; i++) {
      progress = advanceStage(progress);
    }
    expect(progress.activeIndex).toBe(ANALYSIS_STAGES.length - 1);
    expect(progress.completed).toBe(false);
  });

  it("only real completion settles every stage", () => {
    const completed = completeStages();
    expect(completed).toEqual({ activeIndex: ANALYSIS_STAGES.length - 1, completed: true });
  });

  it("completion is terminal — later timer ticks cannot change it", () => {
    const completed = completeStages();
    expect(advanceStage(completed)).toBe(completed);
    expect(stageHoldMs(completed)).toBeNull();
  });

  it("every stage except the final one auto-advances; the final holds for real state", () => {
    ANALYSIS_STAGES.slice(0, -1).forEach((stage) => {
      expect(stage.holdMs).toBeGreaterThan(0);
    });
    expect(ANALYSIS_STAGES[ANALYSIS_STAGES.length - 1].holdMs).toBeNull();
    expect(stageHoldMs({ activeIndex: ANALYSIS_STAGES.length - 1, completed: false })).toBeNull();
  });
});
