/**
 * Typed client for the application backend's claim API. Every network call
 * in the app goes through one of these three functions — components never
 * call `fetch` directly, so the base URL and error mapping stay in one place.
 */

import { API_BASE_URL } from "./config";
import { ApiError, type ApiErrorDetail } from "./errors";
import type {
  ClaimListResponse,
  ClaimResponse,
  CreateClaimInput,
  NotificationItem,
  NotificationListResponse,
  PolicyDocumentResponse,
  ProfileUpdateInput,
  TimelineResponse,
  UnifiedClaimReport,
  UserProfile,
  VehicleCatalogModel,
  VehicleManufacturer,
} from "./types";

function isApiErrorDetail(value: unknown): value is ApiErrorDetail {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as Record<string, unknown>).error_code === "string" &&
    Array.isArray((value as Record<string, unknown>).invalid_filenames)
  );
}

const ALLOWED_IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

export function isSupportedImageFile(file: File): boolean {
  return ALLOWED_IMAGE_TYPES.has(file.type);
}

/** Attaches `Authorization: Bearer <token>` when a token is given — every
 * claim route requires one; the backend derives ownership from it,
 * never from anything in the request body. */
function authHeaders(token: string | undefined): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch (err) {
    // fetch throws on DNS/connection failure or an AbortController abort —
    // there is no HTTP status yet. The rejection's error name ("AbortError"
    // for our own timeout vs "TypeError" for a real network drop) is the
    // only way to tell those apart later, so it rides along in `detail`
    // (diagnostics only, never shown in the UI).
    throw new ApiError(
      "Unable to reach the ClaimSight service.",
      0,
      err instanceof Error ? err.name : undefined
    );
  }

  if (!response.ok) {
    let detail: string | undefined;
    let structuredDetail: ApiErrorDetail | undefined;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body?.detail === "string") {
        detail = body.detail;
      } else if (isApiErrorDetail(body?.detail)) {
        structuredDetail = body.detail;
      }
    } catch {
      // Body wasn't JSON — no further detail available.
    }

    if (process.env.NODE_ENV !== "production") {
      // Technical detail stays in dev logs only, never the UI.
      console.error(`[ClaimSight API] ${response.status} ${path}`, detail ?? structuredDetail);
    }

    throw new ApiError(`Request to ${path} failed`, response.status, detail, structuredDetail);
  }

  return response.json() as Promise<T>;
}

export function createClaim(input: CreateClaimInput, token: string | undefined): Promise<ClaimResponse> {
  return request<ClaimResponse>("/claims", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify(input),
  });
}

export function analyzeClaim(
  claimId: string,
  images: File[],
  token: string | undefined,
  options?: { timeoutMs?: number }
): Promise<ClaimResponse> {
  const formData = new FormData();
  images.forEach((file) => formData.append("images", file));

  // A bounded wait, not a failure boundary: analysis keeps running
  // server-side after an abort, so callers that pass `timeoutMs` are
  // expected to reconcile against real claim status afterwards (see
  // lib/claims/analysisRunner.ts) rather than reporting an error. The
  // abort surfaces as ApiError status 0, same as any transport failure.
  const timeoutMs = options?.timeoutMs;
  const controller = timeoutMs ? new AbortController() : null;
  const timer = controller ? setTimeout(() => controller.abort(), timeoutMs) : null;

  return request<ClaimResponse>(`/claims/${encodeURIComponent(claimId)}/analyze`, {
    method: "POST",
    headers: authHeaders(token),
    body: formData,
    ...(controller ? { signal: controller.signal } : {}),
  }).finally(() => {
    if (timer) clearTimeout(timer);
  });
}

export function getClaim(claimId: string, token: string | undefined): Promise<ClaimResponse> {
  return request<ClaimResponse>(`/claims/${encodeURIComponent(claimId)}`, {
    headers: authHeaders(token),
  });
}

/** Newest-first claim history for the signed-in user (dashboard). Scoped
 * to the caller's own claims server-side — there is no client-supplied
 * user filter to pass here. */
export function listClaims(token: string | undefined): Promise<ClaimListResponse> {
  return request<ClaimListResponse>("/claims", {
    headers: authHeaders(token),
  });
}

