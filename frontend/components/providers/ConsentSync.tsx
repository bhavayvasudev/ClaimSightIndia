"use client";

import { useEffect } from "react";
import { useSession } from "next-auth/react";
import { syncPendingConsentIfNeeded } from "@/lib/consent/consentSync";

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(
  /\/+$/,
  ""
);

/**
 * Mounted once in the root layout, inside `SessionProvider`. Renders
 * nothing — its only job is to notice when a backend access token first
 * becomes available (i.e. right after a sign-in completes) and, if the
 * sign-in page's consent checkbox left a pending marker in
 * sessionStorage, post it once to `POST /users/consent`. See
 * `lib/consent/consentSync.ts` for the actual logic and why sessionStorage
 * is the bridge across the Google redirect.
 */
export function ConsentSync() {
  const { data: session } = useSession();
  const accessToken = session?.backendAccessToken;

  useEffect(() => {
    if (!accessToken) return;
    void syncPendingConsentIfNeeded({
      storage: window.sessionStorage,
      accessToken,
      apiBaseUrl: API_BASE_URL,
      fetchImpl: fetch,
    });
  }, [accessToken]);

  return null;
}
