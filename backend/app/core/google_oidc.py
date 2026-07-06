"""Verifies a Google OIDC ID token's signature, issuer, audience and
expiry against Google's published JWKS — the one place this app
establishes trust in a claimed Google identity. Route/service code must
only ever trust `sub`/`email`/`name`/`picture` taken from the payload
this function returns, never from an unverified request body.
"""

from __future__ import annotations

from typing import Optional, TypedDict

import jwt
from jwt import PyJWKClient

from app.config import get_settings

_ALLOWED_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}

# Tolerance for the verifying machine's clock differing from Google's.
# Google's tokens are stamped by Google's (NTP-disciplined) clock; a local
# clock even 1 second behind it makes a freshly-issued token's `iat` sit
# "in the future" and PyJWT rejects it outright with zero leeway — which
# rejected every real browser sign-in on a host whose Windows Time service
# was stopped. 30s matches the industry-standard bounded skew allowance
# (google-auth's own verifier defaults to 10s); `exp` is still enforced,
# just with the same +/-30s bound — this never admits stale tokens.
_CLOCK_SKEW_LEEWAY_SECONDS = 30

# One shared client per process: PyJWKClient caches Google's public keys
# in-memory and only re-fetches the JWKS when it sees an unrecognized kid.
_jwk_client: Optional[PyJWKClient] = None


def _get_jwk_client() -> PyJWKClient:
    global _jwk_client
    if _jwk_client is None:
        _jwk_client = PyJWKClient(get_settings().google_jwks_url)
    return _jwk_client


class GoogleIdentity(TypedDict):
    sub: str
    email: str
    name: Optional[str]
    picture: Optional[str]


class InvalidGoogleIdToken(Exception):
    """The provided id_token failed signature/issuer/audience/expiry
    verification. Callers must map this to a generic 401 — the specific
    reason is for server logs only, never the client response."""


def verify_google_id_token(id_token: str) -> GoogleIdentity:
    settings = get_settings()
    try:
        signing_key = _get_jwk_client().get_signing_key_from_jwt(id_token)
        payload = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.auth_google_client_id,
            leeway=_CLOCK_SKEW_LEEWAY_SECONDS,
            options={"require": ["exp", "iat", "sub", "email"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidGoogleIdToken(str(exc)) from exc

    if payload.get("iss") not in _ALLOWED_ISSUERS:
        raise InvalidGoogleIdToken("unexpected issuer")

    return GoogleIdentity(
        sub=payload["sub"],
        email=payload["email"],
        name=payload.get("name"),
        picture=payload.get("picture"),
    )
