"use client";

import { useRef, useState } from "react";
import type { CoverageAnalysisResult, CoverageStatus, PolicyAnalysisState } from "@/lib/api";
import { formatInr } from "@/lib/formatting";
import { PillButton } from "@/components/ui/PillButton";

const COVERAGE_LABEL: Record<CoverageStatus, string> = {
  likely_covered: "Likely Covered",
  unclear: "Coverage Unclear",
  potential_exclusion: "Potential Exclusion",
  manual_review: "Manual Review Recommended",
};

const COVERAGE_TONE: Record<CoverageStatus, string> = {
  likely_covered: "bg-mint-wash text-mint",
  unclear: "bg-mist text-graphite",
  potential_exclusion: "bg-[#ffe8e0] text-ember",
  manual_review: "bg-[#fff2df] text-amber",
};

type Props = {
  policyState: PolicyAnalysisState;
  errorMessage?: string | null;
  coverage: CoverageAnalysisResult | null;
  deductibleInr: number | null;
  idvInr: number | null;
  exclusions: string[];
  uploading: boolean;
  onUpload: (file: File) => void;
  policyType?: string | null;
  insurerName?: string | null;
  policyNumberMasked?: string | null;
  coverageStart?: string | null;
  coverageEnd?: string | null;
  policyVehicleMake?: string | null;
  policyVehicleModel?: string | null;
  policyVehicleYear?: number | null;
};

function formatPolicyDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

/**
 * Every status here is a possible real backend state — not a stand-in
 * for "feature not built yet". "Not Available" means no policy was
 * uploaded, which is a normal, unremarkable state for a claim, not an
 * error. Coverage findings are only ever what was retrieved from the
 * claimant's own uploaded policy text — see backend
 * app/services/policy/coverage_analysis.py.
 */
