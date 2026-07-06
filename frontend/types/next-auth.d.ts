import type { DefaultSession } from "next-auth";

/**
 * Adds the backend's own user id and its short-lived access token to the
 * session/JWT — managed by the callbacks in `lib/auth/callbacks.ts` after
 * syncing the Google profile to `POST /users/sync`. `backendAccessToken`
 * is what the frontend sends as `Authorization: Bearer` on every claim
 * request; the backend derives ownership from it, never from a
 * client-supplied id.
 */
declare module "next-auth" {
  interface Session {
    user: {
      backendUserId?: number;
    } & DefaultSession["user"];
    backendAccessToken?: string;
    /** Set when the signed-in session has no backend token *yet* but the
     * Google ID token from sign-in is still valid, so the server-side
     * exchange retries on upcoming session reads. UI should treat this as
     * a brief loading state, never a re-login prompt. */
    backendAuthPending?: boolean;
    /** Set (instead of `backendAccessToken`) when the signed-in Auth.js
     * session has no usable backend token and no way left to obtain one
     * server-side — expired while idle, or the sign-in-time exchange never
     * succeeded before the Google ID token itself expired. Derived per
     * session read in `lib/auth/callbacks.ts`, never stored on the JWT.
     * The only repair is a fresh Google sign-in, so UI reacting to this
     * must offer `signIn("google")`, never auto-retry the failed request. */
    needsBackendReauth?: boolean;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    backendUserId?: number;
    backendAccessToken?: string;
    backendAccessTokenExpiresAt?: number;
    /** The raw Google ID token from the latest sign-in, retained ONLY
     * until the backend exchange succeeds (or the token expires), so a
     * transient failure doesn't permanently poison the session. Lives in
     * the encrypted, HttpOnly Auth.js cookie — server-side only, never
     * exposed on the Session object. */
    pendingGoogleIdToken?: string;
  }
}

// NextAuth's own callback signatures (in `NextAuth(config)`) type their
// `token` param via `@auth/core/jwt` directly, not via the `next-auth/jwt`
// re-export above — augmenting only the latter leaves `token` inside
// `auth.ts`'s callbacks unaugmented, so both are declared here.
declare module "@auth/core/jwt" {
  interface JWT {
    backendUserId?: number;
    backendAccessToken?: string;
    backendAccessTokenExpiresAt?: number;
    pendingGoogleIdToken?: string;
  }
}
