"""India passenger-vehicle catalog: manufacturers -> models -> optional
variants, used to back the frontend's dependent make/model selectors
(Tasks 4/5/8).

Deterministic and versioned by design — the data lives in
`app/data/vehicle_catalog/catalog.json`, a static file checked into the
repo, never generated at runtime or via an LLM call. Updating the catalog
means editing that file (and bumping `version`), not touching this
module. Loaded once and cached in memory: catalog data changes
infrequently and this avoids re-parsing the JSON file on every request.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources

from pydantic import BaseModel


class VehicleModel(BaseModel):
    id: str
    name: str
    category: str
    status: str  # "active" | "discontinued"
    aliases: list[str] = []
    variants: list[str] = []


class VehicleManufacturer(BaseModel):
    id: str
    name: str
    status: str  # "active" | "historical"


class VehicleManufacturerDetail(VehicleManufacturer):
    models: list[VehicleModel]


class CatalogNotFoundError(Exception):
    """Raised for an unknown manufacturer or model id."""


@lru_cache
def _load_catalog() -> dict:
    raw = resources.files("app.data.vehicle_catalog").joinpath("catalog.json").read_text(encoding="utf-8")
    return json.loads(raw)


@lru_cache
def _manufacturers_by_id() -> dict[str, dict]:
    return {mf["id"]: mf for mf in _load_catalog()["manufacturers"]}


def list_manufacturers() -> list[VehicleManufacturer]:
    return [
        VehicleManufacturer(id=mf["id"], name=mf["name"], status=mf["status"])
        for mf in _load_catalog()["manufacturers"]
    ]


def get_manufacturer(manufacturer_id: str) -> VehicleManufacturerDetail:
    mf = _manufacturers_by_id().get(manufacturer_id)
    if mf is None:
        raise CatalogNotFoundError(manufacturer_id)
    return VehicleManufacturerDetail(
        id=mf["id"],
        name=mf["name"],
        status=mf["status"],
        models=[VehicleModel.model_validate(mdl) for mdl in mf["models"]],
    )


def list_models(manufacturer_id: str) -> list[VehicleModel]:
    return get_manufacturer(manufacturer_id).models


def get_model(manufacturer_id: str, model_id: str) -> VehicleModel:
    for model in list_models(manufacturer_id):
        if model.id == model_id:
            return model
    raise CatalogNotFoundError(model_id)
