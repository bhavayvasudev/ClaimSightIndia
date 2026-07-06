import { Nav } from "@/components/landing/Nav";
import { ClaimResultView } from "@/components/claims/ClaimResultView";

export default async function ClaimReportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <main>
      <Nav />
      <ClaimResultView claimId={id} />
    </main>
  );
}
