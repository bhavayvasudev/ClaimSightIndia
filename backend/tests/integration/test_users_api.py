"""Route-level tests for the Google-profile sync endpoint
(`POST /users/sync`), called server-side by the frontend's NextAuth `jwt`
callback on every sign-in.

`verify_google_id_token` itself is faked here (its real signature/aud/iss
verification is unit-tested in isolation in
`tests/unit/test_google_oidc.py`) — these tests are about the route's own
behavior: upsert-by-sub semantics, and that a request the fake rejects as
unverified never reaches user creation at all.
"""

from __future__ import annotations

import json
import time

import httpx
import jwt
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.routes import users as users_routes
from app.config import get_settings
from app.core.google_oidc import GoogleIdentity, InvalidGoogleIdToken
from app.core.legal import CURRENT_LEGAL_VERSION
from app.db.base import Base
from app.db.session import get_db
from app.main import app

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


def _fake_id_token(**overrides) -> str:
    """A JSON blob standing in for a real Google ID token. `verified: true`
    marks it as something the fake verifier below will accept — a
    payload missing that marker simulates an attacker POSTing arbitrary
    identity claims without ever having actually completed Google sign-in."""
    payload = {
        "verified": True,
        "sub": "sub-1",
        "email": "alice@example.com",
        "name": "Alice",
        "picture": "https://example.com/alice.jpg",
    }
    payload.update(overrides)
    return json.dumps(payload)


def _fake_verify_google_id_token(id_token: str) -> GoogleIdentity:
    try:
        data = json.loads(id_token)
    except (ValueError, TypeError):
        raise InvalidGoogleIdToken("malformed token")
    if not data.get("verified") or not data.get("sub") or not data.get("email"):
        raise InvalidGoogleIdToken("not a verified Google identity")
    return GoogleIdentity(
        sub=data["sub"], email=data["email"], name=data.get("name"), picture=data.get("picture")
    )


@pytest.fixture(autouse=True)
def _use_fake_google_verification(monkeypatch):
    monkeypatch.setattr(users_routes, "verify_google_id_token", _fake_verify_google_id_token)


async def test_first_sign_in_creates_user(client):
    response = await client.post("/users/sync", json={"id_token": _fake_id_token()})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"]["email"] == "alice@example.com"
    assert body["user"]["name"] == "Alice"
    assert body["user"]["avatar_url"] == "https://example.com/alice.jpg"
    assert isinstance(body["user"]["id"], int)
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"]
    assert body["expires_in"] > 0


async def test_repeat_sign_in_does_not_duplicate_user(client):
    first = await client.post(
        "/users/sync", json={"id_token": _fake_id_token(sub="sub-2", email="bob@example.com", name="Bob")}
    )
    second = await client.post(
        "/users/sync", json={"id_token": _fake_id_token(sub="sub-2", email="bob@example.com", name="Bob")}
    )
    assert first.json()["user"]["id"] == second.json()["user"]["id"]


async def test_changed_name_and_avatar_update_stored_profile(client):
    first = await client.post(
        "/users/sync",
        json={
            "id_token": _fake_id_token(
                sub="sub-3",
                email="carol@example.com",
                name="Carol",
                picture="https://example.com/old.jpg",
            )
        },
    )
    user_id = first.json()["user"]["id"]

    updated = await client.post(
        "/users/sync",
        json={
            "id_token": _fake_id_token(
                sub="sub-3",
                email="carol@example.com",
                name="Carol Updated",
                picture="https://example.com/new.jpg",
            )
        },
    )
    assert updated.json()["user"]["id"] == user_id
    assert updated.json()["user"]["name"] == "Carol Updated"
    assert updated.json()["user"]["avatar_url"] == "https://example.com/new.jpg"


