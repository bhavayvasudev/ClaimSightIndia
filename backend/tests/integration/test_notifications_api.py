"""Route-level tests for notification endpoints
(`app/api/routes/notifications.py`, Task 12): correct user receives the
event, another user cannot access it, unread count, and mark-read."""

from __future__ import annotations

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.security import issue_access_token
from app.db.base import Base
from app.db.models.user import UserRecord
from app.db.notification_repository import NotificationRepository
from app.db.session import get_db
from app.db.user_repository import UserRepository
from app.main import app

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def client(session_factory):
    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def _make_user(session_factory, **overrides) -> UserRecord:
    defaults = {"google_sub": "sub-1", "email": "a@example.com", "name": "A", "avatar_url": None}
    defaults.update(overrides)
    async with session_factory() as session:
        return await UserRepository(session).create(**defaults)


def _headers_for(user: UserRecord) -> dict:
    token, _ = issue_access_token(user)
    return {"Authorization": f"Bearer {token}"}


async def test_list_notifications_requires_authentication(client):
    response = await client.get("/notifications")
    assert response.status_code == 401


async def test_correct_user_receives_their_own_notification(client, session_factory):
    user = await _make_user(session_factory)
    async with session_factory() as session:
        await NotificationRepository(session).create(
            user_id=user.id, claim_id=None, type="report_ready", title="Claim report ready", body="Body"
        )

    response = await client.get("/notifications", headers=_headers_for(user))
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "Claim report ready"
    assert body["unread_count"] == 1


async def test_other_user_cannot_see_someone_elses_notifications(client, session_factory):
    user_a = await _make_user(session_factory, google_sub="sub-a", email="a@example.com")
    user_b = await _make_user(session_factory, google_sub="sub-b", email="b@example.com")
    async with session_factory() as session:
        await NotificationRepository(session).create(
            user_id=user_a.id, claim_id=None, type="report_ready", title="A's notification", body="Body"
        )

    response = await client.get("/notifications", headers=_headers_for(user_b))
    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_other_user_cannot_mark_read_someone_elses_notification(client, session_factory):
    user_a = await _make_user(session_factory, google_sub="sub-a", email="a@example.com")
    user_b = await _make_user(session_factory, google_sub="sub-b", email="b@example.com")
    async with session_factory() as session:
        notif = await NotificationRepository(session).create(
            user_id=user_a.id, claim_id=None, type="report_ready", title="T", body="B"
        )

    response = await client.post(f"/notifications/{notif.id}/read", headers=_headers_for(user_b))
    assert response.status_code == 404


async def test_mark_read_updates_unread_count(client, session_factory):
    user = await _make_user(session_factory)
    async with session_factory() as session:
        notif = await NotificationRepository(session).create(
            user_id=user.id, claim_id=None, type="report_ready", title="T", body="B"
        )

    headers = _headers_for(user)
    unread_before = await client.get("/notifications/unread-count", headers=headers)
    assert unread_before.json()["unread_count"] == 1

    mark_response = await client.post(f"/notifications/{notif.id}/read", headers=headers)
    assert mark_response.status_code == 200
    assert mark_response.json()["read"] is True

    unread_after = await client.get("/notifications/unread-count", headers=headers)
    assert unread_after.json()["unread_count"] == 0


async def test_mark_all_read(client, session_factory):
    user = await _make_user(session_factory)
    async with session_factory() as session:
        repo = NotificationRepository(session)
        await repo.create(user_id=user.id, claim_id=None, type="report_ready", title="T1", body="B1")
        await repo.create(user_id=user.id, claim_id=None, type="report_ready", title="T2", body="B2")

    headers = _headers_for(user)
    response = await client.post("/notifications/read-all", headers=headers)
    assert response.status_code == 200

    unread = await client.get("/notifications/unread-count", headers=headers)
    assert unread.json()["unread_count"] == 0
