// Renders the ClaimTriageReport for a given claim id. Placeholder until the
// GET /claims/{id} API route exists.
export default async function ClaimReportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <main>
      <h1>Claim {id}</h1>
      <p>Report view — coming next.</p>
    </main>
  );
}
