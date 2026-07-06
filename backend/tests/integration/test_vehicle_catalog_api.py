"""Route-level tests for the public vehicle-catalog endpoints
(`app/api/routes/vehicle_catalog.py`, Tasks 4/5/8). Unauthenticated by
design — this is public reference data, not claim- or user-scoped."""

from __future__ import annotations

import httpx
import pytest
import pytest_asyncio

from app.main import app

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def test_list_manufacturers_no_auth_required(client):
    response = await client.get("/vehicle-catalog/manufacturers")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert any(mf["id"] == "mg-motor" for mf in body)
    assert any(mf["status"] == "historical" for mf in body)


async def test_manufacturer_models(client):
    response = await client.get("/vehicle-catalog/manufacturers/mg-motor/models")
    assert response.status_code == 200
    models = response.json()
    assert any(m["id"] == "astor" and m["category"] == "SUV" for m in models)


async def test_unknown_manufacturer_returns_404(client):
    response = await client.get("/vehicle-catalog/manufacturers/does-not-exist/models")
    assert response.status_code == 404


async def test_model_variants(client):
    response = await client.get("/vehicle-catalog/manufacturers/mg-motor/models/astor/variants")
    assert response.status_code == 200
    assert "Blackstorm" in response.json()


async def test_unknown_model_variants_returns_404(client):
    response = await client.get("/vehicle-catalog/manufacturers/mg-motor/models/not-a-model/variants")
    assert response.status_code == 404


async def test_catalog_response_carries_cache_header(client):
    response = await client.get("/vehicle-catalog/manufacturers")
    assert "cache-control" in {k.lower() for k in response.headers.keys()}
