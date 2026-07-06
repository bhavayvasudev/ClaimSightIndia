"""User sync endpoint.

Called server-side by the frontend's NextAuth `jwt` callback on every
Google sign-in (never from the browser directly) with the raw Google ID
token that sign-in just produced. This route independently verifies that
token (app.core.google_oidc) rather than trusting client-asserted profile
fields, upserts the basic profile, and issues a short-lived backend
access token the frontend then carries on every claim request.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.google_oidc import InvalidGoogleIdToken, verify_google_id_token
from app.core.rate_limit import limiter
from app.core.security import get_current_user, issue_access_token
from app.db.models.user import UserRecord
from app.db.session import get_db
from app.db.user_repository import UserRepository
from app.schemas.user_api import UserResponse, UserSyncRequest, UserSyncResponse
from app.services import user_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


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
