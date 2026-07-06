import type { ClaimStatus } from "./api/types";

/**
 * Indian digit grouping (lakh/crore), mirroring the backend's
 * `format_inr` (`backend/app/schemas/claim_state.py`) — the API sends raw
 * `min_inr`/`max_inr` numbers, not a pre-formatted display string, so this
 * needs to match that logic exactly rather than using `toLocaleString`
 * (which groups in thousands, not lakhs).
 */
export function formatInr(amountRupees: number): string {
  const sign = amountRupees < 0 ? "-" : "";
  const digits = Math.round(Math.abs(amountRupees)).toString();

  let grouped: string;
  if (digits.length <= 3) {
    grouped = digits;
  } else {
    const last3 = digits.slice(-3);
    let rest = digits.slice(0, -3);
    const parts: string[] = [];
    while (rest.length > 2) {
      parts.unshift(rest.slice(-2));
      rest = rest.slice(0, -2);
    }
    if (rest) parts.unshift(rest);
    grouped = `${parts.join(",")},${last3}`;
  }

  return `${sign}₹${grouped}`;
}

export function formatInrRange(minInr: number, maxInr: number): string {
  return `${formatInr(minInr)} – ${formatInr(maxInr)}`;
}

export const CLAIM_STATUS_LABEL: Record<ClaimStatus, string> = {
  intake: "Awaiting Analysis",
  analyzing: "Analysis In Progress",
  analysis_complete: "Analysis Complete",
  review_required: "Review Required",
  failed: "Assessment Failed",
};

export const CLAIM_STATUS_DESCRIPTION: Record<ClaimStatus, string> = {
  intake: "This claim has been created but hasn't been analyzed yet.",
  analyzing: "The AI assessment is currently running.",
  analysis_complete: "Every detected part was assessed with high confidence.",
  review_required: "AI assessment completed. Some detected areas require manual inspection.",
  failed: "The AI assessment could not be completed for this claim.",
};

/** Shared badge color per claim status — used by both the claim detail
 * page and dashboard claim cards so the same status always reads the
 * same way everywhere in the product. */
export const CLAIM_STATUS_TONE: Record<ClaimStatus, string> = {
  intake: "bg-mist text-graphite",
  analyzing: "bg-mist text-graphite",
  analysis_complete: "bg-mint-wash text-mint",
  review_required: "bg-[#fff2df] text-amber",
  failed: "bg-[#ffe8e0] text-ember",
};

/**
 * Some ai-service part labels use car-parts-model shorthand that reads
 * awkwardly to a claimant, e.g. "Passenger's door - (R/R)" or
 * "Headlight - (R)". This only rewrites patterns we can interpret
 * reliably (a leading front/rear axle code, or a trailing left/right side
 * code) — never invents orientation for a label it doesn't recognize; the
 * backend's own `PartDamageAssessment.part` value is never mutated, this
 * only changes what's displayed.
 */
const KNOWN_PART_LABELS: Record<string, string> = {
  "Car hood": "Hood",
  "Car boot": "Boot",
  "Front bumper": "Front Bumper",
  "Rear bumper": "Rear Bumper",
};

const DOOR_PATTERN = /^(Passenger'?s|Driver'?s) door\s*-\s*\(([FR])\/[LR]\)$/i;
const SIDE_SUFFIX_PATTERN = /^(.*?)\s*-\s*\(([LR])\)$/i;

export function formatPartName(rawPartLabel: string): string {
  const known = KNOWN_PART_LABELS[rawPartLabel];
  if (known) return known;

  const doorMatch = rawPartLabel.match(DOOR_PATTERN);
  if (doorMatch) {
    const axle = doorMatch[2].toUpperCase() === "F" ? "Front" : "Rear";
    const who = /passenger/i.test(doorMatch[1]) ? "Passenger" : "Driver";
    return `${axle} ${who} Door`;
  }

  const sideMatch = rawPartLabel.match(SIDE_SUFFIX_PATTERN);
  if (sideMatch) {
    const side = sideMatch[2].toUpperCase() === "L" ? "Left" : "Right";
    const base = sideMatch[1]
      .trim()
      .split(" ")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
    return `${side} ${base}`;
  }

  // Unrecognized shape — clean up punctuation rather than guess orientation.
  return rawPartLabel.replace(/[-_]+/g, " ").replace(/\s+/g, " ").trim();
}
