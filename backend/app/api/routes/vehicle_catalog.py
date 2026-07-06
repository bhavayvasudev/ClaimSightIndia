"""India vehicle-catalog endpoints (Tasks 4/5/8) — manufacturers, their
models, and optional model variants. Public reference data: no
authentication required (nothing here is user- or claim-specific), and
responses carry a long-lived cache header since the catalog only changes
when the static JSON file it's built from is updated and redeployed.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from app.services.vehicle_catalog import (
    CatalogNotFoundError,
    VehicleManufacturer,
    VehicleModel,
    get_model,
    list_manufacturers,
    list_models,
)

router = APIRouter(prefix="/vehicle-catalog", tags=["vehicle-catalog"])

# Catalog data is static per deploy — safe for a browser/CDN to cache for
# a day and revalidate, without needing a version bump for every request.
_CACHE_CONTROL = "public, max-age=86400"


@router.get("/manufacturers", response_model=list[VehicleManufacturer])
async def get_manufacturers(response: Response) -> list[VehicleManufacturer]:
    response.headers["Cache-Control"] = _CACHE_CONTROL
    return list_manufacturers()


@router.get("/manufacturers/{manufacturer_id}/models", response_model=list[VehicleModel])
async def get_manufacturer_models(manufacturer_id: str, response: Response) -> list[VehicleModel]:
    try:
        models = list_models(manufacturer_id)
    except CatalogNotFoundError:
        raise HTTPException(status_code=404, detail="Unknown manufacturer.")
    response.headers["Cache-Control"] = _CACHE_CONTROL
    return models


@router.get("/manufacturers/{manufacturer_id}/models/{model_id}/variants", response_model=list[str])
async def get_model_variants(manufacturer_id: str, model_id: str, response: Response) -> list[str]:
    try:
        model = get_model(manufacturer_id, model_id)
    except CatalogNotFoundError:
        raise HTTPException(status_code=404, detail="Unknown manufacturer or model.")
    response.headers["Cache-Control"] = _CACHE_CONTROL
    return model.variants
