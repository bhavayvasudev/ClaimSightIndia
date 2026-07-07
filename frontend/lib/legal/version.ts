/**
 * Bump alongside any change to `/terms` or `/privacy` copy, and keep in
 * sync with the backend's own `CURRENT_LEGAL_VERSION`
 * (`backend/app/core/legal.py`) — the backend never trusts this value as
 * the persisted record, it only compares against it to log a mismatch
 * from a stale frontend build.
 */
export const LEGAL_VERSION = "2026-07-07";

export const LEGAL_LAST_UPDATED_LABEL = "7 July 2026";
