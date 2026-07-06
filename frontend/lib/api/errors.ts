/**
 * Single place that maps a failed backend call into a message safe to show
 * a claimant. Never surfaces raw backend `detail` text (which may contain
 * exception-derived phrasing) in the normal UI — only these fixed strings.
 */

/** Structured rejection body from a failed create/analyze call. See
 * `backend/app/api/routes/claims.py` and `ai-service/main.py` for the
 * exact set of `error_code`s this can carry: `vehicle_not_detected`,
 * `unsupported_file_type`, `file_too_large`, `too_many_files`,
 * `corrupted_image`. Kept generic (not a union) since new codes are
 * additive and `userFacingMessage` below falls back to a stock message
 * for any it doesn't special-case. */
export interface ApiErrorDetail {
  error_code: string;
  message: string;
  invalid_filenames: string[];
}

export class ApiError extends Error {
  /** HTTP status code, or 0 for a network-level failure (fetch threw). */
  status: number;
  /** Raw backend detail, if any — for development logs only, never the UI,
   * UNLESS it's a structured `ApiErrorDetail` (see `structuredDetail`). */
  detail?: string;
  /** Present only when the backend returned a structured rejection body
   * (`{error_code, message, invalid_filenames}`) — safe to show the user,
   * since it's a deliberate, user-actionable validation result, not an
   * internal error message. */
  structuredDetail?: ApiErrorDetail;

  constructor(message: string, status: number, detail?: string, structuredDetail?: ApiErrorDetail) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.structuredDetail = structuredDetail;
  }
}

const STATUS_MESSAGES: Record<number, string> = {
  0: "Unable to reach the ClaimSight service.",
  400: "One or more selected files are unsupported.",
  401: "Please sign in again to continue.",
  403: "You don't have access to this claim.",
  404: "The claim could not be found.",
  422: "The submitted claim details couldn't be validated. Please check the form and try again.",
  429: "Too many requests. Please wait a moment and try again.",
  502: "The assessment service returned an invalid result. Please retry.",
  503: "The assessment service is temporarily unavailable. Please try again shortly.",
  504: "The assessment took too long. Please retry.",
};

/** Messages for structured `error_code`s that need the invalid filename
 * list rendered inline — anything not listed here just falls through to
 * `STATUS_MESSAGES` for its HTTP status. */
const ERROR_CODE_MESSAGES: Record<string, (files: string) => string> = {
  vehicle_not_detected: (files) =>
    `These photos don't appear to show a vehicle: ${files}. Remove them and try again.`,
  corrupted_image: (files) => `These files couldn't be read as images: ${files}. Try re-exporting them.`,
  unsupported_file_type: (files) =>
    `These files aren't a supported image type: ${files}. Use JPEG, PNG, or WebP.`,
  file_too_large: (files) => `These files are too large: ${files}. Each photo must be under 10MB.`,
  too_many_files: () => "Too many photos in one submission. Remove some and try again.",
};

const FALLBACK_MESSAGE = "Something went wrong. Please try again.";

export function userFacingMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const detail = error.structuredDetail;
    if (detail && detail.error_code in ERROR_CODE_MESSAGES) {
      return ERROR_CODE_MESSAGES[detail.error_code](detail.invalid_filenames.join(", "));
    }
    return STATUS_MESSAGES[error.status] ?? FALLBACK_MESSAGE;
  }
  return FALLBACK_MESSAGE;
}
