"""
FastAPI entrypoint. The claim create/analyze/retrieve routes are wired up;
the LangGraph supervisor wiring and remaining agent nodes come in a later
step — the current flow talks to the ai-service directly (see
`app/services/claim_service.py`) rather than through the graph.
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.routes.claims import router as claims_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.policy import router as policy_router
from app.api.routes.reports import router as reports_router
from app.api.routes.users import router as users_router
from app.api.routes.vehicle_catalog import router as vehicle_catalog_router
from app.config import get_settings
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.db.base import Base
from app.db.session import engine
from app.db.sqlite_dev_bootstrap import sync_missing_columns
from app.observability.context import new_request_id, set_request_id
from app.observability.logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # See app/db/sqlite_dev_bootstrap.py's module docstring — this is the
    # sqlite dev/sandbox substitute for Alembic-managed Postgres
    # migrations, and self-heals the exact schema-drift bug (a stale
    # dev.db missing a newly-added column) that originally broke the
    # claim flow this batch restored.
    if engine.dialect.name == "sqlite":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(sync_missing_columns)
    yield


app = FastAPI(
    title="ClaimSight India",
    description="Multimodal AI claims triage copilot for Indian motor insurers",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.middleware("http")
async def request_correlation(request: Request, call_next):
    """Assigns a correlation id to every request (reuses an inbound
    `X-Request-ID` if the caller/load balancer already set one) so every
    log line emitted while handling this request — including deep inside
    the claim workflow graph — can be tied back to it. Also logs a single
    request-completed line with status code + duration, the minimum
    "did this succeed and how long did it take" signal for every route,
    without needing per-route logging calls."""

    request_id = request.headers.get("X-Request-ID") or new_request_id()
    set_request_id(request_id)
    start = time.perf_counter()

    response = await call_next(request)

    duration_ms = int((time.perf_counter() - start) * 1000)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_completed method=%s path=%s status=%d duration_ms=%d",
        request.method, request.url.path, response.status_code, duration_ms,
    )
    return response


@app.middleware("http")
async def security_headers(request: Request, call_next):
    # This API only ever returns JSON, never renders HTML — no CSP needed
    # here (that belongs to the Next.js frontend). These three are cheap,
    # broadly safe defaults for a JSON API with no legitimate reason to be
    # framed, sniffed as a different content type, or leak a referrer.
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


app.include_router(claims_router)
app.include_router(policy_router)
app.include_router(reports_router)
app.include_router(notifications_router)
app.include_router(users_router)
app.include_router(vehicle_catalog_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Never leak internal stack traces / exception messages to the client
    # — log the detail server-side, return a generic body.
    logger.exception("Unhandled exception on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness only — never touches the database or the ai-service.
    Answers "is this process up", not "can it serve real traffic"; see
    `/ready` for the latter."""
    return {"status": "ok", "environment": settings.environment}


@app.get("/ready")
async def ready() -> JSONResponse:
    """Readiness check — verifies the database is actually reachable
    before a load balancer / orchestrator sends this instance real
    traffic. Does not check the ai-service: a claim can still be created
    (and its history browsed) with the ai-service down, so this instance
    is legitimately "ready" for a meaningful slice of traffic either way
    — the ai-service's own reachability is instead surfaced per-request
    as the existing 503 from `POST /claims/{id}/analyze`."""
    from sqlalchemy import text

    from app.db.session import engine

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Readiness check failed: database unreachable")
        return JSONResponse(status_code=503, content={"status": "not_ready", "reason": "database_unreachable"})

    return JSONResponse(status_code=200, content={"status": "ready"})
