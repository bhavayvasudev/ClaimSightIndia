"""Tests for the MVP category-aware pricing service. These pin two
behaviors that must never regress: pricing varies by vehicle category, and
Manual Inspection / Review Required parts never receive a confident cost."""

from app.schemas.claim_state import PartAssessmentStatus, PartDamageAssessment, PartSeverity
from app.services.cost_model import estimate_cost, summarize_claim_costs


def _part(
    part="Front bumper",
    severity=PartSeverity.MODERATE,
    status=PartAssessmentStatus.ACCEPTED,
    recommended_action="Repair",
    damage_percentage=20.0,
    damage_confidence=0.5,
    part_confidence=0.8,
) -> PartDamageAssessment:
    return PartDamageAssessment(
        part=part,
        severity=severity,
        damage_percentage=damage_percentage,
        damage_confidence=damage_confidence,
        part_confidence=part_confidence,
        status=status,
        recommended_action=recommended_action,
    )


def test_estimate_cost_returns_none_for_manual_inspection():
    estimate = estimate_cost(
        vehicle_type="SUV",
        part_name="Headlight - (R)",
        severity="Uncertain",
        recommended_action="Manual Inspection",
    )
    assert estimate is None


def test_estimate_cost_varies_by_vehicle_category():
    ranges = {
        category: estimate_cost(
            vehicle_type=category,
            part_name="Front bumper",
            severity="Moderate",
            recommended_action="Repair",
        )
        for category in ["Hatchback", "Sedan", "SUV", "Luxury Car"]
    }

    # Strictly increasing min and max as the category scales up.
    ordered = [ranges["Hatchback"], ranges["Sedan"], ranges["SUV"], ranges["Luxury Car"]]
    for cheaper, pricier in zip(ordered, ordered[1:]):
        assert cheaper.min_inr < pricier.min_inr
        assert cheaper.max_inr < pricier.max_inr

    assert ranges["Sedan"].min_inr == 2500
    assert ranges["Sedan"].max_inr == 7000


def test_estimate_cost_commercial_categories_priced_above_passenger_baseline():
    sedan = estimate_cost(
        vehicle_type="Sedan", part_name="Car hood", severity="Severe",
        recommended_action="Replace / Major Repair",
    )
    for category in ["Bus", "Truck", "Commercial Vehicle"]:
        commercial = estimate_cost(
            vehicle_type=category, part_name="Car hood", severity="Severe",
            recommended_action="Replace / Major Repair",
        )
        assert commercial.min_inr > sedan.min_inr
        assert commercial.max_inr > sedan.max_inr


def test_estimate_cost_rejects_unknown_vehicle_type():
    try:
        estimate_cost(
            vehicle_type="Spaceship",
            part_name="Front bumper",
            severity="Moderate",
            recommended_action="Repair",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for unknown vehicle_type")


def test_estimate_cost_range_is_never_inverted():
    for category in ["Hatchback", "Sedan", "SUV", "Luxury Car", "Bus", "Truck", "Commercial Vehicle"]:
        estimate = estimate_cost(
            vehicle_type=category, part_name="Car hood", severity="Severe",
            recommended_action="Replace / Major Repair",
        )
        assert estimate.min_inr <= estimate.max_inr


def test_summarize_claim_costs_excludes_review_required_parts_from_totals():
    parts = [
        _part(part="Car hood", recommended_action="Replace / Major Repair", severity=PartSeverity.SEVERE),
        _part(
            part="Headlight - (R)",
            status=PartAssessmentStatus.REVIEW_REQUIRED,
            recommended_action="Manual Inspection",
            severity=PartSeverity.UNCERTAIN,
        ),
    ]

    summary = summarize_claim_costs(vehicle_type="Sedan", damaged_parts=parts)

    assert summary.parts_priced == 1
    assert summary.parts_pending_manual_inspection == 1
    assert summary.per_part["Headlight - (R)"] is None
    assert summary.per_part["Car hood"] is not None
    assert summary.total_min_inr == summary.per_part["Car hood"].min_inr
    assert summary.total_max_inr == summary.per_part["Car hood"].max_inr


def test_summarize_claim_costs_all_manual_inspection_yields_zero_totals():
    parts = [
        _part(
            part="Front bumper",
            status=PartAssessmentStatus.REVIEW_REQUIRED,
            recommended_action="Manual Inspection",
            severity=PartSeverity.UNCERTAIN,
        ),
    ]

    summary = summarize_claim_costs(vehicle_type="SUV", damaged_parts=parts)

    assert summary.parts_priced == 0
    assert summary.parts_pending_manual_inspection == 1
    assert summary.total_min_inr == 0
    assert summary.total_max_inr == 0
    assert summary.display_range == "Pending manual inspection"


def test_summarize_claim_costs_status_overrides_action_as_a_safety_net():
    # A malformed part with status Review Required but a non-manual action
    # must still be priced as None — the belt-and-suspenders check in
    # summarize_claim_costs, independent of estimate_cost's own guard.
    parts = [
        _part(status=PartAssessmentStatus.REVIEW_REQUIRED, recommended_action="Repair"),
    ]

    summary = summarize_claim_costs(vehicle_type="Sedan", damaged_parts=parts)

    assert summary.per_part["Front bumper"] is None
    assert summary.parts_pending_manual_inspection == 1
