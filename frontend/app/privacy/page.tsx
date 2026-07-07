import { Nav } from "@/components/landing/Nav";
import { LegalDocShell } from "@/components/legal/LegalDocShell";
import { LEGAL_LAST_UPDATED_LABEL } from "@/lib/legal/version";
import { PRIVACY_SECTIONS } from "@/lib/legal/privacyContent";

export const metadata = {
  title: "Privacy Policy — ClaimSight India",
  description:
    "What ClaimSight India collects when you sign in and file a claim, how damage photos and policy documents are handled, and what is and isn't retained.",
};

export default function PrivacyPage() {
  return (
    <main>
      <Nav />
      <LegalDocShell
        title="Privacy Policy"
        lastUpdatedLabel={LEGAL_LAST_UPDATED_LABEL}
        intro="This page explains what ClaimSight India collects, why, and what actually happens to it — based on how the product works today."
        sections={PRIVACY_SECTIONS}
      />
    </main>
  );
}
