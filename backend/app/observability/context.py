"""Request-scoped observability context: correlation id + claim id.

Uses `contextvars` (not thread-locals) since the app is async — each
in-flight request/task gets its own isolated value, safe under
concurrent requests on the same event loop. `ObservabilityLogFilter`
reads these on every log record so every log line during a request
carries its correlation id (and claim id, once known) without every
call site having to pass them explicitly.
"""

from __future__ import annotations

import logging
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Optional

_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_claim_id: ContextVar[Optional[str]] = ContextVar("claim_id", default=None)


def new_request_id() -> str:
    return uuid.uuid4().hex[:16]


def set_request_id(value: str) -> None:
    _request_id.set(value)


def get_request_id() -> Optional[str]:
    return _request_id.get()


@contextmanager
def bind_claim_id(claim_id: Optional[str]) -> Iterator[None]:
    """Wrap the code that handles one claim so every log line emitted
    inside (including from deep inside the graph nodes / RAG pipeline)
    is tagged with which claim it's about — without threading `claim_id`
    through every function signature."""
    token = _claim_id.set(claim_id)
    try:
        yield
    finally:
        _claim_id.reset(token)


def get_claim_id() -> Optional[str]:
    return _claim_id.get()


class ObservabilityLogFilter(logging.Filter):
    """Attaches `request_id`/`claim_id` to every `LogRecord` so the
    formatter in `logging_config.py` can render them. A record produced
    outside any request/claim context (e.g. at startup) gets `"-"` for
    both, never a crash from a missing attribute."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        record.claim_id = get_claim_id() or "-"
        return True
