"use client";

import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { AnimatePresence, motion } from "framer-motion";
import { PillButton } from "@/components/ui/PillButton";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { Reveal } from "@/components/ui/Reveal";
import { UploadField } from "@/components/ui/UploadField";
import { SearchableSelect } from "@/components/ui/SearchableSelect";
import { SignInAgainButton } from "@/components/ui/SignInAgainButton";
import { EASE } from "@/lib/motion";
import {
  ApiError,
  createClaim,
  analyzeClaim,
  isSupportedImageFile,
  listVehicleManufacturers,
  listVehicleModels,
  uploadPolicyDocument,
  userFacingMessage,
  type VehicleCatalogModel,
  type VehicleManufacturer,
} from "@/lib/api";

// Mirrors the backend's real accepted formats
// (`ALLOWED_CONTENT_TYPES` in `backend/app/services/policy/service.py`) —
// never claim support for a format the backend would reject.
const POLICY_ACCEPT = "application/pdf,image/jpeg,image/png,image/webp";
function isSupportedPolicyFile(file: File): boolean {
  return ["application/pdf", "image/jpeg", "image/png", "image/webp"].includes(file.type);
}

type Phase = "form" | "creating" | "analyzing" | "error";

// Truthful, sequential stage messages mirroring what the backend +
// ai-service genuinely do during one /analyze request (upload →
// vehicle-presence validation → YOLO damage analysis → part matching →
// category-aware pricing → persistence). Not tied to a live progress
// signal (the current API has no progress endpoint), so these advance on
// a timer and hold at the last stage — never a fabricated percentage.
const ANALYSIS_STAGES = [
  "Uploading images",
  "Validating vehicle photos",
  "Analyzing visible damage",
  "Matching damaged vehicle parts",
  "Preparing repair estimate",
  "Finalizing assessment",
];

const STAGE_INTERVAL_MS = 2200;

// Mirrors the backend contract (`ClaimCreateRequest` in
// `backend/app/schemas/claim_api.py`) — never stricter than it.
const MIN_VEHICLE_YEAR = 1980;
const MAX_VEHICLE_YEAR = new Date().getFullYear() + 1;

