"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useSession } from "next-auth/react";
import { motion, useReducedMotion } from "framer-motion";
import { Reveal } from "@/components/ui/Reveal";
import { PillButton } from "@/components/ui/PillButton";
import { SignInAgainButton } from "@/components/ui/SignInAgainButton";
import { VehiclePlaceholder } from "@/components/dashboard/ClaimCard";
import { EASE } from "@/lib/motion";
import { loadClaimBundle } from "@/lib/claims/resultLoader";
import {
  downloadClaimReportPdf,
  getClaim,
  getClaimReport,
  getClaimTimeline,
  resolveAssetUrl,
  uploadPolicyDocument,
  userFacingMessage,
  type ClaimResponse,
  type TimelineStage,
  type UnifiedClaimReport,
} from "@/lib/api";
import {
  CLAIM_STATUS_DESCRIPTION,
  CLAIM_STATUS_LABEL,
  CLAIM_STATUS_TONE,
  formatInrRange,
  formatPartName,
} from "@/lib/formatting";
import { ClaimTimeline } from "./ClaimTimeline";
import { PolicyAnalysisPanel } from "./PolicyAnalysisPanel";
import { RiskSignalsPanel } from "./RiskSignalsPanel";

type LoadState = "loading" | "ready" | "error";

// Readiness polling while the claim is still `analyzing` (e.g. the user
// landed here from a dashboard link, or from the intake form's
// "still processing" state). Bounded so a claim stuck server-side doesn't
// poll forever — after the budget the page simply stops auto-refreshing.
const READINESS_POLL_INTERVAL_MS = 4_000;
const READINESS_POLL_LIMIT = 60; // × 4s = 4 minutes

// Quiet refetch cadence when the claim rendered but timeline/report were
// briefly unavailable (a "degraded" bundle — e.g. the post-analysis
// workflow was still committing when we arrived). Bounded: after the
// limit the page simply keeps what it has.
const DEGRADED_RETRY_INTERVAL_MS = 2_500;
const DEGRADED_RETRY_LIMIT = 6;

