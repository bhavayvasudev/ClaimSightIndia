import { Nav } from "@/components/landing/Nav";
import { DocsShell } from "@/components/docs/DocsShell";

export const metadata = {
  title: "Docs — ClaimSight India",
  description:
    "How ClaimSight works: damage analysis, vehicle validation, severity and review status, repair cost estimates, and the API overview.",
};

export default function DocsPage() {
  return (
    <main>
      <Nav />
      <DocsShell />
    </main>
  );
}
