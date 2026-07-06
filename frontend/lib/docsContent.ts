/**
 * Content for the public /docs page (components/docs/DocsShell.tsx).
 *
 * User-facing product documentation — how to use ClaimSight and how to
 * read its results. Deliberately no model file names, no exact
 * anti-abuse thresholds, no internal service architecture, and no claims
 * the product can't back (no regulatory approval, no insurer
 * partnerships, no "final quotation" language).
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
    label: "What ClaimSight Does",
    heading: "What ClaimSight does",
    paragraphs: [
      "ClaimSight is an AI-assisted triage tool for motor insurance claims in India. You enter basic vehicle details and upload photos of the damage; ClaimSight returns a structured, first-pass assessment: which parts look damaged, how severe each looks, and a preliminary repair-cost range. If you attach your insurance policy, it also reads the policy and relates the detected damage to the policy's own wording.",
      "It is a first look, not a final one. Every assessment is meant to speed up a human reviewer's work, not replace their judgment — anything the system isn't confident about is deliberately routed for manual review instead of guessed at.",
    ],
  },
  {
    id: "creating-assessment",
    label: "Creating an Assessment",
    heading: "How to create an assessment",
    paragraphs: [
      "Sign in with Google, then open New Assessment. Select the vehicle's manufacturer, select the model (the vehicle category is detected automatically from the model), and enter the manufacture year. Then upload one or more photos of the damage — JPEG, PNG, or WebP, up to 10 photos of up to 10MB each.",
      "Optionally attach your insurance policy as a PDF or photo; it is processed in the background and its findings appear on the claim's Policy Analysis panel. Press Analyze claim and keep the page open — analysis usually completes within a minute, and you land directly on the finished claim report.",
      "Every claim you create is saved to your account. You can close the browser and come back later — the claim, its report, and its analysis remain available from your dashboard.",
    ],
  },
  {
    id: "photo-guidelines",
    label: "Photo Guidelines",
    heading: "Photo guidelines",
    paragraphs: [
      "Photograph the damage in good light, from about one to three metres away, with the damaged area clearly visible and unobstructed. Several photos from different angles help: findings are cross-checked across photos, so the same dent seen twice is reported once — with more confidence — not double-counted.",
      "Avoid extreme close-ups that crop out the surrounding panel (the system needs context to know which part it is looking at), heavy reflections or rain on the panel, and photos where the vehicle is a small object in a large scene.",
      "Every photo is first checked to confirm it actually shows a vehicle. A photo that doesn't — a person, a receipt, an unrelated scene — is rejected with the exact filename and reason, so you can swap it out and retry without starting over.",
    ],
  },
  {
    id: "statuses",
    label: "Assessment Statuses",
    heading: "Understanding assessment statuses",
    paragraphs: [
      "A claim carries one overall status. Awaiting Analysis: the claim exists but photos haven't been analyzed yet. Analysis In Progress: the assessment is currently running. Analysis Complete: every detected part was assessed with high confidence. Review Required: the analysis finished, but at least one finding needs a human decision before it should be treated as fact. Assessment Failed: the analysis could not be completed — typically unusable photos or a temporary service problem — and can be retried.",
      "Review Required is a normal, healthy outcome — it means the system chose caution over guessing. It is not an error and does not mean your claim was rejected.",
    ],
  },
  {
    id: "severity",
    label: "Severity Levels",
    heading: "Understanding severity levels",
    paragraphs: [
      "Each damaged part is labelled Minor, Moderate, or Severe based on how much of the part appears affected, together with a recommended next step: repair, repair and repaint, or replace. Parts the system cannot judge confidently are labelled Uncertain and routed for manual inspection instead of receiving a made-up severity.",
      "These are heuristic, first-pass calls meant to inform a reviewer — not a certified repair assessment.",
    ],
  },
  {
    id: "review-required",
    label: "Review Required",
    heading: "What “Review Required” means",
    paragraphs: [
      "Every damaged part is marked either Accepted or Review Required. Accepted means the system is confident enough in the detection to act on it directly. Review Required means the finding is real but uncertain — a partial view, an ambiguous angle, low visual confidence — and a person should look at it before it's treated as fact.",
      "A claim with any Review Required part is never silently marked complete: its overall status reflects that a human still needs to weigh in, and those parts never contribute a confident number to the cost estimate.",
    ],
  },
  {
    id: "repair-estimates",
    label: "Repair Estimates",
    heading: "Repair cost estimates",
    paragraphs: [
      "Each Accepted part receives a preliminary repair-cost range in INR, based on the part, the recommended action, and the vehicle's category (a hatchback and a luxury car are not priced the same way). These ranges roll up into a single preliminary estimate for the whole claim.",
      "A part still awaiting manual review never contributes a number to that total — it is shown as pending, not silently priced at zero.",
      "All figures are indicative estimates, not final quotations. Actual repair costs vary with location, workshop, parts availability, taxes, labour rates, and the vehicle's real condition on inspection. An estimate here is never a workshop quote, an insurer-approved payout, or a guarantee.",
    ],
  },
  {
    id: "policy-analysis",
    label: "Policy Analysis",
    heading: "How policy analysis works",
    paragraphs: [
      "If you attach your insurance policy (PDF or photo), ClaimSight extracts its key facts — insurer, policy type, coverage dates, insured declared value, deductible, and listed exclusions — and relates each detected damaged part to the policy's own wording. Findings are labelled as likely covered, unclear, or a potential exclusion, each with the retrieved policy text that supports it.",
      "These findings reflect the wording of the document you uploaded, nothing more. They are not the insurer's adjudication of your claim, and an unclear or potential-exclusion finding simply means the wording deserves a human read. In the claim report, your policy number always appears masked.",
    ],
  },
  {
    id: "data-privacy",
    label: "Data & Privacy",
    heading: "Data and privacy",
    paragraphs: [
      "You sign in with Google; ClaimSight stores your name, email, and profile picture to tie your claims to your account. Your claims — vehicle details, analysis results, estimates, and reports — are stored so your history survives closing the browser, and are only ever visible to your own signed-in account.",
      "Damage photos are processed to produce the assessment and are not retained afterwards — this is why an old claim shows its analysis results and a reference image of the vehicle model, not your original photos. Uploaded policy documents are retained so the policy analysis on your claim can be re-displayed.",
      "The vehicle image shown on a claim is a generic reference photo or illustration of that make and model — it is never one of your uploaded photos and is never used in the damage analysis.",
    ],
  },
  {
    id: "limitations",
    label: "Limitations",
    heading: "Limitations",
    paragraphs: [
      "ClaimSight assists claim triage; it does not approve or reject claims, and does not replace an insurance adjuster's final decision. Every cost figure is a preliminary estimate, never a guaranteed or insurer-approved amount, and every coverage finding reflects wording retrieved from your own uploaded policy document, not the insurer's final adjudication.",
      "Results depend on photo and document quality — poor lighting, extreme crops, heavy obstruction, or a scanned policy with no extractable text can all push a finding into manual review rather than a confident result. That is the intended behavior, not a bug.",
      "Risk signals are neutral indicators that something is worth a second look — an inconsistency, a mismatch, a gap in the evidence — never an accusation or a fraud determination. ClaimSight does not currently read number plates or independently verify registration documents against a government database.",
    ],
  },
];
