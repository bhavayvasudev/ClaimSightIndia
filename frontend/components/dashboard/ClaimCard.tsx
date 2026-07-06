import Link from "next/link";
import Image from "next/image";
import type { ClaimListItem } from "@/lib/api";
import { CLAIM_STATUS_LABEL, CLAIM_STATUS_TONE, formatInrRange } from "@/lib/formatting";

/**
 * The image here is always the `vehicle_reference_image` — a generic
 * illustration of this vehicle's make/model/category, never the
 * claimant's actual uploaded damage photo. The backend doesn't persist
 * submitted claim photos at all today (see the integration report), so
 * there is no "real" evidence photo this could be confused with; this
 * card must never imply otherwise.
 */
export function ClaimCard({ item }: { item: ClaimListItem }) {
  const vehicleTitle =
    [item.vehicle_make, item.vehicle_model].filter(Boolean).join(" ") || item.vehicle_type;
  const createdDate = new Date(item.created_at).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
  const hasPricing = item.summary.total_min_inr != null && item.summary.total_max_inr != null;

  return (
    <div className="flex flex-col overflow-hidden rounded-card border border-fog bg-white shadow-panel">
      <div className="relative aspect-[16/10] w-full shrink-0 bg-mist/40">
        {item.vehicle_reference_image ? (
          <Image
            src={item.vehicle_reference_image.url}
            alt={`Reference vehicle image: ${vehicleTitle}`}
            fill
            unoptimized
            className="object-contain p-6"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-[13px] tracking-body text-ash">
            No reference image
          </div>
        )}
      </div>

      <div className="flex flex-1 flex-col p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="truncate text-[15px] font-semibold tracking-heading text-carbon">
              {vehicleTitle}
            </h3>
            <p className="mt-0.5 text-[12px] tracking-body text-ash">
              {item.vehicle_year ? `${item.vehicle_year} • ` : ""}
              {item.vehicle_type}
            </p>
          </div>
          <span
            className={`inline-flex shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium ${CLAIM_STATUS_TONE[item.status]}`}
          >
            {CLAIM_STATUS_LABEL[item.status]}
          </span>
        </div>

        <p className="mt-3 text-[12px] tracking-body text-ash">{item.id}</p>

        <div className="mt-3 flex-1 space-y-1 text-[13px] tracking-body text-graphite">
          {item.summary.damaged_parts > 0 && (
            <p>
              {item.summary.damaged_parts} damaged part{item.summary.damaged_parts === 1 ? "" : "s"}
            </p>
          )}
          {hasPricing ? (
            <p className="font-medium text-carbon">
              {formatInrRange(item.summary.total_min_inr as number, item.summary.total_max_inr as number)}
            </p>
          ) : item.status === "failed" ? (
            <p className="text-ember">Assessment could not be completed</p>
          ) : (
            <p>Pending manual inspection</p>
          )}
        </div>

        <p className="mt-3 text-[11px] tracking-body text-ash">{createdDate}</p>

        {(item.has_policy || item.needs_manual_review) && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {item.has_policy && (
              <span className="inline-flex rounded-full bg-mist px-2 py-0.5 text-[10px] font-medium tracking-body text-graphite">
                {item.policy_ready ? "Policy Analysis Ready" : "Policy Attached"}
              </span>
            )}
            {item.needs_manual_review && (
              <span className="inline-flex rounded-full bg-[#fff2df] px-2 py-0.5 text-[10px] font-medium tracking-body text-amber">
                Manual Review
              </span>
            )}
          </div>
        )}

        <Link
          href={`/claims/${item.id}`}
          className="mt-4 inline-flex items-center gap-1 text-[13px] font-medium text-lavender transition-colors hover:text-iris"
        >
          View Assessment →
        </Link>
      </div>
    </div>
  );
}
