"""Single source of truth for the currently-published legal document
version. Bump this string whenever `/terms` or `/privacy` copy changes,
alongside the matching `LEGAL_VERSION` constant in the frontend
(`frontend/lib/legal/version.ts`) — the backend always stamps *its own*
value when recording consent (see `POST /users/consent`); the frontend's
copy of the constant is only used to detect a stale build.
"""

CURRENT_LEGAL_VERSION = "2026-07-07"