export function ClaimResultView({ claimId }: { claimId: string }) {
  const { data: session, status: sessionStatus } = useSession();
  const reducedMotion = useReducedMotion() ?? false;
  const [state, setState] = useState<LoadState>("loading");
  const [claim, setClaim] = useState<ClaimResponse | null>(null);
  const [report, setReport] = useState<UnifiedClaimReport | null>(null);
  const [timeline, setTimeline] = useState<TimelineStage[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  // 0 = network/backend-unreachable (see lib/api/client.ts's `request`,
  // which maps a thrown `fetch` into ApiError status 0). Drives which
  // recovery UI renders below (Task 11: a real 404 and an unreachable
  // backend must never look the same).
  const [errorStatus, setErrorStatus] = useState<number | null>(null);
  // True when the claim rendered but timeline/report weren't ready yet —
  // drives a bounded quiet refetch instead of a full-page error.
  const [degraded, setDegraded] = useState(false);
  const [uploadingPolicy, setUploadingPolicy] = useState(false);
  const [policyUploadError, setPolicyUploadError] = useState<string | null>(null);
  const [downloadingPdf, setDownloadingPdf] = useState(false);

  const load = useCallback(
    async (options?: { silent?: boolean }) => {
      // A silent refresh (readiness/degraded polling) must never flash the
      // page back to the loading skeleton, and a transient failure during
      // it must never replace an already-rendered claim with an error —
      // the next poll simply tries again.
      if (!options?.silent) setState("loading");
      const token = session?.backendAccessToken;
      try {
        // The loader retries transient failures itself (the production
        // bug: landing here moments after a reconciled analysis, while
        // the backend is still committing the post-analysis workflow, and
        // turning one blip into a terminal "Connection problem"). The
        // claim is the critical resource; timeline/report only degrade.
        const outcome = await loadClaimBundle({
          claimId,
          fetchClaim: () => getClaim(claimId, token),
          fetchTimeline: () => getClaimTimeline(claimId, token),
          fetchReport: () => getClaimReport(claimId, token),
          attempts: options?.silent ? 1 : undefined,
        });

        if (outcome.ok) {
          setClaim(outcome.bundle.claim);
          // Timeline/report only ever improve — a degraded refresh never
          // clears data an earlier load already rendered.
          if (outcome.bundle.timeline) setTimeline(outcome.bundle.timeline.stages);
          if (outcome.bundle.report) setReport(outcome.bundle.report);
          setDegraded(outcome.bundle.degraded);
          setState("ready");
          return;
        }
        if (options?.silent) return;
        setErrorMessage(outcome.message);
        setErrorStatus(outcome.status);
        setState("error");
      } catch (err) {
        // Non-ApiError = a programming error the loader deliberately
        // rethrows; show the stock failure rather than a blank page.
        if (options?.silent) return;
        setErrorMessage(userFacingMessage(err));
        setErrorStatus(null);
        setState("error");
      }
    },
    [claimId, session?.backendAccessToken]
  );

  useEffect(() => {
    // Wait for the session to resolve before the first fetch — otherwise
    // this fires once with no token (an avoidable 401) and again once
    // `useSession` settles and `load` picks up the real token.
    if (sessionStatus === "loading") return;
    // Backend token bootstrap still in progress (see lib/auth/callbacks.ts)
    // — stay on the loading state; `load` re-runs via its dependency once
    // the token lands on the session.
    if (sessionStatus === "authenticated" && session?.backendAuthPending) return;
    load();
  }, [load, sessionStatus, session?.backendAuthPending]);

  // While the claim is still analyzing server-side, keep checking
  // readiness quietly instead of presenting a half-empty report as final.
  // An interval (not a re-armed timeout) because a poll that finds the
  // status unchanged doesn't alter this effect's dependencies; the
  // cleanup runs — and polling stops — the moment the status moves on.
  const readinessPolls = useRef(0);
  useEffect(() => {
    if (state !== "ready" || claim?.status !== "analyzing") return;
    const interval = window.setInterval(() => {
      readinessPolls.current += 1;
      if (readinessPolls.current > READINESS_POLL_LIMIT) {
        window.clearInterval(interval);
        return;
      }
      load({ silent: true });
    }, READINESS_POLL_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [state, claim?.status, load]);

  // Degraded bundle: the claim rendered but timeline/report lagged behind
  // (typically the post-analysis workflow still committing). Refetch
  // quietly on an interval — same shape as the readiness poll above, and
  // for the same reason: a quiet retry that finds things unchanged doesn't
  // alter this effect's dependencies.
  const degradedRetries = useRef(0);
  useEffect(() => {
    if (state !== "ready" || !degraded) return;
    const interval = window.setInterval(() => {
      degradedRetries.current += 1;
      if (degradedRetries.current > DEGRADED_RETRY_LIMIT) {
        window.clearInterval(interval);
        return;
      }
      load({ silent: true });
    }, DEGRADED_RETRY_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [state, degraded, load]);

  async function handlePolicyUpload(file: File) {
    setUploadingPolicy(true);
    setPolicyUploadError(null);
    try {
      await uploadPolicyDocument(claimId, file, session?.backendAccessToken);
      await load();
    } catch (err) {
      setPolicyUploadError(userFacingMessage(err));
    } finally {
      setUploadingPolicy(false);
    }
  }

  async function handleDownloadPdf() {
    setDownloadingPdf(true);
    try {
      const blob = await downloadClaimReportPdf(claimId, session?.backendAccessToken);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${claimId}-report.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch {
      // Non-critical action — a failed download doesn't disrupt the rest
      // of the page, so this stays a quiet no-op rather than a full-page error.
    } finally {
      setDownloadingPdf(false);
    }
  }

  if (state === "loading") {
    // Visually continuous with both the intake form's "Preparing your
    // assessment report" bridge and this route's loading.tsx — arriving
    // here from a completed analysis reads as one uninterrupted state,
    // not a hard swap to a bare spinner.
    return (
      <motion.div
        initial={reducedMotion ? false : { opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={reducedMotion ? { duration: 0 } : { duration: 0.4, ease: EASE }}
        className="mx-auto flex min-h-screen max-w-content flex-col items-center justify-center px-6"
      >
        <span
          className={`h-5 w-5 rounded-full border-2 border-fog border-t-lavender ${
            reducedMotion ? "" : "animate-spin"
          }`}
          aria-hidden
        />
        <div className="mt-5 text-center">
          <p className="text-[15px] font-medium tracking-body text-carbon">
            Preparing your assessment report
          </p>
          <p className="mt-1.5 text-[13px] tracking-body text-ash">{claimId}</p>
        </div>
      </motion.div>
    );
  }

  if (state === "error" || !claim) {
    // A genuine 404/403 is definitive — retrying re-fetches the exact
    // same outcome, so those only ever offer navigation, never a retry
    // button. A 401 is also unfixable by retrying (the session has no
    // usable backend token) — its one repair is a fresh Google sign-in.
    // Anything else (network failure, 5xx) is transient, so that path
    // keeps the bounded, user-triggered "Try again" instead.
    const isDefinitive = errorStatus === 404 || errorStatus === 403 || errorStatus === 401;
    const title =
      errorStatus === 404
        ? "Claim not found"
        : errorStatus === 403
          ? "Access denied"
          : errorStatus === 401
            ? "Session expired"
            : "Connection problem";

    return (
      <div className="mx-auto flex min-h-screen max-w-content flex-col items-center justify-center gap-6 px-6 text-center">
        <p className="text-[18px] font-medium tracking-heading text-carbon">{title}</p>
        <p className="max-w-copy text-[15px] tracking-body text-graphite">{errorMessage}</p>
        <div className="flex items-center gap-4">
          {errorStatus === 401 && <SignInAgainButton variant="ghost" />}
          {!isDefinitive && (
            <PillButton onClick={load} variant="ghost">
              Try again
            </PillButton>
          )}
          <Link href="/dashboard" className="text-[14px] font-medium text-graphite hover:text-carbon">
            Back to Dashboard
          </Link>
          <Link href="/claims/new" className="text-[14px] font-medium text-graphite hover:text-carbon">
            Start New Assessment
          </Link>
        </div>
      </div>
    );
  }

  const parts = claim.ai_assessment?.damaged_parts ?? [];
  const summary = claim.ai_assessment?.summary;
  const pricing = claim.pricing_assessment;
  const policyStage = timeline.find((s) => s.key === "policy_processed");
  const policyState =
    claim.coverage_analysis?.overall_status === "potential_exclusion" ||
    claim.coverage_analysis?.overall_status === "manual_review" ||
    claim.coverage_analysis?.overall_status === "unclear"
      ? "needs_attention"
      : policyStage?.status === "complete"
        ? "ready"
        : policyStage?.status === "in_progress"
          ? "processing"
          : policyStage?.status === "needs_attention"
            ? "failed"
            : "not_available";

  return (
    <motion.div
      initial={reducedMotion ? false : { opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={reducedMotion ? { duration: 0 } : { duration: 0.55, ease: EASE }}
      className="mx-auto max-w-content px-6 pb-24 pt-32 md:px-8"
    >
      <Reveal>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-[12px] font-medium uppercase tracking-[0.08em] text-ash">Claim</p>
            <h1 className="mt-1 text-[26px] font-semibold tracking-heading text-carbon">{claim.id}</h1>
          </div>
          <div className="flex items-center gap-3">
            <span
              className={`inline-flex rounded-full px-3.5 py-1.5 text-[13px] font-medium ${CLAIM_STATUS_TONE[claim.status]}`}
            >
              {CLAIM_STATUS_LABEL[claim.status]}
            </span>
            <PillButton variant="ghost" size="sm" onClick={handleDownloadPdf} disabled={downloadingPdf}>
              {downloadingPdf ? "Preparing…" : "Download Report (PDF)"}
            </PillButton>
          </div>
        </div>
        <p className="mt-3 max-w-copy text-[15px] leading-relaxed tracking-body text-graphite">
          {CLAIM_STATUS_DESCRIPTION[claim.status]}
        </p>
      </Reveal>

      {claim.status === "analyzing" && (
        <Reveal className="mt-8">
          <div className="flex items-start gap-3.5 rounded-card border border-fog bg-white p-6 shadow-panel">
            <span
              className={`mt-0.5 h-4 w-4 shrink-0 rounded-full border-2 border-fog border-t-lavender ${
                reducedMotion ? "" : "animate-spin"
              }`}
              aria-hidden
            />
            <div>
              <p className="text-[14px] font-medium tracking-body text-carbon">
                Preparing your assessment report
              </p>
              <p className="mt-1 text-[13px] leading-relaxed tracking-body text-graphite">
                The analysis is still running. This page checks automatically and will show the
                full report as soon as it&apos;s ready.
              </p>
            </div>
          </div>
        </Reveal>
      )}

      <Reveal delay={0.05} className="mt-10">
        <div className="rounded-card border border-fog bg-white p-6 shadow-panel md:p-8">
          <p className="text-[12px] font-medium uppercase tracking-[0.08em] text-ash">Vehicle</p>
          <div className="mt-4 flex flex-col gap-6 md:flex-row md:items-center">
            <div className="relative aspect-[16/10] w-full shrink-0 overflow-hidden rounded-input bg-mist/40 md:w-[260px]">
              {claim.vehicle_reference_image ? (
                <Image
                  src={resolveAssetUrl(claim.vehicle_reference_image.url)}
                  alt={`Reference vehicle image: ${[claim.vehicle_make, claim.vehicle_model].filter(Boolean).join(" ") || claim.vehicle_type}`}
                  fill
                  unoptimized
                  className={
                    claim.vehicle_reference_image.source === "category_fallback"
                      ? "object-contain p-5"
                      : "object-cover"
                  }
                />
              ) : (
                <VehiclePlaceholder />
              )}
            </div>
            <div className="grid flex-1 grid-cols-2 gap-x-4 gap-y-4 sm:grid-cols-4 md:grid-cols-2 lg:grid-cols-4">
              <Field label="Category" value={claim.vehicle_type} />
              <Field label="Make" value={claim.vehicle_make ?? "—"} />
              <Field label="Model" value={claim.vehicle_model ?? "—"} />
              <Field label="Year" value={claim.vehicle_year ? String(claim.vehicle_year) : "—"} />
            </div>
          </div>
          <p className="mt-4 text-[11px] tracking-body text-ash">
            Reference image of this model line — not the submitted damage photos.
          </p>
        </div>
      </Reveal>

      {summary && (
        <Reveal delay={0.1} className="mt-6">
          <div className="rounded-card border border-fog bg-white p-6 shadow-panel md:p-8">
            <p className="text-[12px] font-medium uppercase tracking-[0.08em] text-ash">
              Assessment summary
            </p>
            <div className="mt-3 grid grid-cols-3 gap-4">
              <Field label="Damaged parts" value={String(summary.total_parts)} />
              <Field label="Accepted" value={String(summary.accepted)} />
              <Field label="Review required" value={String(summary.review_required)} />
            </div>
          </div>
        </Reveal>
      )}

      {pricing && (
        <Reveal delay={0.15} className="mt-6">
          <div className="rounded-card border border-fog bg-white p-6 shadow-panel md:p-8">
            <p className="text-[12px] font-medium uppercase tracking-[0.08em] text-ash">
              Preliminary Cost Estimate
            </p>
            <p className="mt-2 text-[28px] font-semibold tracking-heading text-carbon">
              {pricing.parts_priced > 0
                ? formatInrRange(pricing.total_min_inr, pricing.total_max_inr)
                : "Pending manual inspection"}
            </p>
            <p className="mt-2 text-[13px] tracking-body text-graphite">
              {pricing.parts_priced > 0
                ? `Estimate covers ${pricing.parts_priced} assessed part${pricing.parts_priced === 1 ? "" : "s"}.`
                : "No parts have a confident estimate yet."}
              {pricing.parts_pending_manual_inspection > 0 &&
                ` ${pricing.parts_pending_manual_inspection} additional part${
                  pricing.parts_pending_manual_inspection === 1 ? "" : "s"
                } require manual inspection.`}
            </p>
            <p className="mt-3 text-[11px] leading-relaxed tracking-body text-ash">
              Indicative estimate only — actual repair costs vary with location, workshop,
              parts availability, taxes, labour, and vehicle condition. Not a final quotation.
            </p>
          </div>
        </Reveal>
      )}

      {parts.length > 0 && (
        <Reveal delay={0.2} className="mt-6">
          <div className="rounded-card border border-fog bg-white p-6 shadow-panel md:p-8">
            <p className="text-[12px] font-medium uppercase tracking-[0.08em] text-ash">
              Damaged parts
            </p>
            <div className="mt-4 divide-y divide-fog">
              {parts.map((part) => {
                const cost = pricing?.per_part[part.part] ?? null;
                const isReviewRequired = part.status === "Review Required";
                return (
                  <div
                    key={`${part.part}-${part.detected_in_images.join(",")}`}
                    className="grid grid-cols-2 gap-y-2 py-4 sm:grid-cols-5 sm:items-center sm:gap-4"
                  >
                    <div className="sm:col-span-2">
                      <p className="text-[14px] font-semibold tracking-body text-carbon">
                        {formatPartName(part.part)}
                      </p>
                      <p className="text-[12px] tracking-body text-ash">
                        {part.severity} · {Math.round(part.damage_percentage)}% damage
                      </p>
                    </div>
                    <div>
                      <span
                        className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-medium ${
                          isReviewRequired ? "bg-[#fff2df] text-amber" : "bg-mint-wash text-mint"
                        }`}
                      >
                        {part.status}
                      </span>
                    </div>
                    <div>
                      <p className="text-[13px] tracking-body text-graphite">
                        {part.recommended_action}
                      </p>
                    </div>
                    <div className="text-right sm:text-left">
                      <p className="text-[13px] font-medium tracking-body text-carbon">
                        {cost ? formatInrRange(cost.min_inr, cost.max_inr) : "Manual Inspection Required"}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </Reveal>
      )}

      <Reveal delay={0.22} className="mt-6">
        <PolicyAnalysisPanel
          policyState={policyState}
          errorMessage={policyUploadError ?? policyStage?.detail}
          coverage={claim.coverage_analysis}
          deductibleInr={report?.policy.deductible_inr ?? null}
          idvInr={report?.policy.idv_inr ?? null}
          exclusions={report?.policy.exclusions ?? []}
          uploading={uploadingPolicy}
          onUpload={handlePolicyUpload}
          policyType={report?.policy.policy_type}
          insurerName={report?.policy.insurer_name}
          policyNumberMasked={report?.policy.policy_number_masked}
          coverageStart={report?.policy.coverage_start}
          coverageEnd={report?.policy.coverage_end}
          policyVehicleMake={report?.policy.policy_vehicle_make}
          policyVehicleModel={report?.policy.policy_vehicle_model}
          policyVehicleYear={report?.policy.policy_vehicle_year}
        />
      </Reveal>

      {claim.risk_assessment && (
        <Reveal delay={0.24} className="mt-6">
          <RiskSignalsPanel risk={claim.risk_assessment} />
        </Reveal>
      )}

      {report?.summary && (
        <Reveal delay={0.26} className="mt-6">
          <div className="rounded-card border border-fog bg-white p-6 shadow-panel md:p-8">
            <p className="text-[12px] font-medium uppercase tracking-[0.08em] text-ash">Claim Summary</p>
            <p className="mt-2 text-[14px] leading-relaxed tracking-body text-graphite">{report.summary}</p>
          </div>
        </Reveal>
      )}

      {timeline.length > 0 && (
        <Reveal delay={0.28} className="mt-6">
          <ClaimTimeline stages={timeline} />
        </Reveal>
      )}
    </motion.div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-ash">{label}</p>
      <p className="mt-1 text-[14px] font-semibold tracking-body text-carbon">{value}</p>
    </div>
  );
}
