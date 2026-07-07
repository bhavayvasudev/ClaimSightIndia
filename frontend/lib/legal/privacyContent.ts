/**
 * Content for /privacy (components/legal/LegalDocShell.tsx via
 * app/privacy/page.tsx). Written to describe what the application
 * actually does today, based on reading the real implementation — not a
 * generic template. Where a claim can't be backed by real code (a
 * deletion mechanism, a compliance certification, a support channel),
 * this deliberately says so rather than promising it. Keep in sync with
 * `lib/docsContent.ts`'s "Data & Privacy" section and bump
 * `lib/legal/version.ts`'s `LEGAL_VERSION` whenever this changes.
 */

import type { LegalSection } from "@/components/legal/LegalDocShell";

export const PRIVACY_SECTIONS: LegalSection[] = [
  {
    id: "overview",
    label: "Overview",
    heading: "Overview",
    paragraphs: [
      "This policy explains what information ClaimSight India collects when you use the product, why, and what happens to it. It describes the application's actual behavior — sign-in, claim creation, damage-photo analysis, and policy-document review — not a generic boilerplate.",
      "ClaimSight India is an early-stage project. This policy will be updated as the product and its infrastructure evolve; the version identifier and \"Last updated\" date above always reflect the copy you're reading.",
    ],
  },
  {
    id: "information-we-collect",
    label: "Information We Collect",
    heading: "Information we collect",
    paragraphs: ["ClaimSight collects the following categories of information:"],
    bullets: [
      "Google account information: when you sign in with Google, ClaimSight receives your Google account's stable identifier, name, email address, and profile picture from Google, and stores them to identify your account and greet you by name.",
      "Profile customizations you choose to add: a display name, a preferred contact email, and a custom profile photo — all optional, and separate from the Google identity above.",
      "Claim and vehicle information you enter: vehicle manufacturer, model, year, and category; and, if you provide them, an incident date and a free-text incident location.",
      "Damage photographs you upload when creating a claim.",
      "Insurance policy documents you choose to upload (PDF or photo), if you attach one to a claim.",
      "Legal consent records: the timestamp of your acceptance of these Terms and this Privacy Policy, and which version you accepted, recorded when you check the consent box on the sign-in page.",
      "Basic technical data inherent to any web request (e.g. what your browser sends to load the page); ClaimSight does not run any analytics or advertising tracking script.",
    ],
  },
  {
    id: "ai-analysis",
    label: "AI Analysis",
    heading: "How ClaimSight analyzes your claim",
    paragraphs: [
      "Damage photos are analyzed by ClaimSight's own computer-vision service, which detects vehicle parts and segments visible damage. This runs on infrastructure ClaimSight operates itself — your photos are not sent to a third-party AI vendor for this step.",
      "If you attach an insurance policy document, its text is extracted and, when the project has an Anthropic API key configured, the already-extracted policy text may be sent to Anthropic's Claude API to identify structured fields (such as insurer, coverage dates, deductible, and exclusions). Only that extracted text is sent for this purpose — never your photos, your account identity, or other claims. When no Anthropic API key is configured, this extraction runs entirely locally using pattern-based rules instead.",
      "Repair-cost estimates and \"risk signal\" checks (flags that something may be worth a second look) are produced by deterministic, rule-based logic within ClaimSight, not by an AI model scoring you or your claim. A risk signal is never a fraud determination.",
      "ClaimSight does not currently use any other third-party AI, analytics, or data-enrichment service (for example, no weather-data lookup or usage-analytics vendor is active in the deployed application, even though some code scaffolding for possible future checks exists but is not wired up).",
    ],
  },
  {
    id: "cookies-sessions",
    label: "Cookies & Sessions",
    heading: "Cookies and sessions",
    paragraphs: [
      "Signing in sets a single encrypted, HttpOnly session cookie (via Auth.js) that keeps you signed in across visits; it cannot be read by page scripts. The frontend separately holds a short-lived, backend-issued access token inside that session, sent with each request you make so the backend can identify which account a claim belongs to.",
      "ClaimSight does not set advertising or third-party tracking cookies.",
    ],
  },
  {
    id: "storage-retention",
    label: "Storage & Retention",
    heading: "Storage and retention",
    paragraphs: ["What is kept, and for how long, differs by data type:"],
    bullets: [
      "Damage photographs are used to produce your assessment and are not stored afterwards — only a hash of the image is kept (to detect exact duplicates), never the image itself. This is why a completed claim shows a generic reference photo of your vehicle's make and model, never your original photo.",
      "Uploaded policy documents are stored so the policy analysis on your claim can continue to be shown to you.",
      "Claim records, vehicle details, analysis results, cost estimates, and generated reports are stored so your history remains available when you return, and are visible only from your own signed-in account.",
      "Profile photos you upload are stored until you replace or reset them.",
      "ClaimSight does not currently offer a self-service account- or data-deletion feature. If you want data removed, see \"Your rights\" below — this is a genuine current limitation, not a design choice we're presenting as a feature.",
    ],
  },
  {
    id: "security",
    label: "Security",
    heading: "Security practices",
    paragraphs: [
      "Google sign-in tokens are independently verified against Google's own published keys before any account is created or updated. Backend access tokens are short-lived and signed with a project-specific secret. Uploaded profile photos are validated as real images before being stored, under server-generated filenames rather than the name of the file you uploaded.",
      "No system is perfectly secure, and ClaimSight does not claim otherwise. These are the concrete measures in place today, not a guarantee against every possible failure.",
    ],
  },
  {
    id: "ai-limitations",
    label: "AI Limitations",
    heading: "Limitations of automated assessment",
    paragraphs: [
      "ClaimSight's damage detection and cost estimates are a first-pass, automated read of the photos and documents you provide — not a certified inspection, not an insurer's adjudication, and not a guarantee of what any insurer will pay or approve. Findings the system isn't confident about are routed for manual review rather than guessed at.",
      "See the Docs page for a fuller explanation of how assessments, statuses, and risk signals work.",
    ],
  },
  {
    id: "childrens-privacy",
    label: "Children's Privacy",
    heading: "Children's privacy",
    paragraphs: [
      "ClaimSight is built for filing and reviewing motor insurance claims, which in practice requires a Google account and, generally, the ability to hold or act on an insurance policy. ClaimSight does not knowingly collect information from children, and does not separately enforce a minimum age beyond what is already required by Google's own account terms.",
    ],
  },
  {
    id: "cross-border",
    label: "Cross-Border Processing",
    heading: "Cross-border processing",
    paragraphs: [
      "Google's identity verification and, when configured, Anthropic's Claude API run on those companies' own infrastructure, which may be located outside India, regardless of where ClaimSight itself is hosted. ClaimSight's own hosting location is still being finalized as the project moves toward a production deployment; this section will be updated with specifics once that is settled.",
    ],
  },
  {
    id: "your-rights",
    label: "Your Rights & Contact",
    heading: "Your rights and how to reach us",
    paragraphs: [
      "You can review and update your display name, contact email, and profile photo at any time from your Profile page. Your Google-derived name, email, and photo refresh automatically each time you sign in and are not separately editable.",
      "ClaimSight India does not currently publish a dedicated privacy contact channel (support email, postal address, or phone number), and does not yet offer self-service account or data deletion. This policy will be updated to reflect those once they are available.",
    ],
  },
  {
    id: "changes",
    label: "Changes to This Policy",
    heading: "Changes to this policy",
    paragraphs: [
      "If this policy changes in a way that affects how your information is handled, this page and its \"Last updated\" date and version identifier will be updated accordingly.",
    ],
  },
];
