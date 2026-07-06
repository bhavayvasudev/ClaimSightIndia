"""Proves the actual impersonation defense in `POST /users/sync`: a Google
ID token is only trusted if it is signed by the key Google's JWKS serves
for it. The JWKS client is faked (no real network call), but the
signature/audience/issuer/expiry verification itself is the real
`app.core.google_oidc` code, unmocked.
"""

from __future__ import annotations

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import get_settings
from app.core import google_oidc

TEST_CLIENT_ID = "test-client-id.apps.googleusercontent.com"


def _rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def google_key():
    return _rsa_key()


@pytest.fixture
def attacker_key():
    return _rsa_key()


class _FakeSigningKey:
    def __init__(self, private_key):
        self.key = private_key.public_key()


@pytest.fixture(autouse=True)
def _patch_settings_and_jwks(monkeypatch, google_key):
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_google_client_id", TEST_CLIENT_ID)

    class _FakeJWKClient:
        def get_signing_key_from_jwt(self, token):
            # Stands in for fetching Google's real JWKS: always resolves
            # to *this* test's "Google" key, regardless of the token's
            # actual `kid` header.
            return _FakeSigningKey(google_key)

    monkeypatch.setattr(google_oidc, "_get_jwk_client", lambda: _FakeJWKClient())
    yield


def _make_id_token(
    signing_key,
    *,
    aud=TEST_CLIENT_ID,
    iss="https://accounts.google.com",
    sub="sub-1",
    email="alice@example.com",
    exp_delta=3600,
    iat_delta=0,
):
    now = int(time.time())
    payload = {
        "sub": sub,
        "email": email,
        "name": "Alice",
        "picture": "https://example.com/alice.jpg",
        "aud": aud,
        "iss": iss,
        "iat": now + iat_delta,
        "exp": now + exp_delta,
    }
    return jwt.encode(payload, signing_key, algorithm="RS256")


def test_verify_accepts_correctly_signed_token(google_key):
    token = _make_id_token(google_key)
    identity = google_oidc.verify_google_id_token(token)
    assert identity["sub"] == "sub-1"
    assert identity["email"] == "alice@example.com"
    assert identity["name"] == "Alice"


def test_verify_rejects_token_signed_by_a_different_key(attacker_key):
    # The actual impersonation check: an attacker can put whatever
    # sub/email they like in the payload, but without Google's private
    # key the signature never matches what our fake JWKS client (standing
    # in for the real one) resolves to.
    token = _make_id_token(attacker_key, sub="victim-sub", email="victim@example.com")
    with pytest.raises(google_oidc.InvalidGoogleIdToken):
        google_oidc.verify_google_id_token(token)


def test_verify_rejects_wrong_audience(google_key):
    token = _make_id_token(google_key, aud="someone-elses-client-id")
    with pytest.raises(google_oidc.InvalidGoogleIdToken):
        google_oidc.verify_google_id_token(token)


def test_verify_rejects_wrong_issuer(google_key):
    token = _make_id_token(google_key, iss="https://evil.example.com")
    with pytest.raises(google_oidc.InvalidGoogleIdToken):
        google_oidc.verify_google_id_token(token)


def test_verify_rejects_expired_token(google_key):
    token = _make_id_token(google_key, exp_delta=-3600)
    with pytest.raises(google_oidc.InvalidGoogleIdToken):
        google_oidc.verify_google_id_token(token)


def test_verify_tolerates_small_forward_clock_skew(google_key):
    """Regression for the 2026-07-05 sign-in outage: Google stamps `iat`
    with *its* clock. On a host whose clock ran slightly behind (Windows
    Time service stopped), every genuine token arrived with `iat` a couple
    of seconds in the future and zero-leeway verification rejected 100% of
    real browser sign-ins — while same-clock test tokens all passed."""
    token = _make_id_token(google_key, iat_delta=10)
    identity = google_oidc.verify_google_id_token(token)
    assert identity["sub"] == "sub-1"


def test_verify_still_rejects_iat_beyond_leeway(google_key):
    # The tolerance is a bounded skew allowance, not a disabled check.
    token = _make_id_token(google_key, iat_delta=300)
    with pytest.raises(google_oidc.InvalidGoogleIdToken):
        google_oidc.verify_google_id_token(token)
