"""Unit tests for the reference-vehicle-image resolver
(`app/services/vehicle_reference.py`). Covers the cache-or-compute
behavior, the fallback-vs-real-match confidence distinction, and the
fallback-upgrade path (a cached category illustration is not final —
it upgrades in place once a real image resolves). Remote lookup is
disabled process-wide in tests (see tests/conftest.py); the Wikimedia
tier is exercised via fake providers and pure-function tests in
test_wikimedia_vehicle_images.py.
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


@pytest.fixture(autouse=True)
def _clear_retry_gate():
    vr._remote_retry_not_before.clear()
    yield
    vr._remote_retry_not_before.clear()


async def test_unknown_model_falls_back_to_category_illustration(repo):
    record = await vr.resolve_vehicle_reference_image(
        repo, make="MG", model="Astor", year=2024, vehicle_type="SUV"
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


async def test_cache_key_ignores_year_and_variant(repo):
    """The representative image is a property of the model line — a 2010
    and a 2024 Honda Civic must share one cached resolution (keying on
    year was one of the original display bugs)."""
    first = await vr.resolve_vehicle_reference_image(
        repo, make="Honda", model="Civic", year=2010, vehicle_type="Sedan"
    )
    second = await vr.resolve_vehicle_reference_image(
        repo, make="Honda", model="Civic", year=2024, vehicle_type="Sedan", variant="ZX CVT"
    )
    assert first.id == second.id


async def test_second_resolution_hits_cache_not_recomputed(repo):
    calls = []

    class _CountingProvider(vr.VehicleImageProvider):
        async def resolve(self, *, make, model, year, vehicle_type, variant=None):
            calls.append((make, model))
            return vr.ReferenceImageResult(
                image_url="/vehicle-images/hyundai-verna-abc.jpg", source="wikimedia", match_confidence=0.75
            )

    provider = _CountingProvider()
    first = await vr.resolve_vehicle_reference_image(
        repo, make="Hyundai", model="Verna", year=2021, vehicle_type="Sedan", provider=provider
    )
    second = await vr.resolve_vehicle_reference_image(
        repo, make="Hyundai", model="Verna", year=2021, vehicle_type="Sedan", provider=provider
    )
    assert first.id == second.id
    assert len(calls) == 1


async def test_curated_entry_is_returned_with_higher_confidence(repo, monkeypatch):
    monkeypatch.setitem(vr.CURATED_VEHICLE_IMAGES, "mg astor", "/vehicle-reference/mg-astor.svg")
    record = await vr.resolve_vehicle_reference_image(
        repo, make="MG", model="Astor", year=2024, vehicle_type="SUV"
    )
    assert record.source == "curated_catalog"
    assert record.image_url == "/vehicle-reference/mg-astor.svg"
    assert record.match_confidence > 0.5


async def test_cached_fallback_upgrades_in_place_when_remote_resolves(repo):
    """One offline moment must never permanently pin a vehicle to the
    generic illustration — the cached fallback row upgrades in place on
    a later successful resolution, so old claims pick it up too."""

    class _FailingThenWorkingProvider(vr.VehicleImageProvider):
        def __init__(self):
            self.attempts = 0

        async def resolve(self, *, make, model, year, vehicle_type, variant=None):
            self.attempts += 1
            if self.attempts == 1:
                return vr._category_fallback(vehicle_type)
            return vr.ReferenceImageResult(
                image_url="/vehicle-images/tata-nexon-abc.jpg", source="wikimedia", match_confidence=0.75
            )

    provider = _FailingThenWorkingProvider()
    first = await vr.resolve_vehicle_reference_image(
        repo, make="Tata Motors", model="Nexon", year=2023, vehicle_type="SUV", provider=provider
    )
    assert first.source == "category_fallback"

    # Within the retry window the cached fallback is returned untouched.
    gated = await vr.resolve_vehicle_reference_image(
        repo, make="Tata Motors", model="Nexon", year=2023, vehicle_type="SUV", provider=provider
    )
    assert gated.source == "category_fallback"
    assert provider.attempts == 1

    # Once the retry window opens, the row upgrades in place.
    vr._remote_retry_not_before.clear()
    upgraded = await vr.resolve_vehicle_reference_image(
        repo, make="Tata Motors", model="Nexon", year=2023, vehicle_type="SUV", provider=provider
    )
    assert upgraded.id == first.id
    assert upgraded.source == "wikimedia"
    assert upgraded.image_url == "/vehicle-images/tata-nexon-abc.jpg"


async def test_default_provider_skips_remote_when_disabled(repo):
    """tests/conftest.py disables remote lookup process-wide — the
    default provider must resolve to the category illustration without
    any network attempt (this test would hang/fail on a network call)."""
    record = await vr.resolve_vehicle_reference_image(
        repo, make="Toyota", model="Fortuner", year=2022, vehicle_type="SUV"
    )
    assert record.source == "category_fallback"
