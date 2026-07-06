"use client";

import { signIn } from "next-auth/react";
import { PillButton } from "@/components/ui/PillButton";

/**
 * The one recovery action for a session that has no usable backend access
 * token (`session.needsBackendReauth`, or a 401 from a claim route): a
 * fresh Google sign-in, which re-runs `auth.ts`'s sign-in-time sync and
 * mints a new token. Deliberately a user-triggered button — never an
 * automatic redirect, which could loop if the backend stays unreachable.
 */
export function SignInAgainButton({
  variant = "primary",
  size = "md",
}: {
  variant?: "primary" | "ghost" | "inverse";
  size?: "sm" | "md" | "lg";
}) {
  return (
    <PillButton onClick={() => signIn("google")} variant={variant} size={size}>
      Sign in again
    </PillButton>
  );
}
