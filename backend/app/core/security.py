"""Backend-issued access tokens and the FastAPI auth dependency.

The frontend never mints these tokens — only `POST /users/sync` does,
and only after independently verifying a Google ID token (see
`app.core.google_oidc`). Every other authenticated route depends on
`get_current_user`, which is the one place a bearer token is decoded,
verified and resolved to a user — no route re-implements this.
"""

from __future__ import annotations

import time
from typing import Optional, Tuple

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models.user import UserRecord
from app.db.session import get_db
from app.db.user_repository import UserRepository

_ALGORITHM = "HS256"

_bearer_scheme = HTTPBearer(auto_error=False)


def issue_access_token(user: UserRecord) -> Tuple[str, int]:
    settings = get_settings()
    now = int(time.time())
    ttl = settings.backend_jwt_ttl_seconds
    payload = {
        "sub": str(user.id),
        "google_sub": user.google_sub,
        "iat": now,
        "exp": now + ttl,
        "iss": settings.backend_jwt_issuer,
        "aud": settings.backend_jwt_audience,
    }
    token = jwt.encode(payload, settings.backend_jwt_secret, algorithm=_ALGORITHM)
    return token, ttl


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> UserRecord:
    """Requires a valid backend-issued bearer token and resolves it to the
    owning `UserRecord`. Missing header, bad signature, expired token, and
    a deleted/unknown user id all collapse to the same generic 401 — never
    logged with the raw token, never distinguished in the response, so
    nothing about *why* verification failed reaches the client."""

    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required.")

    settings = get_settings()
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.backend_jwt_secret,
            algorithms=[_ALGORITHM],
            audience=settings.backend_jwt_audience,
            issuer=settings.backend_jwt_issuer,
        )
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Authentication session is invalid or expired.")

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Authentication session is invalid or expired.")

    user = await UserRepository(db).get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication session is invalid or expired.")

    return user
