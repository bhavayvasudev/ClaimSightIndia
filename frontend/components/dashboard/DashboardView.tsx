"use client";

import { useCallback, useEffect, useState } from "react";
import Image from "next/image";
import { useSession } from "next-auth/react";
import { PillButton } from "@/components/ui/PillButton";
import { Reveal } from "@/components/ui/Reveal";
import { SignInAgainButton } from "@/components/ui/SignInAgainButton";
import { ApiError, listClaims, userFacingMessage, type ClaimListItem } from "@/lib/api";
import {
  STATUS_GROUP,
  STATUS_GROUP_LABEL,
  STATUS_GROUP_ORDER,
  claimsForFilter,
  type DashboardFilter,
  type StatusGroup,
} from "@/lib/claimStatusGroups";
import { ClaimCard } from "./ClaimCard";

type LoadState = "loading" | "ready" | "error";

/**
 * Real backend data only — no mock claim cards, no hardcoded metrics.
 * Every count and card here comes from `GET /claims`, scoped server-side
 * to the signed-in user (see `backend/app/api/routes/claims.py:list_claims`).
 */
type FilterValue = DashboardFilter;

export function DashboardView() {
  const { data: session, status: sessionStatus } = useSession();
  const [state, setState] = useState<LoadState>("loading");
  const [items, setItems] = useState<ClaimListItem[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  // A 401 means the session has no usable backend token — retrying the
  // same request can never succeed, so it gets a sign-in action instead
  // of the "Try again" button transient failures get.
  const [errorStatus, setErrorStatus] = useState<number | null>(null);
  const [filter, setFilter] = useState<FilterValue>("all");

  const load = useCallback(async () => {
    setState("loading");
    try {
      const result = await listClaims(session?.backendAccessToken);
      setItems(result.items);
      setState("ready");
    } catch (err) {
      setErrorMessage(userFacingMessage(err));
      setErrorStatus(err instanceof ApiError ? err.status : null);
      setState("error");
    }
  }, [session?.backendAccessToken]);

  useEffect(() => {
    // Wait for the session to resolve first — otherwise this fires once
    // with no token (an avoidable 401) before `load` picks up the real one.
    if (sessionStatus === "loading") return;
    // Backend token bootstrap still in progress (see lib/auth/callbacks.ts)
    // — stay on the loading state; `load` re-runs via its dependency once
    // the token lands on the session.
    if (sessionStatus === "authenticated" && session?.backendAuthPending) return;
    load();
  }, [load, sessionStatus, session?.backendAuthPending]);

  const firstName = session?.user?.name?.split(" ")[0];

  const counts: Record<StatusGroup, number> = {
    active: 0,
    under_review: 0,
    completed: 0,
    failed: 0,
  };
  for (const item of items) {
    counts[STATUS_GROUP[item.status]] += 1;
  }

  // Failed claims live only in the Failed tab — the default feed and
  // its "All Claims" count exclude them (see lib/claimStatusGroups.ts).
  const filteredItems = claimsForFilter(items, filter);
  const defaultFeedCount = items.length - counts.failed;

  return (
    <div className="mx-auto max-w-content px-6 pb-24 pt-32 md:px-8">
      <Reveal>
        <div className="flex flex-wrap items-center gap-4">
          {session?.user?.image && (
            <Image
              src={session.user.image}
              alt=""
              width={48}
              height={48}
              className="rounded-full"
              unoptimized
            />
          )}
          <div>
            <h1 className="text-[26px] font-semibold tracking-heading text-carbon">
              Welcome back{firstName ? `, ${firstName}` : ""}
            </h1>
            <p className="mt-1 text-[14px] tracking-body text-graphite">
              Track your vehicle assessments and review claim activity.
            </p>
          </div>
        </div>
      </Reveal>

      {state === "loading" && (
        <div aria-label="Loading your claims" className="mt-10">
          <div className="hidden gap-3 md:grid md:grid-cols-5">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-[86px] animate-pulse rounded-card border border-fog bg-mist/50" />
            ))}
          </div>
          <div className="mt-10 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="overflow-hidden rounded-card border border-fog bg-white">
                <div className="aspect-[16/10] w-full animate-pulse bg-mist/60" />
                <div className="space-y-3 p-5">
                  <div className="h-4 w-2/3 animate-pulse rounded bg-mist" />
                  <div className="h-3 w-1/3 animate-pulse rounded bg-mist/70" />
                  <div className="h-3 w-1/2 animate-pulse rounded bg-mist/70" />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {state === "error" && (
        <div className="mt-16 flex flex-col items-center gap-4 text-center">
          <p className="text-[14px] tracking-body text-carbon">{errorMessage}</p>
          {errorStatus === 401 ? (
            <SignInAgainButton variant="ghost" />
          ) : (
            <PillButton onClick={load} variant="ghost">
              Try again
            </PillButton>
          )}
        </div>
      )}

      {state === "ready" && items.length === 0 && (
        <Reveal delay={0.1}>
          <div className="mt-16 flex flex-col items-center gap-4 rounded-card border border-fog bg-mist/30 px-6 py-20 text-center">
            <p className="text-[18px] font-medium tracking-heading text-carbon">No assessments yet.</p>
            <p className="max-w-[360px] text-[14px] leading-relaxed tracking-body text-graphite">
              Upload vehicle damage photos to create your first assessment.
            </p>
            <PillButton href="/claims/new" size="md">
              Start Assessment
            </PillButton>
          </div>
        </Reveal>
      )}

      {state === "ready" && items.length > 0 && (
        <>
          <Reveal delay={0.05} className="mt-10">
            <div className="-mx-6 flex gap-3 overflow-x-auto px-6 pb-2 md:mx-0 md:grid md:grid-cols-5 md:overflow-visible md:px-0">
              <StatusMetric
                label="All Claims"
                value={defaultFeedCount}
                active={filter === "all"}
                onClick={() => setFilter("all")}
              />
              {STATUS_GROUP_ORDER.map((group) => (
                <StatusMetric
                  key={group}
                  label={STATUS_GROUP_LABEL[group]}
                  value={counts[group]}
                  active={filter === group}
                  onClick={() => setFilter(group)}
                />
              ))}
            </div>
          </Reveal>

          {filteredItems.length === 0 ? (
            <Reveal delay={0.1}>
              <p className="mt-16 text-center text-[14px] tracking-body text-graphite">
                No claims match this filter.
              </p>
            </Reveal>
          ) : (
            <div className="mt-10 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {filteredItems.map((item, i) => (
                <Reveal key={item.id} delay={Math.min(i * 0.04, 0.3)}>
                  <ClaimCard item={item} />
                </Reveal>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function StatusMetric({
  label,
  value,
  active,
  onClick,
}: {
  label: string;
  value: number;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`min-w-[136px] shrink-0 rounded-card border px-5 py-4 text-left transition-colors md:min-w-0 md:shrink ${
        active ? "border-lavender bg-lavender/10" : "border-fog bg-white hover:border-ash"
      }`}
    >
      <p className="whitespace-nowrap text-[11px] font-medium uppercase tracking-[0.08em] text-ash">
        {label}
      </p>
      <p className="mt-1.5 text-[24px] font-semibold tracking-heading text-carbon">{value}</p>
    </button>
  );
}
