"""Persistence tests for ClaimRepository. Run against an in-memory SQLite
database (via aiosqlite) rather than Postgres — the model's JSON columns
fall back to generic JSON on non-Postgres dialects for exactly this reason
(see `_jsonb_or_json` in app/db/models/claim.py), so these tests don't need
a live Postgres instance or any Docker service running.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models.claim import ClaimRecordStatus
from app.db.repository import ClaimRepository

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as s:
        yield s

    await engine.dispose()


async def test_create_persists_claim_with_intake_status(session):
    repo = ClaimRepository(session)

    record = await repo.create(
        claim_id="CLM-TEST00000001",
        vehicle_type="Sedan",
        vehicle_make="Hyundai",
        vehicle_model="Verna",
        vehicle_year=2021,
    )

    assert record.id is not None
    assert record.claim_id == "CLM-TEST00000001"
    assert record.status == ClaimRecordStatus.INTAKE.value
    assert record.ai_assessment is None
    assert record.pricing_assessment is None
    assert record.created_at is not None
    assert record.updated_at is not None


async def test_get_by_claim_id_returns_none_when_missing(session):
    repo = ClaimRepository(session)
    assert await repo.get_by_claim_id("CLM-DOES-NOT-EXIST") is None


async def test_get_by_claim_id_round_trips_jsonb_shaped_fields(session):
    repo = ClaimRepository(session)
    await repo.create(
        claim_id="CLM-TEST00000002",
        vehicle_type="SUV",
        vehicle_make=None,
        vehicle_model=None,
        vehicle_year=None,
    )

    record = await repo.get_by_claim_id("CLM-TEST00000002")
    assert record is not None

    record.status = ClaimRecordStatus.ANALYSIS_COMPLETE.value
    record.ai_assessment = {
        "damaged_parts": [{"part": "Front bumper", "severity": "Moderate"}],
        "summary": {"total_parts": 1, "accepted": 1, "review_required": 0},
    }
    record.pricing_assessment = {
        "per_part": {"Front bumper": {"min_inr": 2500, "max_inr": 7000}},
        "total_min_inr": 2500,
        "total_max_inr": 7000,
    }
    await repo.save(record)

    reloaded = await repo.get_by_claim_id("CLM-TEST00000002")
    assert reloaded.status == ClaimRecordStatus.ANALYSIS_COMPLETE.value
    assert reloaded.ai_assessment["damaged_parts"][0]["part"] == "Front bumper"
    assert reloaded.pricing_assessment["total_min_inr"] == 2500


async def test_claim_id_is_unique(session):
    repo = ClaimRepository(session)
    await repo.create(
        claim_id="CLM-DUPLICATE0001",
        vehicle_type="Hatchback",
        vehicle_make=None,
        vehicle_model=None,
        vehicle_year=None,
    )

    with pytest.raises(Exception):
        await repo.create(
            claim_id="CLM-DUPLICATE0001",
            vehicle_type="Sedan",
            vehicle_make=None,
            vehicle_model=None,
            vehicle_year=None,
        )
