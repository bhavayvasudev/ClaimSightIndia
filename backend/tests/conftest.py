"""Fixtures shared across the whole test suite.

`_reset_rate_limiter` matters specifically because slowapi's `Limiter`
(`app.core.rate_limit.limiter`) is a single module-level instance shared
by every test in the process, while each test's own in-memory SQLite
database is created fresh — so a fresh test's "user id 1" would otherwise
inherit request counts left over from a previous test's own "user id 1"
against the same in-memory rate-limit storage.
"""

from __future__ import annotations

import os

# Must run before anything imports app.config (get_settings() is
# lru_cache'd — whatever it reads first sticks for the whole test
# session). A real secret is required outside development, but nothing
# here ever talks to a real Google/production system, so a fixed test
# value is fine and keeps every test's issued/verified tokens consistent.
os.environ.setdefault("BACKEND_JWT_SECRET", "test-only-secret-do-not-use-in-production")

import pytest  # noqa: E402

from app.core.rate_limit import limiter  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter.reset()
    yield
