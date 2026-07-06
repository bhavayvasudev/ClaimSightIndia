"""Shared slowapi Limiter plus the 429 handler that keeps its response
shape consistent with every other structured error code in this API
(`{"error_code": ..., "message": ...}`).

Keyed by authenticated user id when a valid bearer token is present, so
one user can't dodge their own limit across IPs/devices; falls back to
the direct client IP for the one route that runs before any token exists
(`POST /users/sync`). Deliberately reads `request.client.host`, never
`X-Forwarded-For` — this deployment has no trusted reverse-proxy chain
configured, and trusting a client-supplied header for the rate-limit key
would let anyone bypass the limit by rotating a fake header value.
"""

from __future__ import annotations

import jwt
from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings


def _rate_limit_key(request: Request) -> str:
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        settings = get_settings()
        try:
            payload = jwt.decode(
                auth_header[7:],
                settings.backend_jwt_secret,
                algorithms=["HS256"],
                audience=settings.backend_jwt_audience,
                issuer=settings.backend_jwt_issuer,
            )
            return f"user:{payload['sub']}"
        except jwt.PyJWTError:
            # Falls through to IP-keyed limiting. get_current_user rejects
            # the request on its own merits either way — this only decides
            # which bucket absorbs a request carrying a bad token.
            pass
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=_rate_limit_key, storage_uri=get_settings().rate_limit_storage_uri)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "error_code": "rate_limited",
            "message": "Too many requests. Please try again shortly.",
        },
    )
