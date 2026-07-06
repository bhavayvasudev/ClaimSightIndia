"""Manual review (Task 8) and notification (Task 12) repository tests:
review item creation + resolution state transition, and notification
ownership/unread-count/mark-read behavior.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models.review_item import ReviewItemSource, ReviewItemStatus
from app.db.notification_repository import NotificationRepository
from app.db.repository import ClaimRepository
from app.db.review_repository import ReviewItemRepository
from app.db.user_repository import UserRepository

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


async def _make_claim(session):
    repo = ClaimRepository(session)
    return await repo.create(
        claim_id="CLM-TESTREVIEW01", vehicle_type="Sedan", vehicle_make="Hyundai",
        vehicle_model="Verna", vehicle_year=2021,
    )


async def _make_user(session, **overrides):
    defaults = {"google_sub": "sub-1", "email": "a@example.com", "name": "A", "avatar_url": None}
    defaults.update(overrides)
    return await UserRepository(session).create(**defaults)


# ---------------------------------------------------------------------------
# Review items (Task 8)
# ---------------------------------------------------------------------------


async def test_create_review_item_defaults_to_pending(session):
    claim = await _make_claim(session)
    repo = ReviewItemRepository(session)

    item = await repo.create(
        claim_id=claim.id, part="Front bumper", reason="Low confidence detection",
        source=ReviewItemSource.DAMAGE_ASSESSMENT.value,
    )

    assert item.id is not None
    assert item.status == ReviewItemStatus.PENDING.value
    assert item.resolved_at is None


async def test_list_for_claim_is_scoped_to_that_claim(session):
    claim_a = await _make_claim(session)
    repo = ClaimRepository(session)
    claim_b = await repo.create(
        claim_id="CLM-TESTREVIEW02", vehicle_type="SUV", vehicle_make="Tata",
        vehicle_model="Nexon", vehicle_year=2022,
    )

    review_repo = ReviewItemRepository(session)
    await review_repo.create(claim_id=claim_a.id, part=None, reason="A", source=ReviewItemSource.RISK_SIGNAL.value)
    await review_repo.create(claim_id=claim_b.id, part=None, reason="B", source=ReviewItemSource.RISK_SIGNAL.value)

    items = await review_repo.list_for_claim(claim_a.id)
    assert len(items) == 1
    assert items[0].reason == "A"


async def test_resolve_transitions_status_and_sets_resolved_at(session):
    claim = await _make_claim(session)
    review_repo = ReviewItemRepository(session)
    item = await review_repo.create(
        claim_id=claim.id, part=None, reason="Needs a human look",
        source=ReviewItemSource.RISK_SIGNAL.value,
    )

    resolved = await review_repo.resolve(item.id, reviewer_note="Confirmed genuine, cleared.")

    assert resolved.status == ReviewItemStatus.RESOLVED.value
    assert resolved.resolved_at is not None
    assert resolved.reviewer_note == "Confirmed genuine, cleared."


async def test_replace_open_items_preserves_resolved_history(session):
    claim = await _make_claim(session)
    review_repo = ReviewItemRepository(session)

    first = await review_repo.create(
        claim_id=claim.id, part="Front bumper", reason="First pass finding",
        source=ReviewItemSource.DAMAGE_ASSESSMENT.value,
    )
    await review_repo.resolve(first.id, reviewer_note="Cleared")

    await review_repo.replace_open_items_for_claim(
        claim.id, [(None, "New risk signal from re-run", ReviewItemSource.RISK_SIGNAL.value)]
    )

    items = await review_repo.list_for_claim(claim.id)
    assert len(items) == 2
    resolved_items = [i for i in items if i.status == ReviewItemStatus.RESOLVED.value]
    pending_items = [i for i in items if i.status == ReviewItemStatus.PENDING.value]
    assert len(resolved_items) == 1
    assert len(pending_items) == 1
    assert pending_items[0].reason == "New risk signal from re-run"


# ---------------------------------------------------------------------------
# Notifications (Task 12)
# ---------------------------------------------------------------------------


async def test_notification_created_for_correct_user_only(session):
    user_a = await _make_user(session, google_sub="sub-a", email="a@example.com")
    user_b = await _make_user(session, google_sub="sub-b", email="b@example.com")

    repo = NotificationRepository(session)
    await repo.create(user_id=user_a.id, claim_id=None, type="claim_analysis_completed", title="T", body="B")

    a_items = await repo.list_for_user(user_a.id)
    b_items = await repo.list_for_user(user_b.id)

    assert len(a_items) == 1
    assert len(b_items) == 0


async def test_other_user_cannot_mark_read_someone_elses_notification(session):
    user_a = await _make_user(session, google_sub="sub-a", email="a@example.com")
    user_b = await _make_user(session, google_sub="sub-b", email="b@example.com")

    repo = NotificationRepository(session)
    notif = await repo.create(user_id=user_a.id, claim_id=None, type="report_ready", title="T", body="B")

    result = await repo.mark_read(notif.id, user_b.id)
    assert result is None

    reloaded = await repo.list_for_user(user_a.id)
    assert reloaded[0].read_at is None


async def test_unread_count_reflects_only_unread(session):
    user = await _make_user(session)
    repo = NotificationRepository(session)
    n1 = await repo.create(user_id=user.id, claim_id=None, type="report_ready", title="T1", body="B1")
    await repo.create(user_id=user.id, claim_id=None, type="report_ready", title="T2", body="B2")

    assert await repo.unread_count(user.id) == 2

    await repo.mark_read(n1.id, user.id)
    assert await repo.unread_count(user.id) == 1


async def test_mark_all_read_clears_unread_count(session):
    user = await _make_user(session)
    repo = NotificationRepository(session)
    await repo.create(user_id=user.id, claim_id=None, type="report_ready", title="T1", body="B1")
    await repo.create(user_id=user.id, claim_id=None, type="report_ready", title="T2", body="B2")

    await repo.mark_all_read(user.id)
    assert await repo.unread_count(user.id) == 0