export function uploadPolicyDocument(
  claimId: string,
  file: File,
  token: string | undefined
): Promise<PolicyDocumentResponse> {
  const formData = new FormData();
  formData.append("file", file);

  return request<PolicyDocumentResponse>(`/claims/${encodeURIComponent(claimId)}/policy`, {
    method: "POST",
    headers: authHeaders(token),
    body: formData,
  });
}

export function getPolicyStatus(
  claimId: string,
  token: string | undefined
): Promise<PolicyDocumentResponse> {
  return request<PolicyDocumentResponse>(`/claims/${encodeURIComponent(claimId)}/policy`, {
    headers: authHeaders(token),
  });
}

export function getClaimReport(claimId: string, token: string | undefined): Promise<UnifiedClaimReport> {
  return request<UnifiedClaimReport>(`/claims/${encodeURIComponent(claimId)}/report`, {
    headers: authHeaders(token),
  });
}

export function getClaimTimeline(claimId: string, token: string | undefined): Promise<TimelineResponse> {
  return request<TimelineResponse>(`/claims/${encodeURIComponent(claimId)}/timeline`, {
    headers: authHeaders(token),
  });
}

/** Downloads the PDF report as a Blob — a plain `<a href>` can't carry the
 * Authorization header this route requires, so the caller fetches the
 * bytes here and hands the browser an object URL to trigger the download. */
export async function downloadClaimReportPdf(claimId: string, token: string | undefined): Promise<Blob> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/claims/${encodeURIComponent(claimId)}/report/pdf`, {
      headers: authHeaders(token),
    });
  } catch {
    throw new ApiError("Unable to reach the ClaimSight service.", 0);
  }
  if (!response.ok) {
    throw new ApiError(`Request to /claims/${claimId}/report/pdf failed`, response.status);
  }
  return response.blob();
}

export function listNotifications(token: string | undefined): Promise<NotificationListResponse> {
  return request<NotificationListResponse>("/notifications", {
    headers: authHeaders(token),
  });
}

export function markNotificationRead(id: number, token: string | undefined): Promise<NotificationItem> {
  return request<NotificationItem>(`/notifications/${id}/read`, {
    method: "POST",
    headers: authHeaders(token),
  });
}

export function markAllNotificationsRead(token: string | undefined): Promise<{ status: string }> {
  return request<{ status: string }>("/notifications/read-all", {
    method: "POST",
    headers: authHeaders(token),
  });
}

/** The signed-in user's own profile — identity always derives from the
 * bearer token server-side; there is no user-id parameter to pass. */
export function getMyProfile(token: string | undefined): Promise<UserProfile> {
  return request<UserProfile>("/users/me", {
    headers: authHeaders(token),
  });
}

export function updateMyProfile(
  input: ProfileUpdateInput,
  token: string | undefined
): Promise<UserProfile> {
  return request<UserProfile>("/users/me", {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify(input),
  });
}

export function uploadMyAvatar(file: File, token: string | undefined): Promise<UserProfile> {
  const formData = new FormData();
  formData.append("file", file);
  return request<UserProfile>("/users/me/avatar", {
    method: "POST",
    headers: authHeaders(token),
    body: formData,
  });
}

/** "Use Google photo" — clears the custom avatar server-side. */
export function resetMyAvatar(token: string | undefined): Promise<UserProfile> {
  return request<UserProfile>("/users/me/avatar", {
    method: "DELETE",
    headers: authHeaders(token),
  });
}

/** Public reference data — no bearer token, same for every caller. */
export function listVehicleManufacturers(): Promise<VehicleManufacturer[]> {
  return request<VehicleManufacturer[]>("/vehicle-catalog/manufacturers");
}

export function listVehicleModels(manufacturerId: string): Promise<VehicleCatalogModel[]> {
  return request<VehicleCatalogModel[]>(
    `/vehicle-catalog/manufacturers/${encodeURIComponent(manufacturerId)}/models`
  );
}

// No variant/trim client call: variant selection was removed from the
// claim flow (manufacturer → model → year). The backend catalog may
// retain variant data internally, but the claim UX never depends on it.
