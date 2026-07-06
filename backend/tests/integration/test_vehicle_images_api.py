"""Route-level tests for `GET /vehicle-images/{filename}`
(`app/api/routes/vehicle_images.py`) — the stable application URL every
remotely-resolved reference vehicle image is served under. Public by
design (generic model-line images, no user/claim data), so the tests
here are about serving correctness and path safety, not auth.
"""

from __future__ import annotations

import httpx
import pytest
import pytest_asyncio

from app.api.routes import vehicle_images as vehicle_images_route
from app.config import Settings
from app.main import app

pytestmark = pytest.mark.asyncio

PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da63fcff9fa11e00078d027e8fd5480a0000000049454e44ae426082"
)


@pytest.fixture
def image_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(
        vehicle_images_route, "get_settings", lambda: Settings(vehicle_image_dir=str(tmp_path))
    )
    return tmp_path


@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


async def test_serves_stored_image_with_correct_content_type_and_caching(client, image_dir):
    (image_dir / "honda-civic-abc123.png").write_bytes(PNG_BYTES)

    response = await client.get("/vehicle-images/honda-civic-abc123.png")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert "immutable" in response.headers["cache-control"]
    assert response.content == PNG_BYTES


async def test_missing_image_is_404(client, image_dir):
    response = await client.get("/vehicle-images/no-such-file.jpg")
    assert response.status_code == 404


async def test_unsafe_filenames_are_rejected(client, image_dir):
    # A real file exists, but nothing outside the safe-name pattern may
    # reach the filesystem at all.
    (image_dir / "honda-civic-abc123.png").write_bytes(PNG_BYTES)

    for bad in (
        "..%2F..%2Fapp%2Fconfig.py",
        "%2e%2e%2fsecrets.env",
        "honda civic.png",
        "HONDA-CIVIC.PNG",
        "civic.svg",
        "civic.png.py",
    ):
        response = await client.get(f"/vehicle-images/{bad}")
        assert response.status_code in (404, 422), bad
