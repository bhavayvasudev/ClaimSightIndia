/**
 * Application backend base URL. The browser only ever calls this — the
 * ai-service URL is a backend-only concern (`AI_SERVICE_URL` in
 * `backend/app/config.py`) and must never be exposed to the frontend.
 */
export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(
  /\/+$/,
  ""
);
