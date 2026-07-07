"""Route-level tests for the claim create -> analyze -> retrieve flow.

The ai-service is always mocked via `httpx.MockTransport` (wired in through
the `get_ai_service_client` FastAPI dependency) and the database is an
in-memory SQLite engine created fresh per test. These tests must never
load the YOLO models or require a running ai-service/Postgres process.

Every route now requires an authenticated caller — `_make_authed_user`
creates a `UserRecord` directly (bypassing `/users/sync`, whose own
Google-verification behavior is covered separately in
`test_users_api.py` / `tests/unit/test_google_oidc.py`) and mints a real
backend access token for it via `app.core.security.issue_access_token`,
so these tests exercise the exact same verification path a real request
would hit.
"""

from __future__ import annotations

import base64
import time

import httpx
import jwt
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.routes import claims as claims_routes
from app.config import get_settings
from app.core.security import issue_access_token
from app.db.base import Base
from app.db.models.user import UserRecord
from app.db.session import get_db
from app.db.user_repository import UserRepository
from app.main import app
from app.services.ai_client import AIServiceClient

pytestmark = pytest.mark.asyncio

# A genuinely valid (1x1 transparent) PNG — real upload-security
# validation now decodes every image with Pillow, so placeholder bytes
# like the old `b"fake-bytes"` would be rejected as corrupted before ever
# reaching the mocked ai-service.
VALID_IMAGE_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)

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

ANALYZE_CLAIM_REVIEW_REQUIRED_BODY = {
    "success": True,
    "images_processed": 1,
    "claim_analysis": {
        "damaged_parts": [
            {
                "part": "Headlight - (R)",
                "severity": "Uncertain",
                "damage_percentage": 79.55,
                "damage_confidence": 0.08,
                "part_confidence": 0.61,
                "status": "Review Required",
                "recommended_action": "Manual Inspection",
                "detected_in_images": ["front.jpg"],
                "observation_count": 1,
                "max_damage_confidence_seen": 0.08,
                "max_part_confidence_seen": 0.61,
            }
        ],
        "summary": {"total_parts": 0, "accepted": 0, "review_required": 1},
    },
    "individual_results": [],
}


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
async def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def client(session_factory):
    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


async def _make_user(session_factory, **overrides) -> UserRecord:
    defaults = {
        "google_sub": "sub-1",
        "email": "alice@example.com",
        "name": "Alice",
        "avatar_url": None,
    }
    defaults.update(overrides)
    async with session_factory() as session:  # type: AsyncSession
        repo = UserRepository(session)
        return await repo.create(**defaults)


def _headers_for(user: UserRecord) -> dict:
    token, _ = issue_access_token(user)
    return {"Authorization": f"Bearer {token}"}


async def _authed_headers(session_factory, **user_overrides) -> dict:
    user = await _make_user(session_factory, **user_overrides)
    return _headers_for(user)


def _use_ai_handler(handler) -> None:
    app.dependency_overrides[claims_routes.get_ai_service_client] = (
        lambda: AIServiceClient(transport=httpx.MockTransport(handler))
    )


