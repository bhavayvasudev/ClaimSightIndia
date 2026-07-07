"""User sync + profile endpoints.

`POST /sync` is called server-side by the frontend's NextAuth `jwt`
callback on every Google sign-in (never from the browser directly) with
the raw Google ID token that sign-in just produced. This route
independently verifies that token (app.core.google_oidc) rather than
trusting client-asserted profile fields, upserts the basic profile, and
issues a short-lived backend access token the frontend then carries on
every claim request.

The `/me` routes are the profile-management surface. Identity is always
derived from the bearer token (`get_current_user`) — there is no
user-id parameter anywhere, so a user can only ever read or update
their own profile. The Google identity email and google_sub are not
editable through any of them (see the field-tier docstring on
`UserRecord`).
"""

from __future__ import annotations

import hashlib
import io
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.google_oidc import InvalidGoogleIdToken, verify_google_id_token
from app.core.legal import CURRENT_LEGAL_VERSION
from app.core.rate_limit import limiter
from app.core.security import get_current_user, issue_access_token
from app.db.models.user import UserRecord
from app.db.repository import ClaimRepository
from app.db.session import get_db
from app.db.user_repository import UserRepository
from app.schemas.user_api import (
    ClaimStats,
    ConsentAcceptRequest,
    UserProfileResponse,
    UserProfileUpdateRequest,
    UserResponse,
    UserSyncRequest,
    UserSyncResponse,
)
from app.services import user_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])

AVATAR_CONTENT_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
MAX_AVATAR_BYTES = 5 * 1024 * 1024
AVATAR_URL_PREFIX = "/avatars"

# Dashboard status grouping, mirrored from the frontend's
# lib/claimStatusGroups.ts — kept in the same coarse buckets so the
# profile stats can never disagree with the dashboard tabs.
_ACTIVE_STATUSES = {"intake", "analyzing"}
_UNDER_REVIEW_STATUSES = {"review_required"}
_COMPLETED_STATUSES = {"analysis_complete"}
_FAILED_STATUSES = {"failed"}


def _claim_stats(status_counts: dict[str, int]) -> ClaimStats:
    def total_for(statuses: set[str]) -> int:
        return sum(count for status, count in status_counts.items() if status in statuses)

    return ClaimStats(
        total=sum(status_counts.values()),
        active=total_for(_ACTIVE_STATUSES),
        under_review=total_for(_UNDER_REVIEW_STATUSES),
        completed=total_for(_COMPLETED_STATUSES),
        failed=total_for(_FAILED_STATUSES),
    )


def _remove_stored_avatar(custom_avatar_url: str | None) -> None:
    """Best-effort cleanup of a replaced/reset avatar file. Only ever
    deletes inside avatar_dir, and only filenames this app generated."""
    if not custom_avatar_url or not custom_avatar_url.startswith(f"{AVATAR_URL_PREFIX}/"):
        return
    filename = custom_avatar_url.removeprefix(f"{AVATAR_URL_PREFIX}/")
    directory = Path(get_settings().avatar_dir).resolve()
    path = (directory / filename).resolve()
    if directory in path.parents and path.is_file():
        try:
            path.unlink()
        except OSError:
            logger.warning("Could not remove replaced avatar file %s", filename)


@router.post("/sync", response_model=UserSyncResponse)
@limiter.limit("10/minute")
async def sync_user(
    request: Request, payload: UserSyncRequest, db: AsyncSession = Depends(get_db)
) -> UserSyncResponse:
    try:
        identity = verify_google_id_token(payload.id_token)
    except InvalidGoogleIdToken as exc:
        # The client only ever sees a generic 401, but the *reason* must be
        # visible server-side — a silent rejection here poisons every
        # sign-in with no trace (this is how a clock-skew `iat` failure
        # went undiagnosed). PyJWT/`InvalidGoogleIdToken` messages name the
        # failed check only; they never contain token material.
        logger.warning("google id_token verification failed: %s", exc)
        raise HTTPException(status_code=401, detail="Authentication required.")

    repo = UserRepository(db)
    record = await user_service.upsert_from_google(
        repo,
        google_sub=identity["sub"],
        email=identity["email"],
        name=identity["name"],
        avatar_url=identity["picture"],
    )
    access_token, expires_in = issue_access_token(record)
    return UserSyncResponse(
        user=UserResponse.from_record(record),
        access_token=access_token,
        expires_in=expires_in,
    )


@router.post("/refresh", response_model=UserSyncResponse)
@limiter.limit("30/minute")
async def refresh_access_token(
    request: Request, user: UserRecord = Depends(get_current_user)
) -> UserSyncResponse:
    """Re-issues a fresh access token for the bearer of a currently-valid
    one, so a long-lived frontend session can renew before the 12h token
    expiry without re-running Google sign-in. An expired or missing token
    gets the usual 401 from `get_current_user` — renewal never resurrects
    a dead session; only a new Google sign-in (`/users/sync`) can."""
    access_token, expires_in = issue_access_token(user)
    return UserSyncResponse(
        user=UserResponse.from_record(user),
        access_token=access_token,
        expires_in=expires_in,
    )


