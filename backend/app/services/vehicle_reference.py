"""Reference vehicle image resolution.

IMPORTANT — a reference image is a generic illustration/photo of "what
this kind of vehicle looks like", resolved from make/model/category
alone. It is NOT claim evidence: never pass it to the ai-service, never
mix it with uploaded damage photos, never use it for severity
estimation, and never present it as the claimant's actual vehicle. Every
API response that carries one is labelled `vehicle_reference_image` for
exactly this reason — see `app/schemas/dashboard_api.py`.

Resolution tiers, in order:
  1. curated per-model catalog (`CURATED_VEHICLE_IMAGES`) — real,
     licensed assets checked into the repo; empty today.
  2. Wikimedia lookup (`app/services/wikimedia_vehicle_images.py`) —
     exact-title match with redirect following, downloaded once,
     validated, and stored under `settings.vehicle_image_dir`, then
     served from this application's own `/vehicle-images/` route. The
     frontend never hotlinks a third-party image host.
  3. a neutral, category-correct illustration (local SVG) — the
     deliberate placeholder when nothing better resolves.

Successful resolutions are cached in `vehicle_reference_images` keyed by
make+model+category (year and trim deliberately excluded — the
representative image is a property of the model line, and keying on year
was one of the original display bugs). A cached *fallback* row is not
final: while remote lookup is enabled, it is retried on a bounded
in-process schedule and upgraded in place when a real image resolves —
so one offline moment never permanently pins a vehicle to the generic
illustration.

A cached *real* (non-fallback) row is not unconditionally final either:
its `image_url` only stays trustworthy as long as the file it points to
is still sitting under `settings.vehicle_image_dir`. On a host whose
filesystem doesn't survive a restart/redeploy (e.g. Render's default
ephemeral disk), that file can vanish while the DB row survives, and the
row would otherwise keep pointing every future request at a permanent
404. So a cache hit whose backing file is missing on *this* process's
disk is treated exactly like a cached fallback: retried on the same
bounded schedule and repaired (or, if the retry itself can't resolve a
real image, downgraded to the neutral illustration) rather than served
as a known-dead URL forever. See `_local_file_missing`.

`match_confidence` always reflects which tier actually matched — a
weak/no match is never presented as a confident one.
"""

from __future__ import annotations

import hashlib
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import NamedTuple, Optional

from app.config import get_settings
from app.db.vehicle_reference_repository import VehicleReferenceImageRepository
from app.services.wikimedia_vehicle_images import resolve_remote_vehicle_image

# Static, locally-hosted flat-line illustrations (frontend/public/vehicle-reference/)
# — drawn for this project, not scraped or hotlinked from anywhere.
CATEGORY_FALLBACK_IMAGES: dict[str, str] = {
    "Hatchback": "/vehicle-reference/hatchback.svg",
    "Sedan": "/vehicle-reference/sedan.svg",
    "SUV": "/vehicle-reference/suv.svg",
    "Luxury Car": "/vehicle-reference/luxury-car.svg",
    "Bus": "/vehicle-reference/bus.svg",
    "Truck": "/vehicle-reference/truck.svg",
    "Commercial Vehicle": "/vehicle-reference/commercial-vehicle.svg",
}

# Checked before every other tier. Key: "{make} {model}".lower().strip().
# Populate with real, licensed per-model assets to pin a specific image
# without touching any other part of this pipeline.
CURATED_VEHICLE_IMAGES: dict[str, str] = {}

DEFAULT_CATEGORY_IMAGE = CATEGORY_FALLBACK_IMAGES["Sedan"]

# URL prefix served by app/api/routes/vehicle_images.py from
# settings.vehicle_image_dir — the stable, application-controlled URL
# every remotely-resolved image is exposed under.
VEHICLE_IMAGE_URL_PREFIX = "/vehicle-images"

FALLBACK_SOURCE = "category_fallback"

# A cached category-fallback row is retried (and upgraded in place) at
# most this often per process — frequent enough to self-heal after an
# offline start, rare enough never to hammer Wikimedia from a dashboard.
REMOTE_RETRY_INTERVAL_SECONDS = 30 * 60
_remote_retry_not_before: dict[str, float] = {}


class ReferenceImageResult(NamedTuple):
    image_url: str
    source: str
    match_confidence: float


class VehicleImageProvider(ABC):
    @abstractmethod
    async def resolve(
        self,
        *,
        make: str,
        model: str,
        year: Optional[int],
        vehicle_type: str,
        variant: Optional[str] = None,
    ) -> ReferenceImageResult: ...


def _category_fallback(vehicle_type: str) -> ReferenceImageResult:
    fallback_image = CATEGORY_FALLBACK_IMAGES.get(vehicle_type, DEFAULT_CATEGORY_IMAGE)
    return ReferenceImageResult(image_url=fallback_image, source=FALLBACK_SOURCE, match_confidence=0.3)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def store_vehicle_image(content: bytes, extension: str, *, make: str, model: str) -> str:
    """Persists validated image bytes under settings.vehicle_image_dir and
    returns the stable application URL. Content-addressed filename: the
    same bytes always land on the same file, so re-resolution after a
    cache wipe never duplicates storage."""
    settings = get_settings()
    directory = Path(settings.vehicle_image_dir)
    directory.mkdir(parents=True, exist_ok=True)

    digest = hashlib.sha256(content).hexdigest()[:12]
    filename = f"{_slug(f'{make} {model}')}-{digest}.{extension}"
    path = directory / filename
    if not path.exists():
        path.write_bytes(content)
    return f"{VEHICLE_IMAGE_URL_PREFIX}/{filename}"


