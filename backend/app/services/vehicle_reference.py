"""Reference vehicle image resolution.

IMPORTANT — a reference image is a generic illustration of "what this kind
of vehicle looks like", resolved from make/model/year/category alone. It
is NOT claim evidence: never pass it to the ai-service, never mix it with
uploaded damage photos, never use it for severity estimation, and never
present it as the claimant's actual vehicle. Every API response that
carries one is labelled `vehicle_reference_image` for exactly this reason
— see `app/schemas/dashboard_api.py`.

No live external image search is wired up in this MVP: this environment
has no licensed image-API key or manufacturer media-asset feed configured,
and scraping/hotlinking arbitrary search results is explicitly out of
bounds. Wiring a real photo provider later is a matter of adding another
`VehicleImageProvider` implementation and switching `get_default_provider`
— nothing else in this pipeline (caching, the API shape, the dashboard)
needs to change.

`CatalogAndCategoryFallbackProvider` implements two of the five documented
resolution tiers today:
  1-4. a curated per-model catalog (`CURATED_VEHICLE_IMAGES`) — empty for
       now, ready to populate with real, licensed assets later.
  5.   a neutral, category-correct illustration — what every claim
       resolves to in practice right now.
It deliberately never fabricates an "exact match" for a generic
illustration: `match_confidence` always reflects which tier actually
matched, so a weak/no match never gets presented as a confident one.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import NamedTuple, Optional

from app.db.vehicle_reference_repository import VehicleReferenceImageRepository

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

# Checked before the category fallback (resolution tiers 1-4). Empty
# today — see module docstring. Key: "{make} {model}".lower().strip().
# Populate with real, licensed per-model assets to enable a confident
# curated match without touching any other part of this pipeline.
CURATED_VEHICLE_IMAGES: dict[str, str] = {}

DEFAULT_CATEGORY_IMAGE = CATEGORY_FALLBACK_IMAGES["Sedan"]


class ReferenceImageResult(NamedTuple):
    image_url: str
    source: str
    match_confidence: float


class VehicleImageProvider(ABC):
    @abstractmethod
    def resolve(
        self,
        *,
        make: str,
        model: str,
        year: Optional[int],
        vehicle_type: str,
        variant: Optional[str] = None,
    ) -> ReferenceImageResult: ...


class CatalogAndCategoryFallbackProvider(VehicleImageProvider):
    def resolve(
        self,
        *,
        make: str,
        model: str,
        year: Optional[int],
        vehicle_type: str,
        variant: Optional[str] = None,
    ) -> ReferenceImageResult:
        # Exact variant first, then the base make+model, then the
        # category-level illustration (Task 6) — CURATED_VEHICLE_IMAGES is
        # empty today (see module docstring) so this always falls through
        # to the category tier in practice, but the resolution order is
        # ready for real curated assets without touching any caller.
        candidate_keys = []
        if variant:
            candidate_keys.append(f"{make} {model} {variant}".strip().lower())
        candidate_keys.append(f"{make} {model}".strip().lower())

        for key in candidate_keys:
            curated = CURATED_VEHICLE_IMAGES.get(key)
            if curated:
                # A real curated/licensed asset for this exact match —
                # the only case allowed to claim a confident match.
                return ReferenceImageResult(image_url=curated, source="curated_catalog", match_confidence=0.9)

        # No curated entry: never guess a specific vehicle photo. Fall
        # back to a neutral, category-correct illustration at a modest
        # confidence — it depicts the vehicle's *category*, not this
        # specific make/model, and must never be confused with one.
        fallback_image = CATEGORY_FALLBACK_IMAGES.get(vehicle_type, DEFAULT_CATEGORY_IMAGE)
        return ReferenceImageResult(
            image_url=fallback_image, source="category_fallback", match_confidence=0.3
        )


def get_default_provider() -> VehicleImageProvider:
    return CatalogAndCategoryFallbackProvider()


def normalize_query(
    *, make: str, model: str, year: Optional[int], vehicle_type: str, variant: Optional[str] = None
) -> str:
    year_part = str(year) if year is not None else "unknown"
    variant_part = variant.strip().lower() if variant else "none"
    return (
        f"{make.strip().lower()}|{model.strip().lower()}|{variant_part}|"
        f"{year_part}|{vehicle_type.strip().lower()}"
    )


async def resolve_vehicle_reference_image(
    repo: VehicleReferenceImageRepository,
    *,
    make: str,
    model: str,
    year: Optional[int],
    vehicle_type: str,
    variant: Optional[str] = None,
    provider: Optional[VehicleImageProvider] = None,
):
    """Cache-or-compute: the same (make, model, variant, year, vehicle_type)
    always resolves to the same cached row after the first call — a
    dashboard render never re-runs provider resolution for a vehicle it
    has already resolved."""

    query = normalize_query(make=make, model=model, year=year, vehicle_type=vehicle_type, variant=variant)
    cached = await repo.get_by_normalized_query(query)
    if cached is not None:
        return cached

    result = (provider or get_default_provider()).resolve(
        make=make, model=model, year=year, vehicle_type=vehicle_type, variant=variant
    )
    return await repo.create(
        normalized_query=query,
        image_url=result.image_url,
        source=result.source,
        match_confidence=result.match_confidence,
    )
