/**
 * Content for /terms (components/legal/LegalDocShell.tsx via
 * app/terms/page.tsx). Product-specific terms for ClaimSight India, not a
 * generic template — see privacyContent.ts's header comment for the same
 * ground rule. Bump `lib/legal/version.ts`'s `LEGAL_VERSION` whenever
 * this changes.
 */

import type { LegalSection } from "@/components/legal/LegalDocShell";

export const TERMS_SECTIONS: LegalSection[] = [
  {
    id: "acceptance",
    label: "Acceptance",
    heading: "Acceptance of these terms",
    paragraphs: [
      "These Terms of Service govern your use of ClaimSight India. By checking the consent box on the sign-in page and continuing with Google sign-in, you agree to these Terms and to the Privacy Policy. If you do not agree, do not check the box and do not sign in.",
    ],
  },
  {
    id: "accounts",
    label: "Your Account",
    heading: "Account responsibility",
    paragraphs: [
      "ClaimSight accounts are created via Google sign-in; there is no separate ClaimSight password. You're responsible for whatever happens under your Google account while it's able to sign in to ClaimSight, and for keeping that Google account secure.",
      "The information you provide when creating a claim (vehicle details, incident details, uploaded documents) should be your own and should be accurate to the best of your knowledge.",
    ],
  },
  {
    id: "intended-use",
    label: "Intended Use",
    heading: "Intended use of ClaimSight",
    paragraphs: [
      "ClaimSight is an AI-assisted triage tool for motor insurance claims in India: you provide vehicle details and damage photographs (and, optionally, a policy document), and ClaimSight returns a structured, preliminary assessment intended to help a human reviewer work faster — not to replace that reviewer's judgment, and not to act as an insurer.",
    ],
  },
  {
    id: "uploaded-content",
    label: "Uploaded Content",
    heading: "Uploaded content and your responsibility",
    paragraphs: [
      "You retain ownership of the photographs, documents, and other content you upload. By uploading content, you grant ClaimSight the limited right to process it for the purpose of producing your assessment (as described in the Privacy Policy).",
      "You're responsible for making sure you have the right to upload the content you submit, and that it doesn't belong to, or depict, someone else's claim or property without appropriate authorization.",
    ],
  },
  {
    id: "ai-assessments",
    label: "AI-Generated Assessments",
    heading: "AI-generated damage assessments and estimates",
    paragraphs: [
      "Damage assessments, severity labels, and repair-cost estimates produced by ClaimSight are preliminary, automated, informational outputs. They are not a certified inspection, not a legal or professional opinion, and not a final insurance decision.",
      "ClaimSight does not guarantee that any insurer will accept, adopt, or pay out in line with an assessment or estimate generated here. Actual claim outcomes are determined solely by the relevant insurer, in accordance with your policy and applicable law.",
    ],
  },
  {
    id: "prohibited-use",
    label: "Prohibited Use",
    heading: "Prohibited use",
    paragraphs: ["You agree not to:"],
    bullets: [
      "Use ClaimSight to support a claim you know to be false, exaggerated, or fraudulent.",
      "Upload content that is malicious, unlawful, or that you don't have the right to submit.",
      "Attempt to bypass, manipulate, or reverse-engineer the assessment pipeline, or interfere with the service's normal operation.",
      "Access or attempt to access another user's account or claim data.",
      "Use ClaimSight in any way that violates applicable law.",
    ],
  },
  {
    id: "intellectual-property",
    label: "Intellectual Property",
    heading: "Intellectual property",
    paragraphs: [
      "ClaimSight's software, branding, and product design are the property of the ClaimSight India project and its contributors. Nothing in these Terms transfers any of that to you. As set out above, you retain ownership of the content you upload.",
    ],
  },
  {
    id: "availability",
    label: "Service Availability",
    heading: "Service availability",
    paragraphs: [
      "ClaimSight is an early-stage, actively-developed project. Features, availability, and performance may change without notice, and the service may be temporarily unavailable or return incomplete results (for example, if an underlying analysis component is unreachable). No specific uptime or response-time commitment is made.",
    ],
  },
  {
    id: "third-party-services",
    label: "Third-Party Services",
    heading: "Third-party services",
    paragraphs: [
      "Sign-in depends on Google's OAuth service, subject to Google's own terms. Policy-document field extraction may, when configured, use Anthropic's Claude API, subject to Anthropic's own terms. ClaimSight is not responsible for the availability or behavior of these third-party services.",
    ],
  },
  {
    id: "limitation-of-liability",
    label: "Limitation of Liability",
    heading: "Limitation of liability",
    paragraphs: [
      "ClaimSight is provided on an \"as is\" and \"as available\" basis, without warranties of any kind, express or implied, including as to accuracy, reliability, or fitness for a particular purpose. As an early-stage project, ClaimSight and its contributors disclaim liability, to the fullest extent permitted by applicable law, for damages or losses arising from your use of, or reliance on, the service — including decisions made based on an AI-generated assessment or estimate.",
    ],
  },
  {
    id: "termination",
    label: "Termination",
    heading: "Termination and suspension",
    paragraphs: [
      "ClaimSight may suspend or terminate your access if you violate these Terms, misuse the service, or for operational or legal reasons. You may stop using ClaimSight at any time.",
    ],
  },
  {
    id: "changes-to-terms",
    label: "Changes to Terms",
    heading: "Changes to these terms",
    paragraphs: [
      "These Terms may be updated as ClaimSight evolves. The \"Last updated\" date and version identifier at the top of this page reflect the version currently in effect. Continuing to use ClaimSight after an update constitutes acceptance of the revised Terms.",
    ],
  },
  {
    id: "governing-law-contact",
    label: "Governing Law",
    heading: "Governing law",
    paragraphs: [
      "ClaimSight India does not currently publish a registered legal entity, principal place of business, or designated jurisdiction for these Terms. Until that information is published here, these Terms should be read as a good-faith description of how ClaimSight is intended to be used, rather than as designating a specific legal jurisdiction or dispute-resolution forum.",
    ],
  },
];