async def _create_claim(client: httpx.AsyncClient, headers: dict, **overrides) -> dict:
    payload = {
        "vehicle_type": "Sedan",
        "vehicle_make": "Hyundai",
        "vehicle_model": "Verna",
        "vehicle_year": 2021,
    }
    payload.update(overrides)
    response = await client.post("/claims", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


async def test_create_claim_rejects_unauthenticated_request(client):
    response = await client.post(
        "/claims",
        json={
            "vehicle_type": "Sedan",
            "vehicle_make": "Hyundai",
            "vehicle_model": "Verna",
            "vehicle_year": 2021,
        },
    )
    assert response.status_code == 401


async def test_get_claim_rejects_unauthenticated_request(client, session_factory):
    headers = await _authed_headers(session_factory)
    claim = await _create_claim(client, headers)

    response = await client.get(f"/claims/{claim['id']}")
    assert response.status_code == 401


async def test_analyze_claim_rejects_unauthenticated_request(client, session_factory):
    headers = await _authed_headers(session_factory)
    claim = await _create_claim(client, headers)

    response = await client.post(
        f"/claims/{claim['id']}/analyze",
        files=[("images", ("front.jpg", VALID_IMAGE_BYTES, "image/png"))],
    )
    assert response.status_code == 401


async def test_malformed_bearer_token_rejected(client):
    response = await client.get(
        "/claims/CLM-DOES-NOT-EXIST", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


async def test_expired_bearer_token_rejected(client, session_factory):
    user = await _make_user(session_factory)
    settings = get_settings()
    now = int(time.time())
    expired_token = jwt.encode(
        {
            "sub": str(user.id),
            "iat": now - 7200,
            "exp": now - 3600,
            "iss": settings.backend_jwt_issuer,
            "aud": settings.backend_jwt_audience,
        },
        settings.backend_jwt_secret,
        algorithm="HS256",
    )
    response = await client.get(
        "/claims/CLM-DOES-NOT-EXIST", headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert response.status_code == 401


async def test_create_claim_rejects_client_supplied_user_id_field(client, session_factory):
    # user_id was removed from ClaimCreateRequest entirely; with
    # extra="forbid" this now fails schema validation rather than being
    # silently trusted the way it used to be.
    headers = await _authed_headers(session_factory)
    response = await client.post(
        "/claims",
        json={
            "vehicle_type": "Sedan",
            "vehicle_make": "Hyundai",
            "vehicle_model": "Verna",
            "vehicle_year": 2021,
            "user_id": 999,
        },
        headers=headers,
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Ownership / IDOR
# ---------------------------------------------------------------------------


async def test_user_b_cannot_get_user_a_claim(client, session_factory):
    headers_a = await _authed_headers(session_factory, google_sub="sub-a", email="a@example.com")
    headers_b = await _authed_headers(session_factory, google_sub="sub-b", email="b@example.com")

    claim = await _create_claim(client, headers_a)

    response = await client.get(f"/claims/{claim['id']}", headers=headers_b)
    assert response.status_code == 404

    # The owner can still retrieve it — proves this is an ownership check,
    # not a general breakage.
    own_response = await client.get(f"/claims/{claim['id']}", headers=headers_a)
    assert own_response.status_code == 200


async def test_user_b_cannot_analyze_user_a_claim(client, session_factory):
    headers_a = await _authed_headers(session_factory, google_sub="sub-a", email="a@example.com")
    headers_b = await _authed_headers(session_factory, google_sub="sub-b", email="b@example.com")

    claim = await _create_claim(client, headers_a)

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("ai-service should never be called for another user's claim")

    _use_ai_handler(handler)

    response = await client.post(
        f"/claims/{claim['id']}/analyze",
        files=[("images", ("front.jpg", VALID_IMAGE_BYTES, "image/png"))],
        headers=headers_b,
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /claims
# ---------------------------------------------------------------------------


async def test_create_claim_returns_intake_status(client, session_factory):
    headers = await _authed_headers(session_factory)
    body = await _create_claim(client, headers)

    assert body["id"].startswith("CLM-")
    assert body["status"] == "intake"
    assert body["vehicle_type"] == "Sedan"
    assert body["ai_assessment"] is None
    assert body["pricing_assessment"] is None


async def test_create_claim_with_variant_round_trips(client, session_factory):
    headers = await _authed_headers(session_factory)
    body = await _create_claim(
        client,
        headers,
        vehicle_type="SUV",
        vehicle_make="MG Motor",
        vehicle_model="Astor",
        vehicle_variant="Blackstorm",
    )
    assert body["vehicle_variant"] == "Blackstorm"

    get_response = await client.get(f"/claims/{body['id']}", headers=headers)
    assert get_response.json()["vehicle_variant"] == "Blackstorm"


async def test_create_claim_without_variant_is_backward_compatible(client, session_factory):
    """Task 13 — a claim created the old way (no vehicle_variant field at
    all, as every pre-existing claim was) must still work end to end."""
    headers = await _authed_headers(session_factory)
    body = await _create_claim(client, headers)
    assert body["vehicle_variant"] is None

    get_response = await client.get(f"/claims/{body['id']}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["vehicle_variant"] is None


async def test_create_claim_rejects_unknown_vehicle_type(client, session_factory):
    headers = await _authed_headers(session_factory)
    response = await client.post(
        "/claims",
        json={
            "vehicle_type": "Spaceship",
            "vehicle_make": "Hyundai",
            "vehicle_model": "Verna",
            "vehicle_year": 2021,
        },
        headers=headers,
    )
    assert response.status_code == 422


async def test_create_claim_rejects_missing_make_model_year(client, session_factory):
    headers = await _authed_headers(session_factory)
    response = await client.post("/claims", json={"vehicle_type": "Sedan"}, headers=headers)
    assert response.status_code == 422


async def test_create_claim_rejects_blank_make(client, session_factory):
    headers = await _authed_headers(session_factory)
    response = await client.post(
        "/claims",
        json={
            "vehicle_type": "Sedan",
            "vehicle_make": "   ",
            "vehicle_model": "Verna",
            "vehicle_year": 2021,
        },
        headers=headers,
    )
    assert response.status_code == 422


async def test_create_claim_rejects_make_over_max_length(client, session_factory):
    headers = await _authed_headers(session_factory)
    response = await client.post(
        "/claims",
        json={
            "vehicle_type": "Sedan",
            "vehicle_make": "H" * 65,
            "vehicle_model": "Verna",
            "vehicle_year": 2021,
        },
        headers=headers,
    )
    assert response.status_code == 422


async def test_create_claim_trims_make_and_model(client, session_factory):
    headers = await _authed_headers(session_factory)
    body = await _create_claim(client, headers, vehicle_make="  Hyundai  ", vehicle_model="  Verna  ")
    assert body["vehicle_make"] == "Hyundai"
    assert body["vehicle_model"] == "Verna"


async def test_create_claim_allows_hyphens_and_parentheses_in_make(client, session_factory):
    # Legitimate vehicle names can contain hyphens/parentheses/periods —
    # validation must not destructively strip these.
    headers = await _authed_headers(session_factory)
    body = await _create_claim(client, headers, vehicle_make="Mercedes-Benz", vehicle_model="A-Class (W177)")
    assert body["vehicle_make"] == "Mercedes-Benz"
    assert body["vehicle_model"] == "A-Class (W177)"


async def test_create_claim_rejects_year_below_range(client, session_factory):
    headers = await _authed_headers(session_factory)
    response = await client.post(
        "/claims",
        json={
            "vehicle_type": "Sedan",
            "vehicle_make": "Hyundai",
            "vehicle_model": "Verna",
            "vehicle_year": 1899,
        },
        headers=headers,
    )
    assert response.status_code == 422


async def test_create_claim_rejects_year_too_far_in_future(client, session_factory):
    headers = await _authed_headers(session_factory)
    response = await client.post(
        "/claims",
        json={
            "vehicle_type": "Sedan",
            "vehicle_make": "Hyundai",
            "vehicle_model": "Verna",
            "vehicle_year": 2999,
        },
        headers=headers,
    )
    assert response.status_code == 422


async def test_create_claim_associates_authenticated_user(client, session_factory):
    user = await _make_user(session_factory)
    body = await _create_claim(client, _headers_for(user))
    assert body["user_id"] == user.id

    reloaded = await client.get(f"/claims/{body['id']}", headers=_headers_for(user))
    assert reloaded.json()["user_id"] == user.id


# ---------------------------------------------------------------------------
# POST /claims/{claim_id}/analyze
# ---------------------------------------------------------------------------


async def test_analyze_claim_not_found_returns_404(client, session_factory):
    headers = await _authed_headers(session_factory)

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("ai-service should never be called for a missing claim")

    _use_ai_handler(handler)

    response = await client.post(
        "/claims/CLM-DOES-NOT-EXIST/analyze",
        files=[("images", ("front.jpg", VALID_IMAGE_BYTES, "image/png"))],
        headers=headers,
    )
    assert response.status_code == 404


async def test_analyze_claim_all_accepted_yields_analysis_complete_and_pricing(client, session_factory):
    headers = await _authed_headers(session_factory)
    claim = await _create_claim(client, headers)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=ANALYZE_CLAIM_ACCEPTED_BODY)

    _use_ai_handler(handler)

    response = await client.post(
        f"/claims/{claim['id']}/analyze",
        files=[("images", ("front.jpg", VALID_IMAGE_BYTES, "image/png"))],
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["status"] == "analysis_complete"
    assert body["ai_assessment"]["damaged_parts"][0]["part"] == "Front bumper"
    assert body["pricing_assessment"]["parts_priced"] == 1
    assert body["pricing_assessment"]["per_part"]["Front bumper"]["min_inr"] == 2500
    assert body["pricing_assessment"]["per_part"]["Front bumper"]["max_inr"] == 7000


async def test_analyze_claim_review_required_part_preserved_with_null_pricing(client, session_factory):
    headers = await _authed_headers(session_factory)
    claim = await _create_claim(client, headers, vehicle_type="SUV")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=ANALYZE_CLAIM_REVIEW_REQUIRED_BODY)

    _use_ai_handler(handler)

    response = await client.post(
        f"/claims/{claim['id']}/analyze",
        files=[("images", ("front.jpg", VALID_IMAGE_BYTES, "image/png"))],
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["status"] == "review_required"
    assert body["pricing_assessment"]["parts_priced"] == 0
    assert body["pricing_assessment"]["parts_pending_manual_inspection"] == 1
    assert body["pricing_assessment"]["per_part"]["Headlight - (R)"] is None


async def test_analyze_claim_rejects_unsupported_content_type(client, session_factory):
    headers = await _authed_headers(session_factory)
    claim = await _create_claim(client, headers)

    response = await client.post(
        f"/claims/{claim['id']}/analyze",
        files=[("images", ("policy.pdf", b"%PDF-1.4", "application/pdf"))],
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error_code"] == "unsupported_file_type"


async def test_analyze_claim_rejects_corrupted_image(client, session_factory):
    headers = await _authed_headers(session_factory)
    claim = await _create_claim(client, headers)

    response = await client.post(
        f"/claims/{claim['id']}/analyze",
        files=[("images", ("broken.jpg", b"this-is-not-a-real-image", "image/jpeg"))],
        headers=headers,
    )
    assert response.status_code == 422
    body = response.json()["detail"]
    assert body["error_code"] == "corrupted_image"
    assert body["invalid_filenames"] == ["broken.jpg"]


async def test_analyze_claim_rejects_oversized_image(client, session_factory):
    headers = await _authed_headers(session_factory)
    claim = await _create_claim(client, headers)

    oversized = b"0" * (claims_routes.MAX_IMAGE_BYTES + 1)
    response = await client.post(
        f"/claims/{claim['id']}/analyze",
        files=[("images", ("huge.jpg", oversized, "image/jpeg"))],
        headers=headers,
    )
    assert response.status_code == 422
    body = response.json()["detail"]
    assert body["error_code"] == "file_too_large"
    assert body["invalid_filenames"] == ["huge.jpg"]


async def test_analyze_claim_rejects_too_many_files(client, session_factory):
    headers = await _authed_headers(session_factory)
    claim = await _create_claim(client, headers)

    files = [("images", (f"img{i}.png", VALID_IMAGE_BYTES, "image/png")) for i in range(11)]
    response = await client.post(f"/claims/{claim['id']}/analyze", files=files, headers=headers)
    assert response.status_code == 422
    assert response.json()["detail"]["error_code"] == "too_many_files"


async def test_analyze_claim_ai_service_unavailable_returns_503(client, session_factory):
    headers = await _authed_headers(session_factory)
    claim = await _create_claim(client, headers)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    _use_ai_handler(handler)

    response = await client.post(
        f"/claims/{claim['id']}/analyze",
        files=[("images", ("front.jpg", VALID_IMAGE_BYTES, "image/png"))],
        headers=headers,
    )
    assert response.status_code == 503

    # The claim must be left in a clean failed state, not stuck "analyzing".
    reloaded = await client.get(f"/claims/{claim['id']}", headers=headers)
    assert reloaded.json()["status"] == "failed"


async def test_analyze_claim_ai_service_timeout_returns_504(client, session_factory):
    headers = await _authed_headers(session_factory)
    claim = await _create_claim(client, headers)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    _use_ai_handler(handler)

    response = await client.post(
        f"/claims/{claim['id']}/analyze",
        files=[("images", ("front.jpg", VALID_IMAGE_BYTES, "image/png"))],
        headers=headers,
    )
    assert response.status_code == 504


async def test_analyze_claim_malformed_ai_response_returns_502_without_leaking_detail(client, session_factory):
    headers = await _authed_headers(session_factory)
    claim = await _create_claim(client, headers)

    def handler(request: httpx.Request) -> httpx.Response:
        # Valid JSON, but missing the required claim_analysis key entirely.
        return httpx.Response(200, json={"success": True})

    _use_ai_handler(handler)

    response = await client.post(
        f"/claims/{claim['id']}/analyze",
        files=[("images", ("front.jpg", VALID_IMAGE_BYTES, "image/png"))],
        headers=headers,
    )
    assert response.status_code == 502
    assert "Traceback" not in response.text
    assert "claim_analysis" not in response.text


async def test_analyze_claim_vehicle_not_detected_returns_structured_422(client, session_factory):
    headers = await _authed_headers(session_factory)
    claim = await _create_claim(client, headers)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={
                "detail": {
                    "error_code": "vehicle_not_detected",
                    "message": "One or more images do not appear to contain a vehicle.",
                    "invalid_filenames": ["person.jpg"],
                }
            },
        )

    _use_ai_handler(handler)

    response = await client.post(
        f"/claims/{claim['id']}/analyze",
        files=[("images", ("person.jpg", VALID_IMAGE_BYTES, "image/png"))],
        headers=headers,
    )
    assert response.status_code == 422
    body = response.json()["detail"]
    assert body["error_code"] == "vehicle_not_detected"
    assert body["invalid_filenames"] == ["person.jpg"]

    # The claim must be left in a clean failed state, not stuck "analyzing".
    reloaded = await client.get(f"/claims/{claim['id']}", headers=headers)
    assert reloaded.json()["status"] == "failed"


async def test_analyze_claim_retry_after_vehicle_rejection_reuses_same_claim_id(client, session_factory):
    headers = await _authed_headers(session_factory)
    claim = await _create_claim(client, headers)

    def reject_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={
                "detail": {
                    "error_code": "vehicle_not_detected",
                    "message": "One or more images do not appear to contain a vehicle.",
                    "invalid_filenames": ["person.jpg"],
                }
            },
        )

    _use_ai_handler(reject_handler)
    first = await client.post(
        f"/claims/{claim['id']}/analyze",
        files=[("images", ("person.jpg", VALID_IMAGE_BYTES, "image/png"))],
        headers=headers,
    )
    assert first.status_code == 422

    # Retry against the SAME claim id with a corrected image set — never a
    # second POST /claims call, matching the frontend's claim-id-reuse flow.
    _use_ai_handler(lambda request: httpx.Response(200, json=ANALYZE_CLAIM_ACCEPTED_BODY))
    second = await client.post(
        f"/claims/{claim['id']}/analyze",
        files=[("images", ("front.jpg", VALID_IMAGE_BYTES, "image/png"))],
        headers=headers,
    )
    assert second.status_code == 200, second.text
    assert second.json()["id"] == claim["id"]
    assert second.json()["status"] == "analysis_complete"


async def test_analyze_claim_schema_invalid_part_returns_502(client, session_factory):
    headers = await _authed_headers(session_factory)
    claim = await _create_claim(client, headers)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": True,
                "images_processed": 1,
                "claim_analysis": {
                    "damaged_parts": [{"part": "Front bumper"}],  # missing required fields
                    "summary": {},
                },
                "individual_results": [],
            },
        )

    _use_ai_handler(handler)

    response = await client.post(
        f"/claims/{claim['id']}/analyze",
        files=[("images", ("front.jpg", VALID_IMAGE_BYTES, "image/png"))],
        headers=headers,
    )
    assert response.status_code == 502

    reloaded = await client.get(f"/claims/{claim['id']}", headers=headers)
    assert reloaded.json()["status"] == "failed"


# ---------------------------------------------------------------------------
# Analyze idempotency — the production retry-after-lost-response pattern.
# A cold AI service can push one analyze call past a proxy/browser timeout:
# the backend still finishes and commits, but the client never sees the
# response and retries the same claim with the same images. That retry
# must return the persisted result without a second inference run and
# without duplicating any per-claim data.
# ---------------------------------------------------------------------------


def _png_bytes(color: str) -> bytes:
    """A real, decodable PNG whose bytes differ per color — for tests that
    need a *different* image set (different sha256) on the same claim."""
    import io as _io

    from PIL import Image as _Image

    buf = _io.BytesIO()
    _Image.new("RGB", (1, 1), color).save(buf, format="PNG")
    return buf.getvalue()


async def test_reanalyze_identical_images_returns_result_without_second_inference(
    client, session_factory
):
    headers = await _authed_headers(session_factory)
    claim = await _create_claim(client, headers)

    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, json=ANALYZE_CLAIM_ACCEPTED_BODY)

    _use_ai_handler(handler)

    files = [("images", ("front.jpg", VALID_IMAGE_BYTES, "image/png"))]
    first = await client.post(f"/claims/{claim['id']}/analyze", files=files, headers=headers)
    assert first.status_code == 200, first.text

    # The retry a user fires after a lost/timed-out response: same claim,
    # byte-identical images.
    second = await client.post(f"/claims/{claim['id']}/analyze", files=files, headers=headers)
    assert second.status_code == 200, second.text

    assert calls["count"] == 1, "identical retry must not re-run inference"
    assert second.json()["status"] == "analysis_complete"
    assert second.json()["ai_assessment"] == first.json()["ai_assessment"]
    assert second.json()["pricing_assessment"] == first.json()["pricing_assessment"]


async def test_reanalyze_replay_does_not_duplicate_claim_data_or_notifications(
    client, session_factory
):
    headers = await _authed_headers(session_factory)
    claim = await _create_claim(client, headers)

    _use_ai_handler(lambda request: httpx.Response(200, json=ANALYZE_CLAIM_ACCEPTED_BODY))

    files = [("images", ("front.jpg", VALID_IMAGE_BYTES, "image/png"))]
    for _ in range(2):
        response = await client.post(
            f"/claims/{claim['id']}/analyze", files=files, headers=headers
        )
        assert response.status_code == 200, response.text

    listed = await client.get("/claims", headers=headers)
    assert len(listed.json()["items"]) == 1, "retry must never create a second claim"

    notifications = await client.get("/notifications", headers=headers)
    completed = [
        item
        for item in notifications.json()["items"]
        if item["claim_id"] == claim["id"]
    ]
    assert len(completed) == 1, "replay must not emit duplicate notifications"


async def test_reanalyze_with_different_images_reruns_inference(client, session_factory):
    headers = await _authed_headers(session_factory)
    claim = await _create_claim(client, headers)

    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, json=ANALYZE_CLAIM_ACCEPTED_BODY)

    _use_ai_handler(handler)

    first = await client.post(
        f"/claims/{claim['id']}/analyze",
        files=[("images", ("front.jpg", _png_bytes("red"), "image/png"))],
        headers=headers,
    )
    assert first.status_code == 200, first.text

    # A different image set is a genuinely new submission, never a replay.
    second = await client.post(
        f"/claims/{claim['id']}/analyze",
        files=[("images", ("front-2.jpg", _png_bytes("blue"), "image/png"))],
        headers=headers,
    )
    assert second.status_code == 200, second.text
    assert calls["count"] == 2


async def test_reanalyze_after_failed_attempt_reruns_inference_even_with_same_images(
    client, session_factory
):
    """A `failed` claim holds no reusable result — retrying the exact same
    images must re-run inference (e.g. the AI service was down and has
    recovered), never short-circuit to the failed state."""
    headers = await _authed_headers(session_factory)
    claim = await _create_claim(client, headers)

    files = [("images", ("front.jpg", VALID_IMAGE_BYTES, "image/png"))]

    def unavailable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    _use_ai_handler(unavailable)
    first = await client.post(f"/claims/{claim['id']}/analyze", files=files, headers=headers)
    assert first.status_code == 503

    reloaded = await client.get(f"/claims/{claim['id']}", headers=headers)
    assert reloaded.json()["status"] == "failed"

    _use_ai_handler(lambda request: httpx.Response(200, json=ANALYZE_CLAIM_ACCEPTED_BODY))
    second = await client.post(f"/claims/{claim['id']}/analyze", files=files, headers=headers)
    assert second.status_code == 200, second.text
    assert second.json()["status"] == "analysis_complete"


# ---------------------------------------------------------------------------
# GET /claims/{claim_id}
# ---------------------------------------------------------------------------


async def test_get_claim_returns_stored_claim(client, session_factory):
    headers = await _authed_headers(session_factory)
    claim = await _create_claim(client, headers)

    response = await client.get(f"/claims/{claim['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == claim["id"]


async def test_get_claim_not_found_returns_404(client, session_factory):
    headers = await _authed_headers(session_factory)
    response = await client.get("/claims/CLM-DOES-NOT-EXIST", headers=headers)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


async def test_create_claim_rate_limit_returns_429(client, session_factory):
    headers = await _authed_headers(session_factory)

    for _ in range(20):
        response = await client.post(
            "/claims",
            json={
                "vehicle_type": "Sedan",
                "vehicle_make": "Hyundai",
                "vehicle_model": "Verna",
                "vehicle_year": 2021,
            },
            headers=headers,
        )
        assert response.status_code == 201, response.text

    response = await client.post(
        "/claims",
        json={
            "vehicle_type": "Sedan",
            "vehicle_make": "Hyundai",
            "vehicle_model": "Verna",
            "vehicle_year": 2021,
        },
        headers=headers,
    )
    assert response.status_code == 429
    assert response.json()["error_code"] == "rate_limited"


async def test_analyze_claim_rate_limit_returns_429(client, session_factory):
    headers = await _authed_headers(session_factory)

    for _ in range(10):
        response = await client.post(
            "/claims/CLM-DOES-NOT-EXIST/analyze",
            files=[("images", ("front.jpg", VALID_IMAGE_BYTES, "image/png"))],
            headers=headers,
        )
        assert response.status_code == 404

    response = await client.post(
        "/claims/CLM-DOES-NOT-EXIST/analyze",
        files=[("images", ("front.jpg", VALID_IMAGE_BYTES, "image/png"))],
        headers=headers,
    )
    assert response.status_code == 429
    assert response.json()["error_code"] == "rate_limited"


# ---------------------------------------------------------------------------
# GET /claims (claim history list)
# ---------------------------------------------------------------------------


async def test_list_claims_requires_authentication(client):
    response = await client.get("/claims")
    assert response.status_code == 401


async def test_list_claims_empty_for_new_user(client, session_factory):
    headers = await _authed_headers(session_factory)
    response = await client.get("/claims", headers=headers)
    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_list_claims_returns_only_own_claims_newest_first(client, session_factory):
    headers_a = await _authed_headers(session_factory, google_sub="sub-a", email="a@example.com")
    headers_b = await _authed_headers(session_factory, google_sub="sub-b", email="b@example.com")

    await _create_claim(client, headers_a, vehicle_make="Hyundai", vehicle_model="Verna")
    second = await _create_claim(client, headers_a, vehicle_make="Maruti", vehicle_model="Swift")
    await _create_claim(client, headers_b, vehicle_make="Tata", vehicle_model="Nexon")

    response = await client.get("/claims", headers=headers_a)
    assert response.status_code == 200
    items = response.json()["items"]

    # Only A's two claims — B's claim never appears here regardless of
    # any query parameter, since ownership is enforced in the query itself.
    assert len(items) == 2
    assert items[0]["id"] == second["id"]  # newest first
    assert {item["vehicle_make"] for item in items} == {"Hyundai", "Maruti"}


async def test_list_claims_ignores_arbitrary_user_id_query_param(client, session_factory):
    headers_a = await _authed_headers(session_factory, google_sub="sub-a", email="a@example.com")
    headers_b = await _authed_headers(session_factory, google_sub="sub-b", email="b@example.com")
    await _create_claim(client, headers_b)

    response = await client.get("/claims?user_id=999", headers=headers_a)
    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_list_claims_includes_reference_image_and_summary(client, session_factory):
    headers = await _authed_headers(session_factory)
    claim = await _create_claim(client, headers, vehicle_make="MG", vehicle_model="Astor Blackstorm")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=ANALYZE_CLAIM_ACCEPTED_BODY)

    _use_ai_handler(handler)
    await client.post(
        f"/claims/{claim['id']}/analyze",
        files=[("images", ("front.jpg", VALID_IMAGE_BYTES, "image/png"))],
        headers=headers,
    )

    response = await client.get("/claims", headers=headers)
    item = response.json()["items"][0]

    assert item["vehicle_reference_image"]["url"].startswith("/vehicle-reference/")
    assert item["vehicle_reference_image"]["source"] == "category_fallback"
    assert 0.0 <= item["vehicle_reference_image"]["match_confidence"] < 0.5
    assert item["summary"]["damaged_parts"] == 1
    assert item["summary"]["total_min_inr"] == 2500
    assert item["summary"]["total_max_inr"] == 7000


async def test_list_claims_pending_analysis_has_null_pricing_summary(client, session_factory):
    headers = await _authed_headers(session_factory)
    await _create_claim(client, headers)

    response = await client.get("/claims", headers=headers)
    item = response.json()["items"][0]
    assert item["summary"]["damaged_parts"] == 0
    assert item["summary"]["total_min_inr"] is None
    assert item["summary"]["total_max_inr"] is None


async def test_list_claims_dashboard_indicators_before_any_analysis(client, session_factory):
    headers = await _authed_headers(session_factory)
    await _create_claim(client, headers)

    response = await client.get("/claims", headers=headers)
    item = response.json()["items"][0]
    assert item["has_policy"] is False
    assert item["policy_ready"] is False
    assert item["needs_manual_review"] is False


async def test_list_claims_needs_manual_review_indicator_after_review_required_analysis(client, session_factory):
    headers = await _authed_headers(session_factory)
    claim = await _create_claim(client, headers)

    _use_ai_handler(lambda request: httpx.Response(200, json=ANALYZE_CLAIM_REVIEW_REQUIRED_BODY))
    await client.post(
        f"/claims/{claim['id']}/analyze",
        files=[("images", ("front.jpg", VALID_IMAGE_BYTES, "image/png"))],
        headers=headers,
    )

    response = await client.get("/claims", headers=headers)
    item = response.json()["items"][0]
    assert item["needs_manual_review"] is True