class DefaultVehicleImageProvider(VehicleImageProvider):
    """Curated catalog -> Wikimedia -> category illustration."""

    async def resolve(
        self,
        *,
        make: str,
        model: str,
        year: Optional[int],
        vehicle_type: str,
        variant: Optional[str] = None,
    ) -> ReferenceImageResult:
        curated = CURATED_VEHICLE_IMAGES.get(f"{make} {model}".strip().lower())
        if curated:
            return ReferenceImageResult(image_url=curated, source="curated_catalog", match_confidence=0.9)

        if get_settings().vehicle_image_remote_lookup_enabled:
            # Year and category don't widen the cache key (the image is
            # a property of the model line) but they do steer *which*
            # article/generation resolves on first lookup — see
            # wikimedia_vehicle_images.py.
            remote = await resolve_remote_vehicle_image(
                make, model, year=year, vehicle_type=vehicle_type
            )
            if remote is not None:
                url = store_vehicle_image(remote.content, remote.extension, make=make, model=model)
                # A real photo of this model line, matched by exact
                # article title — confident, but still generic (not the
                # claimant's own vehicle, and not year/trim exact).
                return ReferenceImageResult(image_url=url, source="wikimedia", match_confidence=0.75)

        return _category_fallback(vehicle_type)


def get_default_provider() -> VehicleImageProvider:
    return DefaultVehicleImageProvider()


def normalize_query(*, make: str, model: str, vehicle_type: str) -> str:
    """Cache key: make + model + category only. Year and variant are
    deliberately excluded — including them meant every year/trim of the
    same model missed the cache and could resolve differently."""
    return f"{make.strip().lower()}|{model.strip().lower()}|{vehicle_type.strip().lower()}"


def _remote_retry_allowed(query: str) -> bool:
    return time.monotonic() >= _remote_retry_not_before.get(query, 0.0)


def _defer_remote_retry(query: str) -> None:
    _remote_retry_not_before[query] = time.monotonic() + REMOTE_RETRY_INTERVAL_SECONDS


def _local_file_missing(image_url: str) -> bool:
    """True when `image_url` is one this application serves from its own
    disk (`app/api/routes/vehicle_images.py`, rooted at
    `settings.vehicle_image_dir`) and the backing file is not there right
    now. Frontend-served category SVGs and any future non-local curated
    asset never depend on this process's disk and are trusted as-is."""
    prefix = f"{VEHICLE_IMAGE_URL_PREFIX}/"
    if not image_url.startswith(prefix):
        return False
    filename = image_url[len(prefix) :]
    return not (Path(get_settings().vehicle_image_dir) / filename).is_file()


async def resolve_vehicle_reference_image(
    repo: VehicleReferenceImageRepository,
    *,
    make: str,
    model: str,
    year: Optional[int] = None,
    vehicle_type: str,
    variant: Optional[str] = None,
    provider: Optional[VehicleImageProvider] = None,
):
    """Cache-or-compute: the same (make, model, vehicle_type) always
    resolves to the same cached row after the first successful call.
    Cached fallback rows are upgraded in place when a later remote
    lookup succeeds (bounded by REMOTE_RETRY_INTERVAL_SECONDS)."""

    query = normalize_query(make=make, model=model, vehicle_type=vehicle_type)
    active_provider = provider or get_default_provider()

    cached = await repo.get_by_normalized_query(query)
    if cached is not None:
        # A "real" cache hit is only trustworthy while its file is still
        # on this process's disk — see the module docstring and
        # _local_file_missing.
        stale = cached.source != FALLBACK_SOURCE and _local_file_missing(cached.image_url)
        if not stale and (cached.source != FALLBACK_SOURCE or not _remote_retry_allowed(query)):
            return cached
        if stale and not _remote_retry_allowed(query):
            return cached
        # Either a cached fallback with the retry window open, or a
        # previously-real resolution whose backing file is gone (e.g. an
        # ephemeral filesystem wiped by a platform restart) — one more
        # attempt to resolve a real image, repairing the row on success.
        result = await active_provider.resolve(
            make=make, model=model, year=year, vehicle_type=vehicle_type, variant=variant
        )
        if result.source == FALLBACK_SOURCE:
            _defer_remote_retry(query)
            if not stale:
                return cached
            # The row was pointing at a file we know is gone — never
            # keep serving that dead URL; downgrade it to the same
            # neutral illustration a first-time miss would get.
        return await repo.update_resolution(
            cached, image_url=result.image_url, source=result.source, match_confidence=result.match_confidence
        )

    result = await active_provider.resolve(
        make=make, model=model, year=year, vehicle_type=vehicle_type, variant=variant
    )
    if result.source == FALLBACK_SOURCE:
        # Cache the fallback (dashboards must not re-run lookups per
        # render) but keep it upgrade-eligible on the retry schedule.
        _defer_remote_retry(query)
    return await repo.create(
        normalized_query=query,
        image_url=result.image_url,
        source=result.source,
        match_confidence=result.match_confidence,
    )
