/**
 * The real Auth.js `jwt`/`session` callback logic, extracted from
 * `auth.ts` so the exact token/session field names and transformations the
 * app depends on are unit-testable (see `callbacks.test.ts`). Everything
 * here runs server-side only (Node or Edge) — the raw Google ID token and
 * the backend access token live in the encrypted, HttpOnly Auth.js JWT
 * cookie and are never readable by browser JavaScript; the session object
 * exposes only the short-lived backend access token itself.
 *
 * Lifecycle:
 * - Sign-in stores the Google ID token as `pendingGoogleIdToken`, then the
 *   bootstrap step exchanges it at `POST /users/sync` for a backend access
 *   token. The pending token is kept until the exchange SUCCEEDS — a
 *   transient failure (backend restarting, brief network issue) retries on
 *   the next session read instead of silently poisoning the session, and
 *   is bounded by the Google token's own ~1h expiry.
 * - A valid backend token renews server-side via `POST /users/refresh`
 *   inside `RENEW_WINDOW_MS` of its expiry, so an active session never
 *   needs another Google round-trip.
 * - Only when neither exists (token expired while idle AND no live Google
 *   ID token to retry with) does the session report `needsBackendReauth`,
 *   whose one repair is a fresh Google sign-in.
 */

import type { Session } from "next-auth";
import type { JWT } from "next-auth/jwt";

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(
  /\/+$/,
  ""
);

// How long before the backend token's expiry renewal starts. Must be
// comfortably shorter than the backend's 12h TTL, long enough that an
// active session renews well before the deadline.
export const RENEW_WINDOW_MS = 60 * 60 * 1000;

interface BackendTokenResponse {
  user: { id: number };
  access_token: string;
  expires_in: number;
}

function applyBackendTokenResponse(token: JWT, body: BackendTokenResponse): void {
  token.backendUserId = body.user.id;
  token.backendAccessToken = body.access_token;
  token.backendAccessTokenExpiresAt = Date.now() + body.expires_in * 1000;
}

/**
 * Reads a JWT's `exp` without verifying anything — verification is solely
 * the backend's job (`app/core/google_oidc.py`); this only decides whether
 * retrying the sync with this token can possibly still succeed.
 */
export function idTokenIsExpired(idToken: string, nowMs: number = Date.now()): boolean {
  try {
    const payloadSegment = idToken.split(".")[1];
    const payload = JSON.parse(
      atob(payloadSegment.replace(/-/g, "+").replace(/_/g, "/"))
    ) as { exp?: number };
    if (typeof payload.exp !== "number") return true;
    return nowMs >= payload.exp * 1000;
  } catch {
    return true;
  }
}

async function syncBackendUser(token: JWT): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/users/sync`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id_token: token.pendingGoogleIdToken }),
    });
    if (!response.ok) {
      // Server-side log only — status code, never token values. The
      // backend logs its own verification-failure reason alongside this.
      console.warn(`[auth] backend user sync failed with status ${response.status}`);
      return false;
    }
    applyBackendTokenResponse(token, (await response.json()) as BackendTokenResponse);
    return true;
  } catch {
    console.warn("[auth] backend user sync failed: backend unreachable");
    return false;
  }
}

async function renewBackendToken(token: JWT): Promise<void> {
  try {
    const response = await fetch(`${API_BASE_URL}/users/refresh`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token.backendAccessToken}` },
    });
    if (response.ok) {
      applyBackendTokenResponse(token, (await response.json()) as BackendTokenResponse);
    } else if (response.status === 401) {
      // The backend considers this token dead — drop it rather than keep
      // sending it. (Other statuses: keep the still-valid token and let a
      // later invocation inside the renewal window retry.)
      console.warn("[auth] backend token renewal rejected with 401");
      delete token.backendAccessToken;
      delete token.backendAccessTokenExpiresAt;
    }
  } catch {
    // Backend unreachable — retry on a later invocation.
  }
}

export async function jwtCallback({
  token,
  account,
}: {
  token: JWT;
  account?: { id_token?: string } | null;
}): Promise<JWT> {
  if (account?.id_token) {
    token.pendingGoogleIdToken = account.id_token;
  }

  // Bootstrap: a Google ID token is waiting to be exchanged — either the
  // sign-in that just completed, or an earlier exchange that failed and is
  // retried on this session read. Cleared on success or its own expiry.
  if (token.pendingGoogleIdToken) {
    if (idTokenIsExpired(token.pendingGoogleIdToken)) {
      delete token.pendingGoogleIdToken;
    } else if (await syncBackendUser(token)) {
      delete token.pendingGoogleIdToken;
    }
  }

  // Renewal/expiry: an already-expired token is dropped (never sent as a
  // dead header); one nearing expiry renews while it can still
  // authenticate the renewal call itself.
  if (token.backendAccessToken && token.backendAccessTokenExpiresAt !== undefined) {
    if (Date.now() >= token.backendAccessTokenExpiresAt) {
      delete token.backendAccessToken;
      delete token.backendAccessTokenExpiresAt;
    } else if (Date.now() > token.backendAccessTokenExpiresAt - RENEW_WINDOW_MS) {
      await renewBackendToken(token);
    }
  }

  return token;
}

export async function sessionCallback({
  session,
  token,
}: {
  session: Session;
  token: JWT;
}): Promise<Session> {
  if (token.backendUserId !== undefined) {
    session.user.backendUserId = token.backendUserId;
  }

  const expired =
    token.backendAccessTokenExpiresAt !== undefined &&
    Date.now() >= token.backendAccessTokenExpiresAt;

  if (token.backendAccessToken && !expired) {
    session.backendAccessToken = token.backendAccessToken;
  } else if (token.pendingGoogleIdToken && !idTokenIsExpired(token.pendingGoogleIdToken)) {
    // Recoverable: the bootstrap exchange hasn't succeeded yet but can
    // still be retried — surface "in progress", never a re-login prompt.
    session.backendAuthPending = true;
  } else {
    // Unrecoverable without a fresh Google sign-in.
    session.needsBackendReauth = true;
  }

  return session;
}
