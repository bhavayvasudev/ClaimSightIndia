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

from app.config import Settings
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


@pytest.fixture(autouse=True)
def image_dir(tmp_path, monkeypatch):
    """Every test in this file that stores a 'wikimedia'-sourced image
    must land in a throwaway directory, never the real backend/data/ —
    and it lets tests simulate a lost file by deleting it from a known
    location."""
    monkeypatch.setattr(vr, "get_settings", lambda: Settings(vehicle_image_dir=str(tmp_path)))
    return tmp_path


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
            # A real resolution always stores the bytes it returns — the
            # cache-hit check below verifies the file is still there, so
            # a fabricated URL with no backing file would (correctly)
            # never be trusted as a cache hit.
            url = vr.store_vehicle_image(b"fake-jpeg-bytes", "jpg", make=make, model=model)
            return vr.ReferenceImageResult(image_url=url, source="wikimedia", match_confidence=0.75)

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


async def test_local_file_missing_ignores_non_local_urls():
    """Category SVGs and any future non-local curated asset never depend
    on this process's disk — only /vehicle-images/ URLs are ever checked
    against the filesystem."""
    assert vr._local_file_missing("/vehicle-reference/sedan.svg") is False


async def test_local_file_missing_true_when_file_absent(image_dir):
    assert vr._local_file_missing("/vehicle-images/does-not-exist.jpg") is True


async def test_local_file_missing_false_when_file_present(image_dir):
    url = vr.store_vehicle_image(b"bytes", "jpg", make="Honda", model="Civic")
    assert vr._local_file_missing(url) is False


class _StoringProvider(vr.VehicleImageProvider):
    """Mirrors DefaultVehicleImageProvider's real contract: a 'wikimedia'
    result always has its bytes persisted via store_vehicle_image before
    the URL is handed back."""

    def __init__(self, *, fail: bool = False):
        self.attempts = 0
        self.fail = fail

    async def resolve(self, *, make, model, year, vehicle_type, variant=None):
        self.attempts += 1
        if self.fail:
            return vr._category_fallback(vehicle_type)
        url = vr.store_vehicle_image(f"content-{self.attempts}".encode(), "jpg", make=make, model=model)
        return vr.ReferenceImageResult(image_url=url, source="wikimedia", match_confidence=0.75)


async def test_resolution_survives_disk_loss_across_a_restart(repo, image_dir):
    """Reproduces the production bug: the reference image was resolved
    and stored, then the process's disk was wiped (e.g. a Render restart
    onto a fresh ephemeral filesystem) while the DB cache row survived.
    The stale row must never be served as a permanently-dead URL — it is
    detected and repaired on the next request."""
    provider = _StoringProvider()

    first = await vr.resolve_vehicle_reference_image(
        repo, make="Hyundai", model="Creta", year=2022, vehicle_type="SUV", provider=provider
    )
    assert provider.attempts == 1
    stored_path = image_dir / first.image_url.rsplit("/", 1)[-1]
    assert stored_path.is_file()

    # File still present: a cache hit must not re-run the resolution.
    still_cached = await vr.resolve_vehicle_reference_image(
        repo, make="Hyundai", model="Creta", year=2022, vehicle_type="SUV", provider=provider
    )
    assert still_cached.id == first.id
    assert provider.attempts == 1

    # Simulate the restart: the DB row survives, the file does not.
    stored_path.unlink()

    repaired = await vr.resolve_vehicle_reference_image(
        repo, make="Hyundai", model="Creta", year=2022, vehicle_type="SUV", provider=provider
    )
    assert repaired.id == first.id
    assert repaired.source == "wikimedia"
    assert provider.attempts == 2
    assert (image_dir / repaired.image_url.rsplit("/", 1)[-1]).is_file()


async def test_stale_row_downgrades_to_fallback_when_repair_fails(repo, image_dir):
    """If the file is gone AND the repair attempt itself can't resolve a
    real image (e.g. Wikimedia unreachable), the row must not keep
    pointing at the known-dead URL — it downgrades to the same neutral
    illustration a first-time miss gets, and re-enters the normal
    fallback retry cycle."""
    provider = _StoringProvider()
    first = await vr.resolve_vehicle_reference_image(
        repo, make="Tata Motors", model="Punch", year=2023, vehicle_type="SUV", provider=provider
    )
    stored_path = image_dir / first.image_url.rsplit("/", 1)[-1]
    stored_path.unlink()

    provider.fail = True
    downgraded = await vr.resolve_vehicle_reference_image(
        repo, make="Tata Motors", model="Punch", year=2023, vehicle_type="SUV", provider=provider
    )
    assert downgraded.id == first.id
    assert downgraded.source == "category_fallback"

    # Now behaves exactly like any other cached fallback: gated until
    # the retry window opens.
    gated = await vr.resolve_vehicle_reference_image(
        repo, make="Tata Motors", model="Punch", year=2023, vehicle_type="SUV", provider=provider
    )
    assert gated.source == "category_fallback"
    assert provider.attempts == 2
