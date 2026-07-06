"use client";

/**
 * Shared read model for the signed-in user's backend profile
 * (`GET /users/me`). The Auth.js session only carries Google's own
 * name/image — ClaimSight customizations (display name, custom avatar)
 * live in the backend, so the Nav and the profile page both read
 * through this hook and fall back to session values while loading.
 *
 * Cross-component consistency without a state library: any component
 * that changes the profile calls `notifyProfileUpdated()` after a
 * successful save, and every mounted hook instance refetches.
 */

import { useCallback, useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { getMyProfile, type UserProfile } from "@/lib/api";

const PROFILE_UPDATED_EVENT = "claimsight:profile-updated";

export function notifyProfileUpdated(): void {
  window.dispatchEvent(new Event(PROFILE_UPDATED_EVENT));
}

export function useProfile(): {
  profile: UserProfile | null;
  refresh: () => void;
} {
  const { data: session, status: sessionStatus } = useSession();
  const [profile, setProfile] = useState<UserProfile | null>(null);

  const token = session?.backendAccessToken;

  const load = useCallback(() => {
    if (!token) return;
    let cancelled = false;
    getMyProfile(token)
      .then((result) => {
        if (!cancelled) setProfile(result);
      })
      .catch(() => {
        // Non-fatal everywhere this hook is used — callers keep showing
        // session-derived values; the profile page has its own explicit
        // load/error state on top of this.
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  useEffect(() => {
    if (sessionStatus !== "authenticated") {
      setProfile(null);
      return;
    }
    return load();
  }, [sessionStatus, load]);

  useEffect(() => {
    const handler = () => load();
    window.addEventListener(PROFILE_UPDATED_EVENT, handler);
    return () => window.removeEventListener(PROFILE_UPDATED_EVENT, handler);
  }, [load]);

  return { profile, refresh: load };
}