export function PolicyAnalysisPanel({
  policyState,
  errorMessage,
  coverage,
  deductibleInr,
  idvInr,
  exclusions,
  uploading,
  onUpload,
  policyType,
  insurerName,
  policyNumberMasked,
  coverageStart,
  coverageEnd,
  policyVehicleMake,
  policyVehicleModel,
  policyVehicleYear,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  if (policyState === "not_available") {
    return (
      <div className="rounded-card border border-dashed border-fog bg-mist/30 p-6 md:p-8">
        <p className="text-[12px] font-medium uppercase tracking-[0.08em] text-ash">Policy Analysis</p>
        <p className="mt-2 text-[15px] tracking-body text-carbon">Attach policy document</p>
        <p className="mt-1 max-w-copy text-[13px] leading-relaxed tracking-body text-graphite">
          Upload the policy PDF or a clear photo of it to see coverage findings for this claim&rsquo;s
          damage assessment.
        </p>
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            const file = e.dataTransfer.files?.[0];
            if (file) onUpload(file);
          }}
          className={`mt-4 flex h-[100px] cursor-pointer flex-col items-center justify-center rounded-input border border-dashed px-4 text-center transition-colors ${
            dragOver ? "border-lavender bg-white" : "border-fog bg-white"
          }`}
          onClick={() => inputRef.current?.click()}
        >
          <span className="text-[13px] tracking-body text-graphite">
            {uploading ? "Uploading…" : "Click or drop a policy PDF/photo here"}
          </span>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,image/jpeg,image/png,image/webp"
          className="sr-only"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onUpload(file);
          }}
        />
      </div>
    );
  }

  if (policyState === "processing") {
    return (
      <div className="rounded-card border border-fog bg-white p-6 shadow-panel md:p-8">
        <p className="text-[12px] font-medium uppercase tracking-[0.08em] text-ash">Policy Analysis</p>
        <p className="mt-2 text-[14px] tracking-body text-graphite">Processing your uploaded policy document…</p>
      </div>
    );
  }

  if (policyState === "failed") {
    return (
      <div className="rounded-card border border-fog bg-white p-6 shadow-panel md:p-8">
        <p className="text-[12px] font-medium uppercase tracking-[0.08em] text-ash">Policy Analysis</p>
        <p className="mt-2 text-[14px] tracking-body text-carbon">
          {errorMessage ?? "The uploaded policy document could not be processed."}
        </p>
        <div className="mt-3">
          <PillButton variant="ghost" size="sm" onClick={() => inputRef.current?.click()}>
            Try uploading again
          </PillButton>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,image/jpeg,image/png,image/webp"
          className="sr-only"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onUpload(file);
          }}
        />
      </div>
    );
  }

  // ready / needs_attention
  return (
    <div className="rounded-card border border-fog bg-white p-6 shadow-panel md:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-[12px] font-medium uppercase tracking-[0.08em] text-ash">Policy Analysis</p>
        {coverage && (
          <span className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-medium ${COVERAGE_TONE[coverage.overall_status]}`}>
            {COVERAGE_LABEL[coverage.overall_status]}
          </span>
        )}
      </div>

      {coverage && <p className="mt-3 text-[14px] leading-relaxed tracking-body text-graphite">{coverage.summary}</p>}

      <div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">
        {insurerName && (
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-ash">Insurer</p>
            <p className="mt-1 text-[14px] font-semibold tracking-body text-carbon">{insurerName}</p>
          </div>
        )}
        {policyNumberMasked && (
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-ash">Policy Number</p>
            <p className="mt-1 text-[14px] font-semibold tracking-body text-carbon">{policyNumberMasked}</p>
          </div>
        )}
        {policyType && (
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-ash">Policy Type</p>
            <p className="mt-1 text-[14px] font-semibold tracking-body text-carbon">{policyType}</p>
          </div>
        )}
        {coverageStart && (
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-ash">Coverage Start</p>
            <p className="mt-1 text-[14px] font-semibold tracking-body text-carbon">{formatPolicyDate(coverageStart)}</p>
          </div>
        )}
        {coverageEnd && (
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-ash">Coverage Expiry</p>
            <p className="mt-1 text-[14px] font-semibold tracking-body text-carbon">{formatPolicyDate(coverageEnd)}</p>
          </div>
        )}
        {deductibleInr != null && (
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-ash">Deductible</p>
            <p className="mt-1 text-[14px] font-semibold tracking-body text-carbon">{formatInr(deductibleInr)}</p>
          </div>
        )}
        {idvInr != null && (
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-ash">IDV</p>
            <p className="mt-1 text-[14px] font-semibold tracking-body text-carbon">{formatInr(idvInr)}</p>
          </div>
        )}
        {(policyVehicleMake || policyVehicleModel) && (
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-ash">Vehicle on Policy</p>
            <p className="mt-1 text-[14px] font-semibold tracking-body text-carbon">
              {[policyVehicleMake, policyVehicleModel, policyVehicleYear].filter(Boolean).join(" ")}
            </p>
          </div>
        )}
      </div>

      {exclusions.length > 0 && (
        <div className="mt-4">
          <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-ash">Exclusions on file</p>
          <ul className="mt-1.5 space-y-1">
            {exclusions.slice(0, 5).map((item, i) => (
              <li key={i} className="text-[13px] leading-relaxed tracking-body text-graphite">
                • {item}
              </li>
            ))}
          </ul>
        </div>
      )}

      {coverage && coverage.part_assessments.length > 0 && (
        <div className="mt-5 divide-y divide-fog border-t border-fog">
          {coverage.part_assessments.map((pa) => (
            <div key={pa.part} className="py-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-[13px] font-semibold tracking-body text-carbon">{pa.part}</p>
                <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ${COVERAGE_TONE[pa.coverage_status]}`}>
                  {COVERAGE_LABEL[pa.coverage_status]}
                </span>
              </div>
              <p className="mt-1 text-[12px] leading-relaxed tracking-body text-graphite">{pa.reason}</p>
              {pa.relevant_clauses.length > 0 && (
                <div className="mt-1.5 space-y-1">
                  {pa.relevant_clauses.slice(0, 1).map((clause, i) => (
                    <p key={i} className="text-[11px] italic leading-relaxed tracking-body text-ash">
                      {clause.page ? `p.${clause.page}` : ""}
                      {clause.section ? ` (${clause.section})` : ""}: {clause.excerpt.slice(0, 180)}
                      {clause.excerpt.length > 180 ? "…" : ""}
                    </p>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
