import { Nav } from "@/components/landing/Nav";
import { DashboardView } from "@/components/dashboard/DashboardView";

export const metadata = {
  title: "Dashboard — ClaimSight India",
  description: "Your vehicle assessments and claim activity.",
};

export default function DashboardPage() {
  return (
    <main>
      <Nav />
      <DashboardView />
    </main>
  );
}
