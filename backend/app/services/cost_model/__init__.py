"""
Cost estimation service — vehicle-category-aware, heuristic-driven for MVP.

Public interface:
    estimate_cost(vehicle_type, part_name, severity, recommended_action)
        -> PartCostEstimate | None
    summarize_claim_costs(vehicle_type, damaged_parts) -> ClaimCostSummary

See `pricing_config.py` for the (explicitly MVP-heuristic) pricing tables
and `pricing_service.py` for the computation.
"""

from app.services.cost_model.pricing_service import estimate_cost, summarize_claim_costs

__all__ = ["estimate_cost", "summarize_claim_costs"]
