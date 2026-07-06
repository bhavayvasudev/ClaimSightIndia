/**
 * Regression tests for the real Auth.js callback logic — the exact
 * field names and transformations `auth.ts` wires into NextAuth and the
 * API client reads back (`session.backendAccessToken`). These reproduce
 * the two production incidents:
 *  - a sign-in whose backend exchange failed left a 30-day session
 *    permanently without a backend token ("Your session needs to be
 *    refreshed" forever, even after re-authenticating);
 *  - subsequent jwt-callback executions without a new OAuth `account`
 *    must never erase previously stored backend token state.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Session } from "next-auth";
import type { JWT } from "next-auth/jwt";
import {
  RENEW_WINDOW_MS,
  idTokenIsExpired,
  jwtCallback,
  sessionCallback,
} from "@/lib/auth/callbacks";

function base64url(value: string): string {
  return Buffer.from(value)
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

/** Structurally a Google ID token (unsigned — the backend is what
 * verifies signatures; the frontend only ever reads `exp`). */
function makeGoogleIdToken(expDeltaSeconds: number): string {
  const header = base64url(JSON.stringify({ alg: "RS256", kid: "test" }));
  const payload = base64url(
    JSON.stringify({ exp: Math.floor(Date.now() / 1000) + expDeltaSeconds, sub: "google-sub" })
  );
  return `${header}.${payload}.signature`;
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const BACKEND_TOKEN_BODY = { user: { id: 42 }, access_token: "bk-tok-1", expires_in: 43200 };

function freshSession(): Session {
  return { user: {}, expires: "" } as Session;
}

const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  vi.spyOn(console, "warn").mockImplementation(() => {});
});

afterEach(() => {
  fetchMock.mockReset();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("sign-in bootstrap", () => {
  it("exchanges the Google ID token at /users/sync and stores the exact fields the app reads", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, BACKEND_TOKEN_BODY));
    const idToken = makeGoogleIdToken(3600);

    const token = await jwtCallback({ token: {} as JWT, account: { id_token: idToken } });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/users/sync");
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({ id_token: idToken });

    expect(token.backendUserId).toBe(42);
    expect(token.backendAccessToken).toBe("bk-tok-1");
    expect(token.backendAccessTokenExpiresAt).toBeGreaterThan(Date.now());
    // Exchange succeeded — the Google ID token must not linger.
    expect(token.pendingGoogleIdToken).toBeUndefined();
  });

  it("preserves backend token state on later invocations without a new OAuth account", async () => {
    const stored: JWT = {
      backendUserId: 42,
      backendAccessToken: "bk-tok-1",
      backendAccessTokenExpiresAt: Date.now() + RENEW_WINDOW_MS * 3,
    } as JWT;

    const token = await jwtCallback({ token: stored, account: null });

    expect(fetchMock).not.toHaveBeenCalled();
    expect(token.backendAccessToken).toBe("bk-tok-1");
    expect(token.backendUserId).toBe(42);
  });

  it("retries a failed exchange on the next session read instead of poisoning the session", async () => {
    // Sign-in happens while the backend is unreachable.
    fetchMock.mockRejectedValueOnce(new TypeError("fetch failed"));
    const idToken = makeGoogleIdToken(3600);
    let token = await jwtCallback({ token: {} as JWT, account: { id_token: idToken } });

    expect(token.backendAccessToken).toBeUndefined();
    expect(token.pendingGoogleIdToken).toBe(idToken);

    // While recoverable, the session reports "pending", never a re-login prompt.
    const midSession = await sessionCallback({ session: freshSession(), token });
    expect(midSession.backendAuthPending).toBe(true);
    expect(midSession.needsBackendReauth).toBeUndefined();
    expect(midSession.backendAccessToken).toBeUndefined();

    // Next session read — no new OAuth account — completes the exchange.
    fetchMock.mockResolvedValueOnce(jsonResponse(200, BACKEND_TOKEN_BODY));
    token = await jwtCallback({ token, account: null });

    expect(token.backendAccessToken).toBe("bk-tok-1");
    expect(token.pendingGoogleIdToken).toBeUndefined();

    const readySession = await sessionCallback({ session: freshSession(), token });
    expect(readySession.backendAccessToken).toBe("bk-tok-1");
    expect(readySession.backendAuthPending).toBeUndefined();
    expect(readySession.needsBackendReauth).toBeUndefined();
  });

  it("stops retrying once the Google ID token itself has expired and reports reauth", async () => {
    const token = await jwtCallback({
      token: { pendingGoogleIdToken: makeGoogleIdToken(-60) } as JWT,
      account: null,
    });

    expect(fetchMock).not.toHaveBeenCalled();
    expect(token.pendingGoogleIdToken).toBeUndefined();

    const session = await sessionCallback({ session: freshSession(), token });
    expect(session.needsBackendReauth).toBe(true);
    expect(session.backendAuthPending).toBeUndefined();
    expect(session.backendAccessToken).toBeUndefined();
  });
});

