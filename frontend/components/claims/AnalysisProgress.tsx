"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { EASE } from "@/lib/motion";
import { ANALYSIS_STAGES, type StageProgress } from "@/lib/claims/analysisStages";

export type AnalysisProgressMode =
  /** Stages advancing normally while the analyze request runs. */
  | "processing"
  /** The response was lost/slow; real claim status is being checked.
   * Stages hold (never regress) and a calm note explains the wait. */
  | "reconciling"
  /** Analysis confirmed complete — settle everything, confirm success,
   * and hold a "preparing report" state until navigation. */
  | "preparing";

/** How long the settled stage list stays visible before the success
 * confirmation replaces it — a bridge, not an artificial delay. */
const SETTLE_MS = 900;

export function AnalysisProgress({
  claimId,
  progress,
  mode,
}: {
  claimId: string | null;
  progress: StageProgress;
  mode: AnalysisProgressMode;
}) {
  const reducedMotion = useReducedMotion() ?? false;
  const [showSuccess, setShowSuccess] = useState(false);

  useEffect(() => {
    if (mode !== "preparing") {
      setShowSuccess(false);
      return;
    }
    if (reducedMotion) {
      setShowSuccess(true);
      return;
    }
    const timer = window.setTimeout(() => setShowSuccess(true), SETTLE_MS);
    return () => window.clearTimeout(timer);
  }, [mode, reducedMotion]);

  const transition = reducedMotion ? { duration: 0 } : { duration: 0.5, ease: EASE };

  return (
    <div className="mt-10 border-t border-fog pt-8">
      <div className="mx-auto w-full max-w-[420px]">
        <div className="flex items-baseline justify-between gap-4">
          <p className="text-[12px] font-medium uppercase tracking-[0.08em] text-graphite">
            {mode === "preparing" ? "Assessment complete" : "Analysis in progress"}
          </p>
          {claimId && (
            <p className="truncate text-[12px] tracking-body text-ash" title={claimId}>
              {claimId}
            </p>
          )}
        </div>

        <AnimatePresence mode="wait" initial={false}>
          {showSuccess ? (
            <motion.div
              key="success"
              initial={reducedMotion ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reducedMotion ? undefined : { opacity: 0, y: -6 }}
              transition={transition}
              className="flex flex-col items-center py-10 text-center"
            >
              <motion.span
                initial={reducedMotion ? false : { scale: 0.6, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={reducedMotion ? { duration: 0 } : { duration: 0.45, ease: EASE, delay: 0.1 }}
                className="flex h-11 w-11 items-center justify-center rounded-full bg-mint-wash"
              >
                <CheckIcon className="h-5 w-5 text-mint" strokeWidth={2.2} />
              </motion.span>
              <p className="mt-4 text-[15px] font-medium tracking-body text-carbon">
                Analysis complete
              </p>
              <p className="mt-1.5 flex items-baseline text-[13px] tracking-body text-graphite">
                Preparing your assessment report
                <AnimatedEllipsis reducedMotion={reducedMotion} />
              </p>
            </motion.div>
          ) : (
            <motion.div
              key="stages"
              initial={false}
              exit={reducedMotion ? undefined : { opacity: 0, y: -6 }}
              transition={transition}
              className="mt-7"
            >
              <ol>
                {ANALYSIS_STAGES.map((stage, index) => {
                  const settled = progress.completed || index < progress.activeIndex;
                  const active = !progress.completed && index === progress.activeIndex;
                  const isLast = index === ANALYSIS_STAGES.length - 1;
                  return (
                    <li key={stage.key} className="flex gap-3.5">
                      <div className="flex flex-col items-center">
                        <StageIndicator settled={settled} active={active} reducedMotion={reducedMotion} />
                        {!isLast && (
                          <span
                            className={`w-px flex-1 transition-colors duration-500 ${
                              settled ? "bg-mint/30" : "bg-fog"
                            }`}
                          />
                        )}
                      </div>
                      <div className={isLast ? "pb-1" : "pb-5"}>
                        <p
                          className={`text-[13.5px] leading-5 tracking-body transition-colors duration-500 ${
                            active ? "font-medium text-carbon" : settled ? "text-graphite" : "text-ash"
                          }`}
                        >
                          {stage.label}
                        </p>
                        <AnimatePresence initial={false}>
                          {active && (
                            <motion.p
                              initial={reducedMotion ? false : { opacity: 0, height: 0 }}
                              animate={{ opacity: 1, height: "auto" }}
                              exit={reducedMotion ? undefined : { opacity: 0, height: 0 }}
                              transition={reducedMotion ? { duration: 0 } : { duration: 0.4, ease: EASE }}
                              className="overflow-hidden text-[12px] leading-[1.6] tracking-body text-ash"
                            >
                              {stage.detail}
                            </motion.p>
                          )}
                        </AnimatePresence>
                      </div>
                    </li>
                  );
                })}
              </ol>

              <AnimatePresence initial={false} mode="wait">
                {mode === "reconciling" ? (
                  <motion.div
                    key="reconciling"
                    initial={reducedMotion ? false : { opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={reducedMotion ? undefined : { opacity: 0 }}
                    transition={transition}
                    className="mt-7 flex items-start gap-2.5 border-t border-fog pt-5"
                  >
                    <Spinner reducedMotion={reducedMotion} />
                    <p className="text-[12.5px] leading-relaxed tracking-body text-graphite">
                      Taking a little longer than usual — your claim is saved and still being
                      processed. Checking its status now.
                    </p>
                  </motion.div>
                ) : mode === "processing" ? (
                  <motion.p
                    key="note"
                    initial={reducedMotion ? false : { opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={reducedMotion ? undefined : { opacity: 0 }}
                    transition={transition}
                    className="mt-7 border-t border-fog pt-5 text-center text-[12px] tracking-body text-ash"
                  >
                    Analysis usually completes within a minute. Keep this page open.
                  </motion.p>
                ) : null}
              </AnimatePresence>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

function StageIndicator({
  settled,
  active,
  reducedMotion,
}: {
  settled: boolean;
  active: boolean;
  reducedMotion: boolean;
}) {
  if (settled) {
    return (
      <motion.span
        initial={reducedMotion ? false : { scale: 0.5, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={reducedMotion ? { duration: 0 } : { duration: 0.4, ease: EASE }}
        className="flex h-5 w-5 items-center justify-center rounded-full bg-mint-wash"
      >
        <CheckIcon className="h-2.5 w-2.5 text-mint" strokeWidth={3} />
      </motion.span>
    );
  }
  if (active) {
    return (
      <span className="flex h-5 w-5 items-center justify-center rounded-full border border-lavender/40">
        {reducedMotion ? (
          <span className="h-2 w-2 rounded-full bg-lavender" />
        ) : (
          <motion.span
            animate={{ scale: [1, 1.35, 1], opacity: [1, 0.55, 1] }}
            transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
            className="h-2 w-2 rounded-full bg-lavender"
          />
        )}
      </span>
    );
  }
  return (
    <span className="flex h-5 w-5 items-center justify-center">
      <span className="h-1.5 w-1.5 rounded-full bg-fog" />
    </span>
  );
}

function CheckIcon({ className, strokeWidth }: { className: string; strokeWidth: number }) {
  return (
    <svg viewBox="0 0 12 12" fill="none" className={className} aria-hidden>
      <path
        d="M2.2 6.4 4.8 9l5-6"
        stroke="currentColor"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function Spinner({ reducedMotion }: { reducedMotion: boolean }) {
  return (
    <span
      className={`mt-0.5 h-3.5 w-3.5 shrink-0 rounded-full border-2 border-fog border-t-lavender ${
        reducedMotion ? "" : "animate-spin"
      }`}
      aria-hidden
    />
  );
}

function AnimatedEllipsis({ reducedMotion }: { reducedMotion: boolean }) {
  if (reducedMotion) return <span>…</span>;
  return (
    <span className="ml-px inline-flex" aria-hidden>
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          animate={{ opacity: [0.25, 1, 0.25] }}
          transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut", delay: i * 0.18 }}
        >
          .
        </motion.span>
      ))}
    </span>
  );
}