@router.post("/consent", response_model=UserProfileResponse)
@limiter.limit("20/minute")
async def accept_legal_consent(
    request: Request,
    payload: ConsentAcceptRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user),
) -> UserProfileResponse:
    """Records that the authenticated user affirmatively accepted the
    Terms of Service and Privacy Policy. The sign-in page's consent
    checkbox is the only place this is ever called from — the Google
    button there is disabled until it's checked. `CURRENT_LEGAL_VERSION`
    (never the client-reported version) is what actually gets persisted;
    a mismatch only gets logged, to catch a stale frontend build without
    blocking the sign-in it's gating."""
    if payload.terms_version != CURRENT_LEGAL_VERSION or payload.privacy_version != CURRENT_LEGAL_VERSION:
        logger.warning(
            "consent accept called with mismatched legal version (client terms=%s privacy=%s, server=%s)",
            payload.terms_version,
            payload.privacy_version,
            CURRENT_LEGAL_VERSION,
        )
    now = datetime.now(timezone.utc)
    current_user.terms_accepted_at = now
    current_user.privacy_accepted_at = now
    current_user.legal_version_accepted = CURRENT_LEGAL_VERSION
    record = await UserRepository(db).save(current_user)
    status_counts = await ClaimRepository(db).status_counts_for_user(record.id)
    return UserProfileResponse.from_record_with_stats(record, _claim_stats(status_counts))


@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(
    db: AsyncSession = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user),
) -> UserProfileResponse:
    status_counts = await ClaimRepository(db).status_counts_for_user(current_user.id)
    return UserProfileResponse.from_record_with_stats(current_user, _claim_stats(status_counts))


@router.patch("/me", response_model=UserProfileResponse)
@limiter.limit("20/minute")
async def update_my_profile(
    request: Request,
    payload: UserProfileUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user),
) -> UserProfileResponse:
    """Updates only the user-customizable tier. Omitted fields are left
    untouched; an explicit null clears the customization back to the
    provider-derived value (distinguished via `model_fields_set`)."""
    if "display_name" in payload.model_fields_set:
        current_user.display_name = payload.display_name
    if "contact_email" in payload.model_fields_set:
        current_user.contact_email = payload.contact_email

    record = await UserRepository(db).save(current_user)
    status_counts = await ClaimRepository(db).status_counts_for_user(record.id)
    return UserProfileResponse.from_record_with_stats(record, _claim_stats(status_counts))


@router.post("/me/avatar", response_model=UserProfileResponse)
@limiter.limit("10/minute")
async def upload_my_avatar(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user),
) -> UserProfileResponse:
    """Stores a new custom avatar under a server-generated
    content-addressed filename (the original filename is never used as a
    storage path) and points custom_avatar_url at this app's own
    /avatars/ route."""
    extension = AVATAR_CONTENT_TYPES.get(file.content_type or "")
    if extension is None:
        raise HTTPException(status_code=422, detail="Only JPEG, PNG and WebP images are supported.")

    content = await file.read()
    if len(content) > MAX_AVATAR_BYTES:
        raise HTTPException(
            status_code=422,
            detail=f"Profile photo exceeds the {MAX_AVATAR_BYTES // (1024 * 1024)}MB limit.",
        )

    # The declared content type got it this far; the decode proves it.
    try:
        with Image.open(io.BytesIO(content)) as img:
            img.verify()
    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(status_code=422, detail="The file could not be read as an image.")

    directory = Path(get_settings().avatar_dir)
    directory.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(content).hexdigest()[:12]
    filename = f"u{current_user.id}-{digest}.{extension}"
    path = directory / filename
    if not path.exists():
        path.write_bytes(content)

    previous = current_user.custom_avatar_url
    current_user.custom_avatar_url = f"{AVATAR_URL_PREFIX}/{filename}"
    record = await UserRepository(db).save(current_user)
    if previous != current_user.custom_avatar_url:
        _remove_stored_avatar(previous)

    status_counts = await ClaimRepository(db).status_counts_for_user(record.id)
    return UserProfileResponse.from_record_with_stats(record, _claim_stats(status_counts))


@router.delete("/me/avatar", response_model=UserProfileResponse)
@limiter.limit("10/minute")
async def reset_my_avatar(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user),
) -> UserProfileResponse:
    """"Use Google photo": clears the custom avatar so the provider
    avatar becomes the effective one again. Identity data is untouched."""
    previous = current_user.custom_avatar_url
    current_user.custom_avatar_url = None
    record = await UserRepository(db).save(current_user)
    _remove_stored_avatar(previous)

    status_counts = await ClaimRepository(db).status_counts_for_user(record.id)
    return UserProfileResponse.from_record_with_stats(record, _claim_stats(status_counts))
