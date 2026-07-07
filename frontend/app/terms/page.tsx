import { Nav } from "@/components/landing/Nav";
import { LegalDocShell } from "@/components/legal/LegalDocShell";
import { LEGAL_LAST_UPDATED_LABEL } from "@/lib/legal/version";
import { TERMS_SECTIONS } from "@/lib/legal/termsContent";

export const metadata = {
  title: "Terms of Service — ClaimSight India",
  description:
    "The terms that govern using ClaimSight India: account responsibility, AI-generated damage assessments, prohibited use, and limitations.",
};

export default function TermsPage() {
  return (
    <main>
      <Nav />
      <LegalDocShell
        title="Terms of Service"
        lastUpdatedLabel={LEGAL_LAST_UPDATED_LABEL}
        intro="These Terms govern your use of ClaimSight India. Please read them alongside the Privacy Policy."
        sections={TERMS_SECTIONS}
      />
    </main>
  );
}
