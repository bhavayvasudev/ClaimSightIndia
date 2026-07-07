/**
 * Stage model for the analysis-progress experience.
 *
 * The analyze API is a single blocking call with no live progress signal,
 * so stage advancement is time-based — but every label maps to work the
 * backend + ai-service genuinely perform inside that one request, in this
 * order (upload → Pillow/vehicle-presence validation → YOLO damage
 * segmentation → part matching/merge → category-aware pricing →
 * persistence + report workflow). The final stage never auto-completes:
 * it holds as active until the runner confirms real completion, so the UI
 * never claims a result that doesn't exist yet.
 *
 * Kept as a pure module (no React) so the invariants — stages advance
 * monotonically, never regress, never skip past the hold stage on a
 * timer — are directly unit-testable.
 */

export interface AnalysisStage {
  key: string;
  label: string;
  /** One supporting line shown only while the stage is active. */
  detail: string;
  /** Time-based hold before advancing. `null` = hold until real completion. */
  holdMs: number | null;
}

export const ANALYSIS_STAGES: AnalysisStage[] = [
  {
    key: "upload",
    label: "Uploading evidence",
    detail: "Securely transferring your damage photos.",
    holdMs: 1800,
  },
  {
    key: "validate",
    label: "Validating vehicle photos",
    detail: "Confirming each photo clearly shows a vehicle.",
    holdMs: 2600,
  },
  {
    key: "damage",
    label: "Inspecting visible damage",
    detail: "Locating dents, scratches, and broken areas.",
    holdMs: 3200,
  },
  {
    key: "parts",
    label: "Assessing affected components",
    detail: "Matching damage to specific vehicle parts.",
    holdMs: 3000,
  },
  {
    key: "estimate",
    label: "Calculating repair estimate",
    detail: "Applying category-aware pricing for your vehicle.",
    holdMs: 2800,
  },
  {
    key: "finalize",
    label: "Finalising assessment",
    detail: "Verifying and recording the completed analysis.",
    holdMs: null,
  },
];

export interface StageProgress {
  /** Index of the currently active stage; stages before it are settled. */
  activeIndex: number;
  /** True only once real completion is confirmed — every stage settles. */
  completed: boolean;
}

export const INITIAL_STAGE_PROGRESS: StageProgress = { activeIndex: 0, completed: false };

/** Timer tick: move to the next stage. Never advances past the final
 * hold stage, and never mutates a completed progression. */
export function advanceStage(progress: StageProgress): StageProgress {
  if (progress.completed) return progress;
  const nextIndex = Math.min(progress.activeIndex + 1, ANALYSIS_STAGES.length - 1);
  if (nextIndex === progress.activeIndex) return progress;
  return { activeIndex: nextIndex, completed: false };
}

/** Real completion confirmed: settle every stage. Terminal — no
 * subsequent transition can un-complete it. */
export function completeStages(): StageProgress {
  return { activeIndex: ANALYSIS_STAGES.length - 1, completed: true };
}

/** The hold before auto-advancing out of `activeIndex`, or null when the
 * stage waits for real completion. */
export function stageHoldMs(progress: StageProgress): number | null {
  if (progress.completed) return null;
  return ANALYSIS_STAGES[progress.activeIndex].holdMs;
}
