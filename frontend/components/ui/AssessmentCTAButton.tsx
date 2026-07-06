"use client";

import type { ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { PillButton } from "./PillButton";

type AssessmentCTAButtonProps = {
  children: ReactNode;
  size?: "sm" | "md" | "lg";
  variant?: "primary" | "ghost" | "inverse";
};

/**
 * The single entry point into the real, API-backed claim flow. Never a
 * plain `href="/demo"` link: signed-in users go straight to
 * `/claims/new`; signed-out users land on the provider-choice screen
 * (`/signin`) first and continue to `/claims/new` after Google sign-in.
 * Shared by Nav, Hero, and Footer so the gating logic exists in exactly
 * one place.
 */
export function AssessmentCTAButton({
  children,
  size = "md",
  variant = "primary",
}: AssessmentCTAButtonProps) {
  const { data: session, status } = useSession();
  const router = useRouter();

  function handleClick() {
    if (session) {
      router.push("/claims/new");
    } else {
      router.push("/signin?callbackUrl=%2Fclaims%2Fnew");
    }
  }

  return (
    <PillButton onClick={handleClick} size={size} variant={variant} disabled={status === "loading"}>
      {children}
    </PillButton>
  );
}
