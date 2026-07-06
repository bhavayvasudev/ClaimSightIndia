import { Suspense } from "react";
import { SignInCard } from "@/components/auth/SignInCard";

export const metadata = {
  title: "Sign in — ClaimSight India",
  description: "Sign in with Google to start or review a vehicle damage assessment.",
};

export default function SignInPage() {
  return (
    <Suspense fallback={null}>
      <SignInCard />
    </Suspense>
  );
}