async def test_sync_then_create_claim_associates_correct_user(client):
    sync_response = await client.post(
        "/users/sync", json={"id_token": _fake_id_token(sub="sub-4", email="dave@example.com", name="Dave")}
    )
    body = sync_response.json()
    access_token = body["access_token"]

    claim_response = await client.post(
        "/claims",
        json={
            "vehicle_type": "Sedan",
            "vehicle_make": "Hyundai",
            "vehicle_model": "Verna",
            "vehicle_year": 2021,
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert claim_response.status_code == 201, claim_response.text
    assert claim_response.json()["user_id"] == body["user"]["id"]


async def test_unverified_identity_cannot_create_or_impersonate_user(client):
    # No "verified" marker — the fake verifier (standing in for a real,
    # unsigned/invalid Google ID token) rejects this before any user is
    # looked up or created, so an attacker can't POST an arbitrary
    # google_sub/email straight into the users table.
    response = await client.post(
        "/users/sync",
        json={"id_token": json.dumps({"sub": "victim-sub", "email": "victim@example.com"})},
    )
    assert response.status_code == 401
    assert "victim" not in response.text


async def test_refresh_reissues_token_that_authenticates(client):
    """The frontend's `jwt` callback renews via `POST /users/refresh`
    before the 12h expiry — the renewed token must be a first-class
    credential on claim routes, tied to the same user."""
    sync_response = await client.post(
        "/users/sync", json={"id_token": _fake_id_token(sub="sub-5", email="erin@example.com", name="Erin")}
    )
    sync_body = sync_response.json()

    refresh_response = await client.post(
        "/users/refresh", headers={"Authorization": f"Bearer {sync_body['access_token']}"}
    )
    assert refresh_response.status_code == 200, refresh_response.text
    refresh_body = refresh_response.json()
    assert refresh_body["user"]["id"] == sync_body["user"]["id"]
    assert refresh_body["expires_in"] > 0

    claim_response = await client.post(
        "/claims",
        json={
            "vehicle_type": "Sedan",
            "vehicle_make": "Hyundai",
            "vehicle_model": "Verna",
            "vehicle_year": 2021,
        },
        headers={"Authorization": f"Bearer {refresh_body['access_token']}"},
    )
    assert claim_response.status_code == 201, claim_response.text
    assert claim_response.json()["user_id"] == sync_body["user"]["id"]


async def test_refresh_without_token_is_rejected(client):
    response = await client.post("/users/refresh")
    assert response.status_code == 401


async def test_refresh_with_expired_token_is_rejected(client):
    """Renewal never resurrects a dead session — an expired token gets the
    same 401 as any other claim route, forcing a fresh Google sign-in."""
    sync_response = await client.post(
        "/users/sync", json={"id_token": _fake_id_token(sub="sub-6", email="frank@example.com", name="Frank")}
    )
    user_id = sync_response.json()["user"]["id"]

    settings = get_settings()
    now = int(time.time())
    expired_token = jwt.encode(
        {
            "sub": str(user_id),
            "iat": now - 7200,
            "exp": now - 3600,
            "iss": settings.backend_jwt_issuer,
            "aud": settings.backend_jwt_audience,
        },
        settings.backend_jwt_secret,
        algorithm="HS256",
    )
    response = await client.post("/users/refresh", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Legal consent (/users/consent)
# ---------------------------------------------------------------------------


async def test_consent_requires_authentication(client):
    response = await client.post(
        "/users/consent", json={"terms_version": CURRENT_LEGAL_VERSION, "privacy_version": CURRENT_LEGAL_VERSION}
    )
    assert response.status_code == 401


async def test_new_user_has_no_recorded_consent(client):
    """Existing users (and anyone who just signed in without ever hitting
    the consent endpoint) must show no consent recorded at all — the sync
    route itself never touches these columns."""
    _, headers = await _signed_in_user(client, "consent-1", "sam@example.com")
    profile = (await client.get("/users/me", headers=headers)).json()
    assert profile["terms_accepted_at"] is None
    assert profile["privacy_accepted_at"] is None
    assert profile["legal_version_accepted"] is None


async def test_accepting_consent_stores_timestamps_and_version(client):
    _, headers = await _signed_in_user(client, "consent-2", "tara@example.com")
    response = await client.post(
        "/users/consent",
        json={"terms_version": CURRENT_LEGAL_VERSION, "privacy_version": CURRENT_LEGAL_VERSION},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["terms_accepted_at"] is not None
    assert body["privacy_accepted_at"] is not None
    assert body["legal_version_accepted"] == CURRENT_LEGAL_VERSION

    reread = (await client.get("/users/me", headers=headers)).json()
    assert reread["terms_accepted_at"] == body["terms_accepted_at"]
    assert reread["privacy_accepted_at"] == body["privacy_accepted_at"]
    assert reread["legal_version_accepted"] == CURRENT_LEGAL_VERSION


async def test_accepting_consent_twice_is_idempotent_and_refreshes_timestamp(client):
    _, headers = await _signed_in_user(client, "consent-3", "uma@example.com")
    first = await client.post(
        "/users/consent",
        json={"terms_version": CURRENT_LEGAL_VERSION, "privacy_version": CURRENT_LEGAL_VERSION},
        headers=headers,
    )
    second = await client.post(
        "/users/consent",
        json={"terms_version": CURRENT_LEGAL_VERSION, "privacy_version": CURRENT_LEGAL_VERSION},
        headers=headers,
    )
    assert first.status_code == 200 and second.status_code == 200
    # Same user record, not a new row — no duplicate/second user id created.
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["legal_version_accepted"] == CURRENT_LEGAL_VERSION


async def test_consent_with_mismatched_version_still_stores_server_version(client):
    """A stale frontend build reporting an old version must never make it
    into the persisted record — the backend's own constant always wins."""
    _, headers = await _signed_in_user(client, "consent-4", "vik@example.com")
    response = await client.post(
        "/users/consent",
        json={"terms_version": "2020-01-01", "privacy_version": "2020-01-01"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["legal_version_accepted"] == CURRENT_LEGAL_VERSION


async def test_users_can_only_accept_consent_for_their_own_account(client):
    _, headers_a = await _signed_in_user(client, "consent-5a", "wren@example.com")
    _, headers_b = await _signed_in_user(client, "consent-5b", "xavi@example.com")

    await client.post(
        "/users/consent",
        json={"terms_version": CURRENT_LEGAL_VERSION, "privacy_version": CURRENT_LEGAL_VERSION},
        headers=headers_a,
    )
    b_profile = (await client.get("/users/me", headers=headers_b)).json()
    assert b_profile["terms_accepted_at"] is None


# ---------------------------------------------------------------------------
# Profile (/users/me) routes
# ---------------------------------------------------------------------------


def _png_bytes(color=(30, 60, 200), size=(8, 8)) -> bytes:
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", size, color=color).save(buffer, format="PNG")
    return buffer.getvalue()


async def _signed_in_user(client, sub: str, email: str, name: str = "User", picture: str | None = None):
    response = await client.post(
        "/users/sync",
        json={"id_token": _fake_id_token(sub=sub, email=email, name=name, picture=picture)},
    )
    body = response.json()
    return body["user"], {"Authorization": f"Bearer {body['access_token']}"}


async def test_me_requires_authentication(client):
    assert (await client.get("/users/me")).status_code == 401
    assert (await client.patch("/users/me", json={"display_name": "X"})).status_code == 401
    assert (await client.delete("/users/me/avatar")).status_code == 401


async def test_me_returns_identity_and_stats(client):
    _, headers = await _signed_in_user(client, "me-1", "grace@example.com", "Grace")
    response = await client.get("/users/me", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["email"] == "grace@example.com"
    assert body["auth_provider"] == "google"
    assert body["display_name"] is None
    assert body["contact_email"] is None
    assert body["claim_stats"] == {
        "total": 0,
        "active": 0,
        "under_review": 0,
        "completed": 0,
        "failed": 0,
    }
    assert body["created_at"] is not None


async def test_display_name_update_persists_and_trims(client):
    _, headers = await _signed_in_user(client, "me-2", "henry@example.com", "Henry")
    response = await client.patch(
        "/users/me", json={"display_name": "  Henry K.  "}, headers=headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["display_name"] == "Henry K."

    reread = await client.get("/users/me", headers=headers)
    assert reread.json()["display_name"] == "Henry K."
    # Provider-derived name is untouched.
    assert reread.json()["name"] == "Henry"


async def test_blank_and_markup_display_names_are_rejected(client):
    _, headers = await _signed_in_user(client, "me-3", "iris@example.com")
    assert (
        await client.patch("/users/me", json={"display_name": "   "}, headers=headers)
    ).status_code == 422
    assert (
        await client.patch("/users/me", json={"display_name": "<script>x</script>"}, headers=headers)
    ).status_code == 422
    assert (
        await client.patch("/users/me", json={"display_name": "x" * 65}, headers=headers)
    ).status_code == 422


async def test_contact_email_update_never_touches_identity_email(client):
    _, headers = await _signed_in_user(client, "me-4", "jack@example.com")
    response = await client.patch(
        "/users/me", json={"contact_email": "jack.claims@other.com"}, headers=headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["contact_email"] == "jack.claims@other.com"
    assert body["email"] == "jack@example.com"  # verified Google identity — unchanged


async def test_invalid_contact_email_is_rejected(client):
    _, headers = await _signed_in_user(client, "me-5", "kate@example.com")
    for bad in ["not-an-email", "a@b", "a b@c.com", "<x>@y.com"]:
        response = await client.patch("/users/me", json={"contact_email": bad}, headers=headers)
        assert response.status_code == 422, bad


async def test_identity_fields_are_not_patchable(client):
    """`extra="forbid"`: email/google_sub can never ride in through the
    profile update body."""
    _, headers = await _signed_in_user(client, "me-6", "liam@example.com")
    for payload in [{"email": "evil@example.com"}, {"google_sub": "stolen-sub"}, {"id": 999}]:
        response = await client.patch("/users/me", json=payload, headers=headers)
        assert response.status_code == 422, payload


async def test_explicit_null_clears_customization(client):
    _, headers = await _signed_in_user(client, "me-7", "mia@example.com", "Mia")
    await client.patch("/users/me", json={"display_name": "Custom Mia"}, headers=headers)
    response = await client.patch("/users/me", json={"display_name": None}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["display_name"] is None


async def test_users_can_only_update_their_own_profile(client):
    """No user-id parameter exists anywhere on /me — identity comes only
    from the bearer token, so A's update can never land on B."""
    _, headers_a = await _signed_in_user(client, "me-8a", "ana@example.com", "Ana")
    _, headers_b = await _signed_in_user(client, "me-8b", "ben@example.com", "Ben")

    await client.patch("/users/me", json={"display_name": "Ana Custom"}, headers=headers_a)

    b_profile = (await client.get("/users/me", headers=headers_b)).json()
    assert b_profile["display_name"] is None
    assert b_profile["email"] == "ben@example.com"


async def test_resync_preserves_customizations_but_refreshes_provider_fields(client):
    """The Google-sync regression guard: a later sign-in refreshes
    provider-derived identity metadata but never overwrites the user's
    ClaimSight customizations."""
    _, headers = await _signed_in_user(
        client, "me-9", "nora@example.com", "Nora", picture="https://example.com/nora-old.jpg"
    )
    await client.patch(
        "/users/me",
        json={"display_name": "Nora Custom", "contact_email": "nora.claims@other.com"},
        headers=headers,
    )
    upload = await client.post(
        "/users/me/avatar",
        files={"file": ("me.png", _png_bytes(), "image/png")},
        headers=headers,
    )
    custom_avatar_url = upload.json()["custom_avatar_url"]
    assert custom_avatar_url

    # Same google_sub signs in again with refreshed Google profile data.
    await client.post(
        "/users/sync",
        json={
            "id_token": _fake_id_token(
                sub="me-9",
                email="nora@example.com",
                name="Nora Googled",
                picture="https://example.com/nora-new.jpg",
            )
        },
    )

    profile = (await client.get("/users/me", headers=headers)).json()
    assert profile["name"] == "Nora Googled"  # provider tier refreshed
    assert profile["avatar_url"] == "https://example.com/nora-new.jpg"
    assert profile["display_name"] == "Nora Custom"  # custom tier preserved
    assert profile["contact_email"] == "nora.claims@other.com"
    assert profile["custom_avatar_url"] == custom_avatar_url


async def test_avatar_upload_stores_and_serves_image(client):
    user, headers = await _signed_in_user(client, "me-10", "omar@example.com")
    response = await client.post(
        "/users/me/avatar",
        files={"file": ("../../evil name.png", _png_bytes(), "image/png")},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    url = response.json()["custom_avatar_url"]
    # Server-generated content-addressed name — never the original filename.
    assert url.startswith(f"/avatars/u{user['id']}-")
    assert "evil" not in url

    served = await client.get(url)
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/png"
    assert served.content == _png_bytes()


async def test_avatar_rejects_non_image_and_oversized_uploads(client):
    _, headers = await _signed_in_user(client, "me-11", "pia@example.com")

    not_image = await client.post(
        "/users/me/avatar",
        files={"file": ("nope.txt", b"just text", "text/plain")},
        headers=headers,
    )
    assert not_image.status_code == 422

    masquerading = await client.post(
        "/users/me/avatar",
        files={"file": ("fake.png", b"<html>not an image</html>", "image/png")},
        headers=headers,
    )
    assert masquerading.status_code == 422

    oversized = await client.post(
        "/users/me/avatar",
        files={"file": ("big.png", b"x" * (5 * 1024 * 1024 + 1), "image/png")},
        headers=headers,
    )
    assert oversized.status_code == 422


async def test_avatar_reset_restores_google_photo(client):
    _, headers = await _signed_in_user(
        client, "me-12", "quinn@example.com", picture="https://example.com/quinn.jpg"
    )
    await client.post(
        "/users/me/avatar",
        files={"file": ("me.png", _png_bytes(), "image/png")},
        headers=headers,
    )
    response = await client.delete("/users/me/avatar", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["custom_avatar_url"] is None
    assert body["avatar_url"] == "https://example.com/quinn.jpg"


async def test_profile_claim_stats_reflect_owned_claims(client):
    _, headers = await _signed_in_user(client, "me-13", "ravi@example.com")
    for _ in range(2):
        created = await client.post(
            "/claims",
            json={
                "vehicle_type": "Sedan",
                "vehicle_make": "Hyundai",
                "vehicle_model": "Verna",
                "vehicle_year": 2021,
            },
            headers=headers,
        )
        assert created.status_code == 201

    stats = (await client.get("/users/me", headers=headers)).json()["claim_stats"]
    assert stats["total"] == 2
    assert stats["active"] == 2  # intake claims group under Active
    assert stats["failed"] == 0


async def test_users_sync_rate_limit_returns_429(client):
    for i in range(10):
        response = await client.post(
            "/users/sync", json={"id_token": _fake_id_token(sub=f"sub-rl-{i}", email=f"user{i}@example.com")}
        )
        assert response.status_code == 200, response.text

    response = await client.post(
        "/users/sync", json={"id_token": _fake_id_token(sub="sub-rl-11", email="user11@example.com")}
    )
    assert response.status_code == 429
    assert response.json()["error_code"] == "rate_limited"
