/**
 * Bridges the sign-in page's consent checkbox to server-side persistence
 * across the Google OAuth redirect. `auth.ts`/`lib/auth/callbacks.ts` (the
 * actual OAuth token bridge) are never touched by this — the checkbox
 * click happens on this domain, before the redirect to Google, so there
 * is no request in flight at that moment that could carry the fact of
 * the click to the backend. Instead: the click writes a short-lived
 * marker to sessionStorage (which survives the round-trip through
 * Google's domain and back, since it's tied to the tab, not the page),
 * and once the app sees an authenticated backend session again, it POSTs
 * that marker once to `POST /users/consent` and clears it.
 *
 * Every function here is dependency-injected (storage, fetch) so it's
 * unit-testable in this project's node-environment vitest setup, the
 * same pattern `lib/claims/analysisRunner.ts` uses for its own retries.
 */

const CONSENT_MARKER_KEY = "claimsight:pendingLegalConsent";

// Generous enough to cover a slow OAuth round-trip (Google account
// picker, 2FA) without leaving a marker that could resurface a
// long-abandoned consent click on some unrelated future sign-in.
const MAX_MARKER_AGE_MS = 10 * 60 * 1000;

export interface PendingConsentMarker {
  termsVersion: string;
  privacyVersion: string;
  recordedAt: number;
}

type ReadableStorage = Pick<Storage, "getItem">;
type WritableStorage = Pick<Storage, "setItem">;
type ClearableStorage = Pick<Storage, "removeItem">;

/** Called at the moment the (now-enabled) Google button is clicked. */
export function markConsentGiven(
  storage: WritableStorage,
  versions: { termsVersion: string; privacyVersion: string },
  now: number = Date.now()
): void {
  const marker: PendingConsentMarker = { ...versions, recordedAt: now };
  storage.setItem(CONSENT_MARKER_KEY, JSON.stringify(marker));
}

/** Null if there's no marker, it's malformed, or it's aged out. */
export function readPendingConsent(
  storage: ReadableStorage,
  now: number = Date.now()
): PendingConsentMarker | null {
  const raw = storage.getItem(CONSENT_MARKER_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<PendingConsentMarker>;
    if (
      typeof parsed.termsVersion !== "string" ||
      typeof parsed.privacyVersion !== "string" ||
      typeof parsed.recordedAt !== "number"
    ) {
      return null;
    }
    if (now - parsed.recordedAt > MAX_MARKER_AGE_MS) return null;
    return { termsVersion: parsed.termsVersion, privacyVersion: parsed.privacyVersion, recordedAt: parsed.recordedAt };
  } catch {
    return null;
  }
}

export function clearPendingConsent(storage: ClearableStorage): void {
  storage.removeItem(CONSENT_MARKER_KEY);
}

export type ConsentSyncOutcome = "synced" | "no-marker" | "no-token" | "failed";

/**
 * Posts the pending marker once a backend access token is available.
 * Leaves the marker in place on failure (network blip, backend
 * restarting) so a later call — e.g. the next session read — retries,
 * bounded by the marker's own staleness check above.
 */
export async function syncPendingConsentIfNeeded({
  storage,
  accessToken,
  apiBaseUrl,
  fetchImpl,
  now,
}: {
  storage: ReadableStorage & WritableStorage & ClearableStorage;
  accessToken: string | undefined;
  apiBaseUrl: string;
  fetchImpl: typeof fetch;
  now?: number;
}): Promise<ConsentSyncOutcome> {
  const marker = readPendingConsent(storage, now);
  if (!marker) return "no-marker";
  if (!accessToken) return "no-token";

  try {
    const response = await fetchImpl(`${apiBaseUrl.replace(/\/+$/, "")}/users/consent`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify({
        terms_version: marker.termsVersion,
        privacy_version: marker.privacyVersion,
      }),
    });
    if (!response.ok) return "failed";
    clearPendingConsent(storage);
    return "synced";
  } catch {
    return "failed";
  }
}
