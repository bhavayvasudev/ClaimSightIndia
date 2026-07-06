# Security notes

## Authentication

The frontend uses Auth.js (NextAuth v5) with the default JWT session
strategy and Google as the only provider. On every real sign-in, `auth.ts`'s
`jwt` callback sends the raw Google ID token (`account.id_token`) to
`POST /users/sync`. The backend independently verifies that token's
signature, issuer and audience against Google's JWKS
(`app/core/google_oidc.py`) — it never trusts client-asserted
`google_sub`/`email`/`name`/`avatar_url` — then upserts the user and issues
its own short-lived HS256 access token (`app/core/security.py`,
`BACKEND_JWT_SECRET`, default 12h TTL). That token rides in the NextAuth
session as `session.backendAccessToken` and is sent as
`Authorization: Bearer` on every claim request. `get_current_user` is the
one FastAPI dependency that verifies it and resolves the owning user; every
claim route depends on it, and claim ownership is always derived from the
verified token, never from a request body field.

## Claim ownership

`GET /claims/{id}` and `POST /claims/{id}/analyze` both resolve the claim
via `ClaimRepository.get_by_claim_id_for_user(claim_id, current_user.id)`,
which returns `None` identically for "doesn't exist" and "belongs to
someone else" — both surface as a plain 404, never a 403, so a client can't
distinguish "wrong owner" from "no such claim".

## Rate limiting

`slowapi` (`app/core/rate_limit.py`), keyed by authenticated user id when a
bearer token is present, else by the direct client IP (`request.client.host`
— never `X-Forwarded-For`, since this deployment has no trusted reverse
proxy in front of it yet). Storage is `RATE_LIMIT_STORAGE_URI`
(`memory://` by default — per-process, correct for local dev or a single
instance only). **Before running more than one backend instance in
production, point this at a shared Redis-compatible store** (e.g.
`redis://<host>:6379`), or each instance enforces its own independent
limit and the effective limit multiplies by instance count.

## ai-service exposure

The ai-service (`ai-service/main.py`) is called server-to-server only, from
`backend/app/services/ai_client.py` — it has no CORS configuration (a
browser can't read its responses cross-origin) and is not part of
`infra/docker-compose.yml` today. **In production, keep it on a private
network unreachable from outside the backend** (e.g. a Docker network with
no published port, or an equivalent private-subnet/service-mesh setup).
As an optional second layer — not a replacement for network isolation —
set `AI_SERVICE_SHARED_SECRET` to the same value in both the backend and
the ai-service; the backend then attaches it as `X-Internal-Service-Token`
on every request, and the ai-service rejects any request missing or
mismatching it. Left unset (the default), no such check runs, which is
fine as long as network isolation holds.

## Upload validation

Enforced in `backend/app/api/routes/claims.py` before any bytes reach the
ai-service (and redundantly in `ai-service/main.py`, since that service
does not assume the backend is its only possible caller):

- max 10 images per analyze request (`too_many_files`)
- max 10MB per image (`file_too_large`)
- content-type restricted to JPEG/PNG/WebP (`unsupported_file_type`)
- the bytes must actually decode as an image via Pillow, not just claim
  the right content-type (`corrupted_image`)
- vehicle-presence validation (`vehicle_not_detected`) is unchanged and
  still runs only after all of the above pass

All four are distinct, stable `error_code`s in the same
`{"error_code", "message", "invalid_filenames"}` shape (a 422), so the
frontend never has to guess which check failed from a string message.

## Secrets

`BACKEND_JWT_SECRET` and `AUTH_GOOGLE_CLIENT_ID` are required (the app
fails to start without them) whenever `ENVIRONMENT=production`
(`app/config.py`). Generate `BACKEND_JWT_SECRET` with
`openssl rand -base64 48`; never reuse the frontend's `AUTH_SECRET` for it
— they protect different things and rotate on different schedules.
