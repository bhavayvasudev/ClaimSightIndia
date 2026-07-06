import type { RiskAssessment, RiskSignalSeverity } from "@/lib/api";

const SEVERITY_TONE: Record<RiskSignalSeverity, string> = {
  info: "bg-mist text-graphite",
  warning: "bg-[#fff2df] text-amber",
  high: "bg-[#ffe8e0] text-ember",
};

const LEVEL_LABEL: Record<RiskAssessment["risk_level"], string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  insufficient_data: "Insufficient Data",
};

const LEVEL_TONE: Record<RiskAssessment["risk_level"], string> = {
  low: "bg-mint-wash text-mint",
  medium: "bg-[#fff2df] text-amber",
  high: "bg-[#ffe8e0] text-ember",
  insufficient_data: "bg-mist text-graphite",
};

/**
 * Neutral language only — "Risk Signals", never an accusation. See
 * backend app/services/risk/risk_engine.py module docstring. A signal
 * here means "worth a human look", not "this person did something wrong".
 */
export function RiskSignalsPanel({ risk }: { risk: RiskAssessment }) {
  return (
    <div className="rounded-card border border-fog bg-white p-6 shadow-panel md:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-[12px] font-medium uppercase tracking-[0.08em] text-ash">Risk Signals</p>
        <span className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-medium ${LEVEL_TONE[risk.risk_level]}`}>
          {LEVEL_LABEL[risk.risk_level]}
        </span>
      </div>

      {risk.risk_level === "insufficient_data" && (
        <p className="mt-3 text-[14px] tracking-body text-graphite">
          Not enough evidence yet to evaluate risk signals for this claim.
        </p>
      )}

      {risk.risk_level !== "insufficient_data" && risk.signals.length === 0 && (
        <p className="mt-3 text-[14px] tracking-body text-graphite">No significant inconsistencies detected.</p>
      )}

      {risk.signals.length > 0 && (
        <ul className="mt-4 space-y-2.5">
          {risk.signals.map((signal, i) => (
            <li key={i} className="flex items-start gap-2.5">
              <span className={`mt-0.5 inline-flex shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${SEVERITY_TONE[signal.severity]}`}>
                {signal.severity}
              </span>
              <p className="text-[13px] leading-relaxed tracking-body text-graphite">{signal.description}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
