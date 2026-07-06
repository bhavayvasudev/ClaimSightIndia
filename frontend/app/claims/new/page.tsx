import { Nav } from "@/components/landing/Nav";
import { ClaimIntakeForm } from "@/components/claims/ClaimIntakeForm";

export const metadata = {
  title: "Submit a Claim — ClaimSight India",
  description: "Enter vehicle details and upload damage photos for an AI damage assessment.",
};

export default function NewClaimPage() {
  return (
    <main>
      <Nav />
      <ClaimIntakeForm />
    </main>
  );
}
