/**
 * Content for the public /docs page (components/docs/DocsShell.tsx).
 *
 * Deliberately product/API-level only — no model file names, no exact
 * anti-abuse thresholds, no internal service architecture. See the
 * security-hardening batch's docs/security.md for the internal version of
 * anything referenced here.
 */

export interface DocSection {
  id: string;
  label: string;
  heading: string;
  paragraphs: string[];
}

export const DOC_SECTIONS: DocSection[] = [
  {
    id: "overview",
    label: "Overview",
    heading: "Overview",
    paragraphs: [
      "ClaimSight is an AI-assisted triage tool for motor insurance claims in India. A claimant (or the person filing on their behalf) enters basic vehicle details and uploads photos of the damage; ClaimSight returns a structured, first-pass assessment: which parts look damaged, how severe each looks, and a preliminary repair-cost range.",
      "It is a first look, not a final one. Every assessment is meant to speed up a human reviewer's work, not replace their judgment.",
    ],
  },
  {
    id: "how-it-works",
    label: "How ClaimSight Works",
    heading: "How ClaimSight works",
    paragraphs: [
      "A claim moves through a short, fixed pipeline: vehicle details are recorded, each uploaded photo is checked to confirm it actually shows a vehicle, the photos are analyzed for visible damage, each affected part gets its own severity and confidence assessment, a preliminary repair-cost range is produced, and anything the system isn't confident about is routed for manual review.",
      "Every stage produces a structured result — a status, a label, a number — rather than a single free-text answer. That's deliberate: a structured field can be inspected, sorted, and challenged; a paragraph of prose can only be read.",
    ],
  },
  {
    id: "damage-analysis",
    label: "Damage Analysis",
    heading: "Damage analysis",
    paragraphs: [
      "Uploaded photos are analyzed to identify visible vehicle parts and the damage on them. When a claim includes several photos of the same vehicle, findings are cross-checked across angles rather than trusted from a single frame — the same dent seen from two photos is reported once, not twice.",
      "Each damaged part is reported with a severity (Minor, Moderate, or Severe) and a recommended next step (repair, repair and repaint, or replace). These are heuristic, first-pass calls meant to inform a reviewer, not a certified repair estimate.",
    ],
  },
  {
    id: "vehicle-validation",
    label: "Vehicle Validation",
    heading: "Vehicle validation",
    paragraphs: [
      "Before any photo is analyzed for damage, ClaimSight checks that it actually shows a vehicle. A photo that doesn't — a person, a receipt, an unrelated scene — is rejected with a clear reason and the exact filename, so it can be swapped out and the claim retried without starting over.",
      "This check runs first, before the more expensive damage analysis, and a rejected photo is never silently accepted or silently dropped from the claim.",
    ],
  },
  {
    id: "severity-review",
    label: "Severity & Review Status",
    heading: "Severity & review status",
    paragraphs: [
      "Every damaged part is marked either Accepted or Review Required. Accepted means the system is confident enough in the detection to act on it directly. Review Required means the finding is real but uncertain — a partial view, an ambiguous angle, low visual confidence — and a human should look at it before it's treated as fact.",
      "A claim with any Review Required part is never silently marked complete: its overall status reflects that a person still needs to weigh in.",
    ],
  },
  {
    id: "repair-estimates",
    label: "Repair Cost Estimates",
    heading: "Repair cost estimates",
    paragraphs: [
      "Each Accepted part receives a preliminary repair-cost range in INR, based on the part, the recommended action, and the vehicle's category (a hatchback and a luxury car are not priced the same way). These ranges roll up into a single preliminary estimate for the whole claim.",
      "A part still awaiting manual review never contributes a confident number to that total — it's shown as pending, not silently priced at zero or guessed. These figures are always a preliminary estimate, never a workshop quote, an insurer-approved payout, or a guarantee.",
    ],
  },
  {
    id: "api-overview",
    label: "API Overview",
    heading: "API overview",
    paragraphs: [
      "ClaimSight's application backend exposes a small set of authenticated endpoints behind Google sign-in: create a claim from vehicle details, submit photos for analysis, upload a policy document, retrieve a claim's report and timeline, and list your own claim history. Every request is tied to the signed-in account — you can only ever see and act on your own claims.",
      "The API is intentionally narrow in scope for now: it covers claim intake, policy analysis, and retrieval — not account administration or insurer-side case management.",
    ],
  },
  {
    id: "limitations",
    label: "Limitations",
    heading: "Limitations",
    paragraphs: [
      "ClaimSight assists claim triage; it does not approve or reject claims, and does not replace an insurance adjuster's final decision. Every cost figure is a preliminary estimate, never a guaranteed or insurer-approved amount, and every coverage finding reflects wording retrieved from the claimant's own uploaded policy document, not the insurer's final adjudication.",
      "Results depend on photo and document quality — poor lighting, extreme crops, heavy obstruction, or a scanned policy with no extractable text can all push a finding into manual review rather than a confident result, which is the intended behavior, not a bug.",
      "Risk signals are neutral indicators that something is worth a second look — an inconsistency, a mismatch, a gap in the evidence — never an accusation or a fraud determination. ClaimSight does not currently read number plates or independently verify registration documents against a government database.",
    ],
  },
];
