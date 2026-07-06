"""Unit tests for the reference-vehicle-image resolver
(`app/services/vehicle_reference.py`). Covers the cache-or-compute
behavior and the fallback-vs-curated confidence distinction — this is
never claim evidence, so it must never claim a confident match it
doesn't actually have.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.vehicle_reference_repository import VehicleReferenceImageRepository
from app.services import vehicle_reference as vr

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def repo():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield VehicleReferenceImageRepository(session)
    await engine.dispose()


async def test_unknown_model_falls_back_to_category_illustration(repo):
    record = await vr.resolve_vehicle_reference_image(
        repo, make="MG", model="Astor Blackstorm", year=2024, vehicle_type="SUV"
    )
    assert record.source == "category_fallback"
    assert record.image_url == vr.CATEGORY_FALLBACK_IMAGES["SUV"]
    # A category illustration is never presented as a confident,
    # vehicle-specific match.
    assert record.match_confidence < 0.5


async def test_unknown_category_falls_back_to_default_image(repo):
    record = await vr.resolve_vehicle_reference_image(
        repo, make="Unknown", model="Thing", year=None, vehicle_type="Not A Real Category"
    )
    assert record.image_url == vr.DEFAULT_CATEGORY_IMAGE


async def test_second_resolution_hits_cache_not_recomputed(repo, monkeypatch):
    calls = []

    class _CountingProvider(vr.VehicleImageProvider):
        def resolve(self, *, make, model, year, vehicle_type, variant=None):
            calls.append((make, model, year, vehicle_type))
            return vr.ReferenceImageResult(
                image_url="/vehicle-reference/sedan.svg", source="category_fallback", match_confidence=0.3
            )

    monkeypatch.setattr(vr, "get_default_provider", lambda: _CountingProvider())

    first = await vr.resolve_vehicle_reference_image(
        repo, make="Hyundai", model="Verna", year=2021, vehicle_type="Sedan"
    )
    second = await vr.resolve_vehicle_reference_image(
        repo, make="Hyundai", model="Verna", year=2021, vehicle_type="Sedan"
    )
    assert first.id == second.id
    assert len(calls) == 1


async def test_curated_entry_is_returned_with_higher_confidence(repo, monkeypatch):
    monkeypatch.setitem(vr.CURATED_VEHICLE_IMAGES, "mg astor blackstorm", "/vehicle-reference/mg-astor.svg")
    record = await vr.resolve_vehicle_reference_image(
        repo, make="MG", model="Astor Blackstorm", year=2024, vehicle_type="SUV"
    )
    assert record.source == "curated_catalog"
    assert record.image_url == "/vehicle-reference/mg-astor.svg"
    assert record.match_confidence > 0.5
