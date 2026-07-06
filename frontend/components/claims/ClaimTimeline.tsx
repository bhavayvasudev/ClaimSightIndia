import type { TimelineStage, TimelineStageStatus } from "@/lib/api";

const STATUS_DOT: Record<TimelineStageStatus, string> = {
  complete: "bg-mint",
  in_progress: "bg-lavender",
  not_started: "bg-fog",
  not_available: "bg-fog",
  needs_attention: "bg-amber",
};

const STATUS_LABEL: Record<TimelineStageStatus, string> = {
  complete: "Complete",
  in_progress: "In Progress",
  not_started: "Not Started",
  not_available: "Not Available",
  needs_attention: "Needs Attention",
};

/**
 * A clean vertical progress list, not a logistics-style delivery tracker.
 * Every stage's status is exactly what the backend derived from real
 * persisted state (`app/services/report/timeline_service.py`) — no
 * synthetic percentage, and a skipped optional stage (no policy uploaded)
 * reads as "Not Available", never as a failure.
 */
export function ClaimTimeline({ stages }: { stages: TimelineStage[] }) {
  return (
    <div className="rounded-card border border-fog bg-white p-6 shadow-panel md:p-8">
      <p className="text-[12px] font-medium uppercase tracking-[0.08em] text-ash">Claim Timeline</p>
      <div className="mt-4 space-y-0">
        {stages.map((stage, i) => (
          <div key={stage.key} className="flex gap-3">
            <div className="flex flex-col items-center">
              <span className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${STATUS_DOT[stage.status]}`} aria-hidden />
              {i < stages.length - 1 && <span className="w-px flex-1 bg-fog" aria-hidden />}
            </div>
            <div className="pb-5">
              <div className="flex flex-wrap items-baseline gap-x-2">
                <p className="text-[14px] font-medium tracking-body text-carbon">{stage.label}</p>
                <span className="text-[12px] tracking-body text-ash">{STATUS_LABEL[stage.status]}</span>
              </div>
              {stage.detail && (
                <p className="mt-0.5 text-[12px] leading-relaxed tracking-body text-graphite">{stage.detail}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
