"""Route-level tests for the unified claim report, timeline, and PDF
export endpoints (`app/api/routes/reports.py`, Tasks 6/7/11)."""

from __future__ import annotations

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.routes import claims as claims_routes
from app.core.security import issue_access_token
from app.db.base import Base
from app.db.models.user import UserRecord
from app.db.session import get_db
from app.db.user_repository import UserRepository
from app.main import app
from app.services.ai_client import AIServiceClient

pytestmark = pytest.mark.asyncio

ANALYZE_CLAIM_ACCEPTED_BODY = {
    "success": True,
    "images_processed": 1,
    "claim_analysis": {
        "damaged_parts": [
            {
                "part": "Front bumper",
                "severity": "Moderate",
                "damage_percentage": 20.0,
                "damage_confidence": 0.5,
                "part_confidence": 0.8,
                "status": "Accepted",
                "recommended_action": "Repair",
                "detected_in_images": ["front.jpg"],
                "observation_count": 1,
                "max_damage_confidence_seen": 0.5,
                "max_part_confidence_seen": 0.8,
            }
        ],
        "summary": {"total_parts": 1, "accepted": 1, "review_required": 0},
    },
    "individual_results": [],
}

import base64

VALID_IMAGE_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


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


async def _create_claim(client: httpx.AsyncClient, headers: dict) -> dict:
    response = await client.post(
        "/claims",
        json={"vehicle_type": "Sedan", "vehicle_make": "Hyundai", "vehicle_model": "Verna", "vehicle_year": 2021},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _use_ai_handler(handler) -> None:
    app.dependency_overrides[claims_routes.get_ai_service_client] = (
        lambda: AIServiceClient(transport=httpx.MockTransport(handler))
    )


async def test_report_before_analysis_shows_no_damage_and_no_policy(client, session_factory):
    headers = _headers_for(await _make_user(session_factory))
    claim = await _create_claim(client, headers)

    response = await client.get(f"/claims/{claim['id']}/report", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["damage"]["damaged_parts"] == 0
    assert body["policy"]["state"] == "not_available"
    assert body["risk"]["risk_level"] == "insufficient_data"


async def test_report_after_analysis_reflects_damage_and_pricing(client, session_factory):
    headers = _headers_for(await _make_user(session_factory))
    claim = await _create_claim(client, headers)

    _use_ai_handler(lambda request: httpx.Response(200, json=ANALYZE_CLAIM_ACCEPTED_BODY))
    analyze_response = await client.post(
        f"/claims/{claim['id']}/analyze",
        files=[("images", ("front.jpg", VALID_IMAGE_BYTES, "image/png"))],
        headers=headers,
    )
    assert analyze_response.status_code == 200, analyze_response.text

    response = await client.get(f"/claims/{claim['id']}/report", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["damage"]["damaged_parts"] == 1
    assert body["damage"]["accepted"] == 1
    assert body["pricing"]["parts_priced"] == 1
    assert body["risk"]["risk_level"] == "low"
    assert "Damage assessment identified 1 affected part" in body["summary"]


async def test_report_requires_ownership(client, session_factory):
    headers_a = _headers_for(await _make_user(session_factory, google_sub="sub-a", email="a@example.com"))
    headers_b = _headers_for(await _make_user(session_factory, google_sub="sub-b", email="b@example.com"))
    claim = await _create_claim(client, headers_a)

    response = await client.get(f"/claims/{claim['id']}/report", headers=headers_b)
    assert response.status_code == 404


async def test_timeline_shows_claim_created_and_not_available_policy(client, session_factory):
    headers = _headers_for(await _make_user(session_factory))
    claim = await _create_claim(client, headers)

    response = await client.get(f"/claims/{claim['id']}/timeline", headers=headers)
    assert response.status_code == 200
    stages = {s["key"]: s for s in response.json()["stages"]}
    assert stages["claim_created"]["status"] == "complete"
    assert stages["policy_processed"]["status"] == "not_available"
    assert stages["damage_assessment_complete"]["status"] == "not_started"


async def test_timeline_after_analysis_marks_damage_and_pricing_complete(client, session_factory):
    headers = _headers_for(await _make_user(session_factory))
    claim = await _create_claim(client, headers)

    _use_ai_handler(lambda request: httpx.Response(200, json=ANALYZE_CLAIM_ACCEPTED_BODY))
    await client.post(
        f"/claims/{claim['id']}/analyze",
        files=[("images", ("front.jpg", VALID_IMAGE_BYTES, "image/png"))],
        headers=headers,
    )

    response = await client.get(f"/claims/{claim['id']}/timeline", headers=headers)
    stages = {s["key"]: s for s in response.json()["stages"]}
    assert stages["damage_assessment_complete"]["status"] == "complete"
    assert stages["pricing_complete"]["status"] == "complete"
    assert stages["risk_review_complete"]["status"] == "complete"
    assert stages["report_ready"]["status"] == "complete"


async def test_pdf_export_returns_pdf_bytes(client, session_factory):
    headers = _headers_for(await _make_user(session_factory))
    claim = await _create_claim(client, headers)

    response = await client.get(f"/claims/{claim['id']}/report/pdf", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


async def test_pdf_export_requires_ownership(client, session_factory):
    headers_a = _headers_for(await _make_user(session_factory, google_sub="sub-a", email="a@example.com"))
    headers_b = _headers_for(await _make_user(session_factory, google_sub="sub-b", email="b@example.com"))
    claim = await _create_claim(client, headers_a)

    response = await client.get(f"/claims/{claim['id']}/report/pdf", headers=headers_b)
    assert response.status_code == 404
