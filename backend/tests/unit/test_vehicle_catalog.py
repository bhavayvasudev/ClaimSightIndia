"""Unit tests for the India vehicle catalog service
(`app/services/vehicle_catalog.py`, Tasks 4/5/8)."""

from __future__ import annotations

import pytest

from app.services.vehicle_catalog import (
    CatalogNotFoundError,
    get_manufacturer,
    get_model,
    list_manufacturers,
    list_models,
)

VALID_CATEGORIES = {"Hatchback", "Sedan", "SUV", "Luxury Car", "Bus", "Truck", "Commercial Vehicle"}


def test_list_manufacturers_returns_active_and_historical():
    manufacturers = list_manufacturers()
    statuses = {mf.status for mf in manufacturers}
    assert "active" in statuses
    assert "historical" in statuses
    assert len(manufacturers) > 30


def test_no_duplicate_manufacturer_ids():
    manufacturers = list_manufacturers()
    ids = [mf.id for mf in manufacturers]
    assert len(ids) == len(set(ids))


def test_manufacturer_model_lookup_returns_current_and_discontinued():
    models = list_models("maruti-suzuki")
    statuses = {mdl.status for mdl in models}
    assert "active" in statuses
    assert "discontinued" in statuses
    assert len(models) > 5


def test_no_duplicate_model_ids_within_any_manufacturer():
    for mf in list_manufacturers():
        model_ids = [mdl.id for mdl in list_models(mf.id)]
        assert len(model_ids) == len(set(model_ids)), f"duplicate model id under {mf.id}"


def test_every_model_has_a_known_category():
    for mf in list_manufacturers():
        for mdl in list_models(mf.id):
            assert mdl.category in VALID_CATEGORIES, f"{mf.id}/{mdl.id} has unknown category {mdl.category}"


def test_invalid_manufacturer_raises_not_found():
    with pytest.raises(CatalogNotFoundError):
        list_models("not-a-real-manufacturer")


def test_invalid_model_raises_not_found():
    with pytest.raises(CatalogNotFoundError):
        get_model("maruti-suzuki", "not-a-real-model")


def test_historical_manufacturer_still_has_selectable_models():
    ford = get_manufacturer("ford")
    assert ford.status == "historical"
    assert any(mdl.name == "EcoSport" for mdl in ford.models)


def test_representative_current_and_discontinued_entries_present():
    astor = get_model("mg-motor", "astor")
    assert astor.status == "active"
    assert "Blackstorm" in astor.variants

    xuv500 = get_model("mahindra", "xuv500")
    assert xuv500.status == "discontinued"
