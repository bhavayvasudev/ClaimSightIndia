/**
 * Application backend base URL. The browser only ever calls this — the
 * ai-service URL is a backend-only concern (`AI_SERVICE_URL` in
 * `backend/app/config.py`) and must never be exposed to the frontend.
 */
export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(
  /\/+$/,
  ""
);

/**
 * Resolves an image/asset path from an API response to a browser-loadable
 * URL. Backend-served reference vehicle images arrive as "/vehicle-images/…"
 * (served by the backend's own route — see
 * backend/app/api/routes/vehicle_images.py) and need the API origin
 * prefixed; frontend-hosted assets ("/vehicle-reference/…" category
 * illustrations in public/) and absolute URLs pass through untouched.
 */
export function resolveAssetUrl(path: string): string {
  if (path.startsWith("/vehicle-images/") || path.startsWith("/avatars/")) {
    return `${API_BASE_URL}${path}`;
  }
  return path;
}
