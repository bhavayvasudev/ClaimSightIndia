import NextAuth from "next-auth";
import Google from "next-auth/providers/google";
import { jwtCallback, sessionCallback } from "@/lib/auth/callbacks";

/**
 * Gates the real claim-assessment flow. The application backend has no
 * OAuth handshake of its own — this session is what proves someone signed
 * in — and the callbacks (extracted to `lib/auth/callbacks.ts` so their
 * exact token/session transformations are unit-tested) bridge it to the
 * backend: the raw Google ID token from a sign-in is exchanged server-side
 * at `POST /users/sync` (the backend independently verifies it against
 * Google — see `backend/app/core/google_oidc.py`) for a short-lived
 * backend access token. That token — not any locally-known user id — is
 * what rides in the session and gets sent as `Authorization: Bearer` on
 * every claim request, so the backend derives claim ownership itself
 * instead of trusting a client-supplied value. A failed exchange retries
 * on later session reads while the Google token is still valid, and a live
 * backend token renews via `POST /users/refresh` — see the lifecycle notes
 * in `lib/auth/callbacks.ts`.
 */
export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [Google],
  // Custom provider-choice screen (frontend/app/signin/page.tsx) instead of
  // Auth.js's built-in generic page — Google is the only functional
  // provider there; Apple/Facebook are inert "Coming soon" buttons with no
  // Auth.js provider registered for either.
  pages: {
    signIn: "/signin",
  },
  callbacks: {
    jwt: ({ token, account }) => jwtCallback({ token, account }),
    session: ({ session, token }) => sessionCallback({ session, token }),
  },
});