describe("renewal and expiry", () => {
  it("renews a token nearing expiry via /users/refresh, authenticated by the current token", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(200, { ...BACKEND_TOKEN_BODY, access_token: "bk-tok-2" })
    );
    const stored: JWT = {
      backendUserId: 42,
      backendAccessToken: "bk-tok-1",
      backendAccessTokenExpiresAt: Date.now() + RENEW_WINDOW_MS / 2,
    } as JWT;

    const token = await jwtCallback({ token: stored, account: null });

    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/users/refresh");
    expect((init as RequestInit).headers).toMatchObject({
      Authorization: "Bearer bk-tok-1",
    });
    expect(token.backendAccessToken).toBe("bk-tok-2");
  });

  it("drops a token the backend rejects with 401 and the session reports reauth", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(401, { detail: "Authentication required." }));
    const stored: JWT = {
      backendAccessToken: "bk-tok-1",
      backendAccessTokenExpiresAt: Date.now() + RENEW_WINDOW_MS / 2,
    } as JWT;

    const token = await jwtCallback({ token: stored, account: null });
    expect(token.backendAccessToken).toBeUndefined();

    const session = await sessionCallback({ session: freshSession(), token });
    expect(session.needsBackendReauth).toBe(true);
  });

  it("drops an already-expired token without ever sending it", async () => {
    const stored: JWT = {
      backendAccessToken: "bk-tok-1",
      backendAccessTokenExpiresAt: Date.now() - 1000,
    } as JWT;

    const token = await jwtCallback({ token: stored, account: null });

    expect(fetchMock).not.toHaveBeenCalled();
    expect(token.backendAccessToken).toBeUndefined();

    const session = await sessionCallback({ session: freshSession(), token });
    expect(session.needsBackendReauth).toBe(true);
  });
});

describe("session exposure", () => {
  it("exposes a valid token under the exact names the API client reads", async () => {
    const session = await sessionCallback({
      session: freshSession(),
      token: {
        backendUserId: 42,
        backendAccessToken: "bk-tok-1",
        backendAccessTokenExpiresAt: Date.now() + 60_000,
      } as JWT,
    });

    expect(session.backendAccessToken).toBe("bk-tok-1");
    expect(session.user.backendUserId).toBe(42);
    expect(session.backendAuthPending).toBeUndefined();
    expect(session.needsBackendReauth).toBeUndefined();
  });
});

describe("idTokenIsExpired", () => {
  it("reads exp from a well-formed token", () => {
    expect(idTokenIsExpired(makeGoogleIdToken(3600))).toBe(false);
    expect(idTokenIsExpired(makeGoogleIdToken(-1))).toBe(true);
  });

  it("treats malformed tokens as expired", () => {
    expect(idTokenIsExpired("not-a-jwt")).toBe(true);
    expect(idTokenIsExpired("")).toBe(true);
  });
});
