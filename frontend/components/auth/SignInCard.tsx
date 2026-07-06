"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { signIn } from "next-auth/react";
import { Reveal } from "@/components/ui/Reveal";
import { AppleIcon, FacebookIcon, GoogleIcon } from "./ProviderIcons";

const DEFAULT_CALLBACK_URL = "/claims/new";

/**
 * The one place `signIn()` is ever called with a provider argument.
 * Google is the only wired-up provider (`auth.ts`); Apple/Facebook are
 * inert "Coming soon" buttons — plain `disabled` elements with no
 * `onClick`/`href`, so they can't start an OAuth request, navigate, or
 * touch the URL no matter how they're activated.
 */
export function SignInCard() {
  const searchParams = useSearchParams();
  const [isRedirecting, setIsRedirecting] = useState(false);
  const callbackUrl = searchParams.get("callbackUrl") || DEFAULT_CALLBACK_URL;

  function handleGoogleSignIn() {
    setIsRedirecting(true);
    signIn("google", { callbackUrl });
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-white px-6 py-16">
      <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute left-1/2 top-[8%] h-[420px] w-[640px] -translate-x-1/2 rounded-full bg-lavender/[0.08] blur-[130px]" />
      </div>

      <Reveal className="relative w-full max-w-[420px]">
        <div className="rounded-card border border-fog bg-white p-8 shadow-panel md:p-10">
          <Link href="/" className="mb-8 flex items-center justify-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-lavender" aria-hidden />
            <span className="text-[14px] font-semibold tracking-heading text-carbon">
              ClaimSight <span className="font-normal text-ash">India</span>
            </span>
          </Link>

          <h1 className="text-center text-[22px] font-semibold tracking-heading text-carbon">
            Sign in to ClaimSight
          </h1>
          <p className="mt-2 text-center text-[13px] leading-relaxed tracking-body text-ash">
            Continue to start or review a vehicle damage assessment.
          </p>

          <div className="mt-8">
            <button
              type="button"
              onClick={handleGoogleSignIn}
              disabled={isRedirecting}
              className="flex w-full items-center justify-center gap-3 rounded-full border border-fog bg-white px-5 py-3 text-[14px] font-medium text-carbon transition-colors hover:bg-mist disabled:cursor-not-allowed disabled:opacity-60"
            >
              <GoogleIcon />
              {isRedirecting ? "Redirecting…" : "Continue with Google"}
            </button>
          </div>

          <div className="my-7 flex items-center gap-3">
            <span className="h-px flex-1 bg-fog" aria-hidden />
            <span className="text-[11px] font-medium uppercase tracking-[0.08em] text-ash">or</span>
            <span className="h-px flex-1 bg-fog" aria-hidden />
          </div>

          <div className="flex flex-col gap-3">
            <DisabledProviderButton icon={<AppleIcon />} label="Continue with Apple" />
            <DisabledProviderButton icon={<FacebookIcon />} label="Continue with Facebook" />
          </div>

          <p className="mt-8 text-center text-[12px] leading-relaxed tracking-body text-ash">
            By continuing, you agree this is a preliminary AI-assisted assessment, not a final
            insurance decision.
          </p>
        </div>
      </Reveal>
    </div>
  );
}

function DisabledProviderButton({ icon, label }: { icon: ReactNode; label: string }) {
  return (
    <button
      type="button"
      disabled
      aria-disabled="true"
      className="flex w-full cursor-not-allowed items-center justify-between gap-3 rounded-full border border-fog bg-mist/60 px-5 py-3 text-[14px] font-medium text-ash"
    >
      <span className="flex items-center gap-3">
        <span className="opacity-50">{icon}</span>
        {label}
      </span>
      <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.06em] text-ash ring-1 ring-inset ring-fog">
        Coming soon
      </span>
    </button>
  );
}