export function ClaimIntakeForm() {
  const router = useRouter();
  const { data: session, status: sessionStatus } = useSession();

  // Backend-auth state machine (see lib/auth/callbacks.ts):
  // - reauth: no backend token AND no way to obtain one server-side —
  //   every claim request would 401, so block submission and offer the one
  //   real repair (a fresh Google sign-in).
  // - pending: session still resolving, or the server-side token exchange
  //   hasn't succeeded yet but retries on upcoming session reads — a brief
  //   wait state, never a re-login prompt.
  const needsBackendReauth =
    sessionStatus === "authenticated" && session?.needsBackendReauth === true;
  const backendAuthPending =
    sessionStatus === "loading" ||
    (sessionStatus === "authenticated" && !session?.backendAccessToken && !needsBackendReauth);

  const [manufacturers, setManufacturers] = useState<VehicleManufacturer[]>([]);
  const [manufacturersLoading, setManufacturersLoading] = useState(true);
  const [manufacturersError, setManufacturersError] = useState(false);
  const [manufacturerId, setManufacturerId] = useState<string | null>(null);

  const [models, setModels] = useState<VehicleCatalogModel[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelId, setModelId] = useState<string | null>(null);

  const [vehicleYear, setVehicleYear] = useState("");

  // Loaded once — the catalog is public reference data shared by every
  // caller (see backend/app/api/routes/vehicle_catalog.py).
  useEffect(() => {
    let cancelled = false;
    listVehicleManufacturers()
      .then((result) => {
        if (!cancelled) setManufacturers(result);
      })
      .catch(() => {
        if (!cancelled) setManufacturersError(true);
      })
      .finally(() => {
        if (!cancelled) setManufacturersLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Changing manufacturer clears the selected model — a model id from a
  // different manufacturer's list is never valid here.
  useEffect(() => {
    setModelId(null);
    if (!manufacturerId) {
      setModels([]);
      return;
    }
    let cancelled = false;
    setModelsLoading(true);
    listVehicleModels(manufacturerId)
      .then((result) => {
        if (!cancelled) setModels(result);
      })
      .catch(() => {
        if (!cancelled) setModels([]);
      })
      .finally(() => {
        if (!cancelled) setModelsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [manufacturerId]);

  const selectedManufacturer = manufacturers.find((mf) => mf.id === manufacturerId) ?? null;
  const selectedModel = models.find((mdl) => mdl.id === modelId) ?? null;

  const [images, setImages] = useState<File[]>([]);
  const [rejectedCount, setRejectedCount] = useState(0);

  const [policyFile, setPolicyFile] = useState<File | null>(null);
  const [policyFileRejected, setPolicyFileRejected] = useState(false);

  const [phase, setPhase] = useState<Phase>("form");
  // Set once the claim is created; a retry after an analyze failure
  // reuses this id instead of calling createClaim again.
  const [claimId, setClaimId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  // HTTP status of the last failure — a 401 renders a sign-in action,
  // since resubmitting the same unauthenticated request can never succeed.
  const [errorStatus, setErrorStatus] = useState<number | null>(null);
  const [stageIndex, setStageIndex] = useState(0);

  const stageTimer = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (stageTimer.current) window.clearInterval(stageTimer.current);
    };
  }, []);

  function handleImages(e: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    const accepted = files.filter(isSupportedImageFile);
    // Append to (never replace) the current selection, de-duplicated by
    // name+size — picking a second batch must not silently drop the first.
    setImages((current) => {
      const seen = new Set(current.map((f) => `${f.name}|${f.size}`));
      return [...current, ...accepted.filter((f) => !seen.has(`${f.name}|${f.size}`))];
    });
    setRejectedCount(files.length - accepted.length);
    // Reset the input so selecting the same file again re-fires onChange.
    e.target.value = "";
  }

  function removeImage(index: number) {
    setImages((current) => current.filter((_, i) => i !== index));
  }

  function formatFileSize(bytes: number): string {
    if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }

  function handlePolicyFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    if (file && !isSupportedPolicyFile(file)) {
      setPolicyFile(null);
      setPolicyFileRejected(true);
      return;
    }
    setPolicyFile(file);
    setPolicyFileRejected(false);
  }

  function startStageCycle() {
    setStageIndex(0);
    stageTimer.current = window.setInterval(() => {
      setStageIndex((i) => Math.min(i + 1, ANALYSIS_STAGES.length - 1));
    }, STAGE_INTERVAL_MS);
  }

  function stopStageCycle() {
    if (stageTimer.current) {
      window.clearInterval(stageTimer.current);
      stageTimer.current = null;
    }
  }

  async function runAnalysis(idToAnalyze: string) {
    setPhase("analyzing");
    setErrorMessage(null);
    setErrorStatus(null);
    startStageCycle();
    try {
      const result = await analyzeClaim(idToAnalyze, images, session?.backendAccessToken);
      stopStageCycle();
      router.push(`/claims/${result.id}`);
    } catch (err) {
      stopStageCycle();
      setErrorMessage(userFacingMessage(err));
      setErrorStatus(err instanceof ApiError ? err.status : null);
      setPhase("error");
    }
  }

  const parsedYear = Number(vehicleYear);
  const hasValidYear =
    vehicleYear.trim() !== "" &&
    Number.isInteger(parsedYear) &&
    parsedYear >= MIN_VEHICLE_YEAR &&
    parsedYear <= MAX_VEHICLE_YEAR;
  const hasNoImages = images.length === 0;
  const missingMake = selectedManufacturer === null;
  const missingModel = selectedModel === null;
  const missingYear = !hasValidYear;
  const hasMissingRequiredFields = missingMake || missingModel || missingYear || hasNoImages;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (phase === "creating" || phase === "analyzing") return;
    // The reauth banner / pending note already explain these states —
    // never fire a claim request without a usable backend token.
    if (needsBackendReauth || backendAuthPending) return;

    if (hasMissingRequiredFields || !selectedManufacturer || !selectedModel) {
      setErrorMessage(
        hasNoImages
          ? "Select at least one damage photo to continue."
          : "Select a manufacturer, model, and a valid manufacture year to continue."
      );
      setPhase("error");
      return;
    }

    // A claim id already exists from a previous attempt on this
    // submission — re-analyze it rather than creating a second claim.
    if (claimId) {
      await runAnalysis(claimId);
      return;
    }

    setErrorMessage(null);
    setErrorStatus(null);
    setPhase("creating");
    try {
      const claim = await createClaim(
        {
          vehicle_type: selectedModel.category,
          vehicle_make: selectedManufacturer.name,
          vehicle_model: selectedModel.name,
          vehicle_year: parsedYear,
        },
        session?.backendAccessToken
      );
      setClaimId(claim.id);

      // Fired but not awaited — a slow OCR/extraction pass, or the
      // document failing to process, must never delay or block
      // navigation to the completed damage assessment. Any outcome
      // (including failure) is visible on the claim page's own Policy
      // Analysis panel once it lands there.
      if (policyFile) {
        uploadPolicyDocument(claim.id, policyFile, session?.backendAccessToken).catch(() => {});
      }

      await runAnalysis(claim.id);
    } catch (err) {
      setErrorMessage(userFacingMessage(err));
      setErrorStatus(err instanceof ApiError ? err.status : null);
      setPhase("error");
    }
  }

  const busy = phase === "creating" || phase === "analyzing";
  const vehicleFieldsLocked = busy || Boolean(claimId);

  return (
    <section className="relative bg-white">
      <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute left-1/2 top-[4%] h-[420px] w-[680px] -translate-x-1/2 rounded-full bg-lavender/[0.1] blur-[130px]" />
      </div>
      <div className="relative mx-auto flex min-h-screen max-w-content flex-col items-center justify-center px-6 pb-24 pt-32 md:px-8">
        <Reveal className="text-center">
          <SectionLabel>New claim</SectionLabel>
        </Reveal>
        <Reveal delay={0.1} className="text-center">
          <h1 className="mx-auto mt-6 max-w-[680px] text-balance text-[34px] font-semibold leading-[1.12] tracking-display text-carbon sm:text-[44px] md:text-[54px]">
            Submit vehicle damage for assessment.
          </h1>
        </Reveal>
        <Reveal delay={0.18} className="text-center">
          <p className="mx-auto mt-6 max-w-copy text-[16px] leading-relaxed tracking-body text-graphite">
            Enter the vehicle details and upload damage photos — ClaimSight will detect affected
            parts and estimate a preliminary repair cost.
          </p>
        </Reveal>

        <Reveal delay={0.2} className="w-full">
          <form
            onSubmit={handleSubmit}
            className="mx-auto mt-14 w-full max-w-[820px] rounded-card border border-fog bg-white p-6 shadow-panel md:p-10"
          >
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
              <div>
                <SearchableSelect
                  id="vehicle_manufacturer"
                  label="Manufacturer"
                  placeholder="Search or select manufacturer"
                  value={manufacturerId}
                  onChange={setManufacturerId}
                  disabled={vehicleFieldsLocked}
                  loading={manufacturersLoading}
                  emptyMessage={manufacturersError ? "Couldn't load manufacturers." : "No results."}
                  options={manufacturers.map((mf) => ({
                    id: mf.id,
                    label: mf.name,
                    badge: mf.status === "historical" ? "Discontinued in India" : null,
                  }))}
                />
              </div>

              <div>
                <SearchableSelect
                  id="vehicle_model"
                  label="Model"
                  placeholder={manufacturerId ? "Search or select model" : "Select a manufacturer first"}
                  value={modelId}
                  onChange={setModelId}
                  disabled={vehicleFieldsLocked || !manufacturerId}
                  loading={modelsLoading}
                  emptyMessage="No results."
                  options={models.map((mdl) => ({
                    id: mdl.id,
                    label: mdl.name,
                    badge: mdl.status === "discontinued" ? "Discontinued" : null,
                  }))}
                />
              </div>

              <div>
                <label
                  htmlFor="vehicle_year"
                  className="block text-[12px] font-medium uppercase tracking-[0.08em] text-graphite"
                >
                  Manufacture year
                </label>
                <input
                  id="vehicle_year"
                  type="number"
                  inputMode="numeric"
                  required
                  value={vehicleYear}
                  onChange={(e) => setVehicleYear(e.target.value)}
                  disabled={vehicleFieldsLocked}
                  placeholder="e.g. 2023"
                  className="mt-3 w-full rounded-input border border-fog bg-white px-4 py-3 text-[15px] tracking-body text-carbon placeholder:text-ash focus:border-lavender focus:outline-none focus:ring-2 focus:ring-lavender/20 disabled:opacity-60"
                />
                {missingYear && vehicleYear.trim() !== "" && (
                  <p className="mt-1.5 text-[12px] text-ash">
                    Enter a year between {MIN_VEHICLE_YEAR} and {MAX_VEHICLE_YEAR}.
                  </p>
                )}
              </div>

              <div>
                <label className="block text-[12px] font-medium uppercase tracking-[0.08em] text-graphite">
                  Vehicle category
                </label>
                <div className="mt-3 w-full rounded-input border border-fog bg-mist/40 px-4 py-3 text-[15px] tracking-body text-carbon">
                  {selectedModel ? selectedModel.category : "Detected from the selected model"}
                </div>
              </div>
            </div>

            <div className="mt-6">
              <UploadField
                label="Damage photos"
                hint={
                  images.length
                    ? `${images.length} photo${images.length === 1 ? "" : "s"} selected — click to add more`
                    : "Click to upload one or more photos"
                }
                accept="image/jpeg,image/png,image/webp"
                multiple
                disabled={vehicleFieldsLocked}
                onChange={handleImages}
              />
              {images.length > 0 && (
                <ul className="mt-3 flex flex-wrap gap-2">
                  {images.map((file, index) => (
                    <li
                      key={`${file.name}|${file.size}`}
                      className="inline-flex max-w-full items-center gap-2 rounded-full border border-fog bg-mist/40 py-1 pl-3 pr-1.5 text-[12px] tracking-body text-graphite"
                    >
                      <span className="max-w-[220px] truncate">{file.name}</span>
                      <span className="shrink-0 text-ash">{formatFileSize(file.size)}</span>
                      <button
                        type="button"
                        onClick={() => removeImage(index)}
                        disabled={vehicleFieldsLocked}
                        aria-label={`Remove ${file.name}`}
                        className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-ash transition-colors hover:bg-fog hover:text-carbon disabled:opacity-50"
                      >
                        ×
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {rejectedCount > 0 && (
                <p className="mt-2 text-[13px] text-ember">
                  {rejectedCount} file(s) were skipped — only JPEG, PNG, or WebP images are
                  supported.
                </p>
              )}
              {hasNoImages && (
                <p className="mt-2 text-[13px] text-ash">
                  Select at least one damage photo before starting the assessment.
                </p>
              )}
            </div>

            <div className="mt-8 border-t border-fog pt-8">
              <p className="text-[12px] font-medium uppercase tracking-[0.08em] text-graphite">
                Insurance Policy <span className="text-ash">— Optional</span>
              </p>
              <p className="mt-2 max-w-copy text-[13px] leading-relaxed tracking-body text-graphite">
                Attach your policy document to include coverage analysis in the claim report.
              </p>
              <div className="mt-4">
                <UploadField
                  label="Policy document"
                  hint={policyFile ? policyFile.name : "Click to upload a PDF or photo of your policy"}
                  accept={POLICY_ACCEPT}
                  disabled={vehicleFieldsLocked}
                  onChange={handlePolicyFile}
                />
                {policyFileRejected && (
                  <p className="mt-2 text-[13px] text-ember">
                    Unsupported file — only PDF, JPEG, PNG, or WebP files are supported.
                  </p>
                )}
                {policyFile && (
                  <button
                    type="button"
                    onClick={() => {
                      setPolicyFile(null);
                      setPolicyFileRejected(false);
                    }}
                    disabled={vehicleFieldsLocked}
                    className="mt-2 text-[12px] font-medium text-graphite underline decoration-fog underline-offset-2 hover:text-carbon disabled:opacity-60"
                  >
                    Remove policy document
                  </button>
                )}
              </div>
            </div>

            {needsBackendReauth && (
              <div className="mt-8 rounded-input border border-ember/25 bg-ember/[0.06] px-4 py-4 text-center">
                <p className="text-[14px] tracking-body text-ember">
                  Your session has expired. Sign in again to submit a claim.
                </p>
                <div className="mt-3 flex justify-center">
                  <SignInAgainButton size="sm" />
                </div>
              </div>
            )}

            <div className="mt-8 flex justify-center">
              <PillButton
                type="submit"
                size="lg"
                disabled={busy || hasMissingRequiredFields || needsBackendReauth || backendAuthPending}
              >
                {phase === "creating"
                  ? "Creating claim…"
                  : phase === "analyzing"
                    ? "Analyzing…"
                    : claimId
                      ? "Retry analysis"
                      : "Analyze claim"}
              </PillButton>
            </div>

            {backendAuthPending && (
              <p className="mt-4 text-center text-[13px] tracking-body text-ash">
                Preparing your session…
              </p>
            )}

            <AnimatePresence>
              {phase === "analyzing" && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.6, ease: EASE }}
                  className="overflow-hidden"
                >
                  <div className="mt-10 border-t border-fog pt-8">
                    <ul className="mx-auto flex w-fit flex-col gap-2.5">
                      {ANALYSIS_STAGES.map((stage, index) => (
                        <li key={stage} className="flex items-center gap-2.5">
                          {index < stageIndex ? (
                            <span className="flex h-4 w-4 items-center justify-center text-[11px] text-mint">✓</span>
                          ) : index === stageIndex ? (
                            <span className="flex h-4 w-4 items-center justify-center">
                              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-lavender" />
                            </span>
                          ) : (
                            <span className="flex h-4 w-4 items-center justify-center">
                              <span className="h-1 w-1 rounded-full bg-fog" />
                            </span>
                          )}
                          <span
                            className={`text-[13px] tracking-body ${
                              index === stageIndex
                                ? "font-medium text-carbon"
                                : index < stageIndex
                                  ? "text-graphite"
                                  : "text-ash"
                            }`}
                          >
                            {stage}
                          </span>
                        </li>
                      ))}
                    </ul>
                    <p className="mt-5 text-center text-[12px] tracking-body text-ash">
                      Analysis usually completes within a minute. Keep this page open.
                    </p>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <AnimatePresence>
              {phase === "error" && errorMessage && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.4, ease: EASE }}
                  className="overflow-hidden"
                >
                  <div className="mt-8 rounded-input border border-ember/25 bg-ember/[0.06] px-4 py-3 text-center">
                    <p className="text-[14px] tracking-body text-ember">{errorMessage}</p>
                    {errorStatus === 401 && (
                      <div className="mt-3 flex justify-center">
                        <SignInAgainButton size="sm" />
                      </div>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </form>
        </Reveal>
      </div>
    </section>
  );
}
