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
