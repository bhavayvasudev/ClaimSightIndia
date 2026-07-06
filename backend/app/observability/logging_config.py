"""Structured application logging (Task 13).

Deliberately a plain stdlib `logging` config, not a new logging
framework dependency — this project already uses `logging.getLogger(__name__)`
everywhere (see `app/main.py`, `app/api/routes/claims.py`, etc.); this
module only changes the *formatter* (structured, with request/claim
correlation) and adds the correlation-id filter, without requiring any
call site to change.

Never logs: request/response bodies, `Authorization` headers, bearer
tokens, OAuth details, full policy document text, or any other secret —
every log call in this codebase logs a message + safe identifiers
(claim id, status codes, counts), never raw payloads. This module doesn't
enforce that itself (there's no reliable generic way to redact arbitrary
call-site strings); it's a call-site discipline documented here and
followed throughout `app/`.
"""

from __future__ import annotations

import logging
import sys

from app.observability.context import ObservabilityLogFilter

_FORMAT = "%(asctime)s %(levelname)-8s [req=%(request_id)s claim=%(claim_id)s] %(name)s: %(message)s"


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.setLevel(level)

    # Idempotent: FastAPI's dev reloader / repeated test-suite imports of
    # app.main must never accumulate duplicate handlers on the root logger.
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT))
    handler.addFilter(ObservabilityLogFilter())
    root.addHandler(handler)
