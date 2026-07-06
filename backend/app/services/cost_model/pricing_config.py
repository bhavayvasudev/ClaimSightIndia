"""
MVP heuristic pricing configuration for ClaimSight India.

THIS IS NOT REAL PRICING DATA. `PART_GROUP_BASE_RANGES` and
`CATEGORY_MULTIPLIERS` exist to prove the pricing architecture varies
correctly by vehicle category, part, and recommended action — replace both
with real workshop/insurer/OEM pricing data before this is used for
anything beyond a demo. See docs/decision_log.md.

Nothing outside `services/cost_model/` should import from this module
directly — go through `pricing_service.estimate_cost` so the config
structure can change without breaking callers.
"""

from __future__ import annotations

from typing import NamedTuple


class CostRange(NamedTuple):
    min_inr: int
    max_inr: int


# Base ranges assume a Sedan (multiplier 1.0 below). Keyed by
# (part_group, recommended_action). Mirrors ai-service/pipeline.py's
# get_cost_estimate part groupings 1:1 so both services reason about the
# same part taxonomy — see resolve_part_group.
PART_GROUP_BASE_RANGES: dict[str, dict[str, CostRange]] = {
    "headlight": {
        "Repair": CostRange(1500, 4000),
        "Replace": CostRange(5000, 25000),
    },
    "rear_light": {
        "Repair": CostRange(1000, 3000),
        "Replace": CostRange(3000, 15000),
    },
    "bumper": {
        "Repair": CostRange(2500, 7000),
        "Replace": CostRange(7000, 20000),
    },
    "hood": {
        "Repair": CostRange(3000, 7000),
        "Repair + Repaint": CostRange(6000, 12000),
        "Replace / Major Repair": CostRange(12000, 30000),
    },
    "door": {
        "Repair": CostRange(2500, 6000),
        "Repair + Repaint": CostRange(5000, 10000),
        "Replace / Major Repair": CostRange(10000, 30000),
    },
    "fender": {
        "Repair": CostRange(2000, 5000),
        "Repair + Repaint": CostRange(4000, 8000),
        "Replace / Major Repair": CostRange(7000, 18000),
    },
    "boot": {
        "Repair": CostRange(3000, 7000),
        "Repair + Repaint": CostRange(6000, 12000),
        "Replace / Major Repair": CostRange(12000, 30000),
    },
    "generic": {
        "Repair": CostRange(2000, 6000),
        "Repair + Repaint": CostRange(5000, 12000),
        "Replace": CostRange(10000, 30000),
        "Replace / Major Repair": CostRange(10000, 30000),
    },
}


# Multiplier applied to the Sedan-baseline ranges above. Passenger
# categories scale on part size/labour cost; Bus/Truck/Commercial Vehicle
# get their own higher band for larger panels, larger lighting assemblies,
# and commercial labour rates — not derived from any real cost study yet.
CATEGORY_MULTIPLIERS: dict[str, float] = {
    "Hatchback": 0.85,
    "Sedan": 1.0,
    "SUV": 1.35,
    "Luxury Car": 2.5,
    "Bus": 2.0,
    "Truck": 2.2,
    "Commercial Vehicle": 1.8,
}


def resolve_part_group(part_name: str) -> str:
    """Same keyword grouping as ai-service/pipeline.py:get_cost_estimate.
    Kept in sync by hand since the two services currently duplicate this
    logic on purpose — AI vision inference and pricing business logic stay
    in separate services (see docs/decision_log.md)."""

    name = part_name.lower()

    if "headlight" in name:
        return "headlight"

    if "rear light" in name or "tail light" in name:
        return "rear_light"

    if "bumper" in name:
        return "bumper"

    if "hood" in name or "bonnet" in name:
        return "hood"

    if "door" in name:
        return "door"

    if "fender" in name:
        return "fender"

    if "boot" in name:
        return "boot"

    return "generic"
