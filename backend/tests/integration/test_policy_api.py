"""Route-level tests for policy document upload/status
(`app/api/routes/policy.py`)."""

from __future__ import annotations

import httpx
import pytest
import pytest_asyncio
from fpdf import FPDF, XPos, YPos
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.routes import claims as claims_routes
from app.api.routes import policy as policy_routes
from app.core.security import issue_access_token
from app.db.base import Base
from app.db.models.user import UserRecord
from app.db.session import get_db
from app.db.user_repository import UserRepository
from app.main import app
from app.services.ai_client import AIServiceClient

pytestmark = pytest.mark.asyncio


def _make_policy_pdf() -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    for line in [
        "POLICY SCHEDULE",
        "Policy No: 3001/PVT/2026/00099999",
        "Policy Period: 01/01/2026 To 31/12/2026",
        "This is a Comprehensive policy.",
        "Insured's Declared Value (IDV): 5,00,000",
        "Own Damage Coverage",
        "The Company shall indemnify the insured against accidental damage.",
    ]:
        pdf.cell(0, 8, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    return bytes(pdf.output())


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


async def test_upload_policy_requires_authentication(client, session_factory):
    headers = _headers_for(await _make_user(session_factory))
    claim = await _create_claim(client, headers)

    response = await client.post(
        f"/claims/{claim['id']}/policy",
        files=[("file", ("policy.pdf", _make_policy_pdf(), "application/pdf"))],
    )
    assert response.status_code == 401


async def test_upload_policy_success_extracts_structured_data(client, session_factory):
    user = await _make_user(session_factory)
    headers = _headers_for(user)
    claim = await _create_claim(client, headers)

    response = await client.post(
        f"/claims/{claim['id']}/policy",
        files=[("file", ("policy.pdf", _make_policy_pdf(), "application/pdf"))],
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "processed"
    assert body["structured_data"]["idv_inr"] == 500000
    assert body["structured_data"]["policy_type"] == "Comprehensive"
    # Full extracted text is never returned over the API.
    assert "extracted_text" not in body


async def test_claim_report_masks_policy_number_and_surfaces_structured_fields(client, session_factory):
    """Task 3 — the unified report is the surface the claim page actually
    renders from; the full policy number must never appear in it, only
    the last-4-masked form, alongside the other structured fields the
    Policy Analysis panel displays."""
    user = await _make_user(session_factory)
    headers = _headers_for(user)
    claim = await _create_claim(client, headers)

    upload_response = await client.post(
        f"/claims/{claim['id']}/policy",
        files=[("file", ("policy.pdf", _make_policy_pdf(), "application/pdf"))],
        headers=headers,
    )
    assert upload_response.status_code == 201, upload_response.text
    full_policy_number = upload_response.json()["structured_data"]["policy_number"]
    assert full_policy_number  # the fixture's PDF has one

    report_response = await client.get(f"/claims/{claim['id']}/report", headers=headers)
    assert report_response.status_code == 200
    policy = report_response.json()["policy"]

    assert policy["policy_number_masked"] is not None
    assert policy["policy_number_masked"] != full_policy_number
    assert policy["policy_number_masked"].endswith(full_policy_number[-4:])
    assert full_policy_number not in report_response.text
    assert policy["policy_type"] == "Comprehensive"
    assert policy["idv_inr"] == 500000


async def test_upload_policy_rejects_unsupported_file_type(client, session_factory):
    headers = _headers_for(await _make_user(session_factory))
    claim = await _create_claim(client, headers)

    response = await client.post(
        f"/claims/{claim['id']}/policy",
        files=[("file", ("policy.txt", b"not a policy", "text/plain"))],
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error_code"] == "unsupported_file_type"


async def test_upload_policy_scanned_pdf_with_no_text_marks_failed(client, session_factory):
    headers = _headers_for(await _make_user(session_factory))
    claim = await _create_claim(client, headers)

    from pypdf import PdfWriter
    import io

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)

    response = await client.post(
        f"/claims/{claim['id']}/policy",
        files=[("file", ("scanned.pdf", buf.getvalue(), "application/pdf"))],
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "failed"
    assert body["error_message"] is not None


async def test_policy_processing_failure_does_not_erase_damage_assessment(client, session_factory):
    """Task 10 — a policy upload that fails to process must never wipe out
    an already-successful damage assessment on the same claim."""
    import base64
    import io

    from pypdf import PdfWriter

    headers = _headers_for(await _make_user(session_factory))
    claim = await _create_claim(client, headers)

    valid_image = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    app.dependency_overrides[claims_routes.get_ai_service_client] = lambda: AIServiceClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
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
                },
            )
        )
    )
    analyze_response = await client.post(
        f"/claims/{claim['id']}/analyze",
        files=[("images", ("front.jpg", valid_image, "image/png"))],
        headers=headers,
    )
    assert analyze_response.status_code == 200, analyze_response.text
    assert analyze_response.json()["ai_assessment"] is not None

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    policy_response = await client.post(
        f"/claims/{claim['id']}/policy",
        files=[("file", ("scanned.pdf", buf.getvalue(), "application/pdf"))],
        headers=headers,
    )
    assert policy_response.status_code == 201
    assert policy_response.json()["status"] == "failed"

    claim_after = await client.get(f"/claims/{claim['id']}", headers=headers)
    assert claim_after.status_code == 200
    body = claim_after.json()
    assert body["ai_assessment"] is not None
    assert body["ai_assessment"]["summary"]["total_parts"] == 1
    assert body["pricing_assessment"] is not None


async def test_get_policy_status_not_found_before_upload(client, session_factory):
    headers = _headers_for(await _make_user(session_factory))
    claim = await _create_claim(client, headers)

    response = await client.get(f"/claims/{claim['id']}/policy", headers=headers)
    assert response.status_code == 404


async def test_user_b_cannot_upload_policy_to_user_a_claim(client, session_factory):
    headers_a = _headers_for(await _make_user(session_factory, google_sub="sub-a", email="a@example.com"))
    headers_b = _headers_for(await _make_user(session_factory, google_sub="sub-b", email="b@example.com"))
    claim = await _create_claim(client, headers_a)

    response = await client.post(
        f"/claims/{claim['id']}/policy",
        files=[("file", ("policy.pdf", _make_policy_pdf(), "application/pdf"))],
        headers=headers_b,
    )
    assert response.status_code == 404


async def test_reupload_policy_replaces_prior_document(client, session_factory):
    headers = _headers_for(await _make_user(session_factory))
    claim = await _create_claim(client, headers)

    first = await client.post(
        f"/claims/{claim['id']}/policy",
        files=[("file", ("policy.pdf", _make_policy_pdf(), "application/pdf"))],
        headers=headers,
    )
    assert first.status_code == 201

    second = await client.post(
        f"/claims/{claim['id']}/policy",
        files=[("file", ("policy-v2.pdf", _make_policy_pdf(), "application/pdf"))],
        headers=headers,
    )
    assert second.status_code == 201
    assert second.json()["filename"] == "policy-v2.pdf"

    status_response = await client.get(f"/claims/{claim['id']}/policy", headers=headers)
    assert status_response.json()["filename"] == "policy-v2.pdf"
