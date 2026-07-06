"""Smoke tests for the shared ClaimState schema — not agent logic tests.
These exist to pin the contract every agent node relies on."""

from datetime import date

from app.schemas.claim_state import (
    ClaimIntakeInput,
    ClaimState,
    ClaimStatus,
    FraudAssessment,
    FraudRisk,
    PartAssessmentStatus,
    PartCostEstimate,
    PartDamageAssessment,
    PartSeverity,
    PolicyDetails,
    SeverityLevel,
    VehicleCategory,
    VehicleDetails,
    VisionAssessment,
    format_inr,
)


def _intake() -> ClaimIntakeInput:
    return ClaimIntakeInput(
        vehicle_image_id="img_plate_1",
        damage_image_ids=["img_dmg_1", "img_dmg_2"],
        policy_pdf_id="pdf_policy_1",
        incident_description="Rear-ended at a signal, windshield cracked.",
        incident_date=date(2026, 6, 20),
        incident_location="Bengaluru, Karnataka",
        vehicle_type=VehicleCategory.SEDAN,
        vehicle_make="Hyundai",
        vehicle_model="Verna",
        vehicle_year=2021,
    )


def test_new_claim_state_defaults_to_intake_status():
    state = ClaimState.new(_intake())
    assert state.status == ClaimStatus.INTAKE
    assert state.claim_id.startswith("CLM-")
    assert state.vehicle is None
    assert state.needs_human_review is False


def test_registration_number_normalizes_and_derives_state():
    v = VehicleDetails(registration_number="mh 12 ab 1234", vehicle_make="Hyundai")
    assert v.registration_number == "MH12AB1234"
    assert v.state == "Maharashtra"


def _part(
    part: str,
    severity: PartSeverity,
    status: PartAssessmentStatus = PartAssessmentStatus.ACCEPTED,
) -> PartDamageAssessment:
    return PartDamageAssessment(
        part=part,
        severity=severity,
        damage_percentage=25.0,
        damage_confidence=0.5,
        part_confidence=0.8,
        status=status,
        recommended_action="Repair",
    )


def test_vision_assessment_derives_overall_severity_from_worst_accepted_part():
    vision = VisionAssessment(
        damaged_parts=[
            _part("Front bumper", PartSeverity.MINOR),
            _part("Car hood", PartSeverity.SEVERE),
        ]
    )
    assert vision.overall_severity == SeverityLevel.SEVERE


def test_vision_assessment_ignores_review_required_parts_for_overall_severity():
    # A Review Required/Uncertain part must never drive a confident
    # claim-wide severity, even if its raw damage_percentage looks large.
    vision = VisionAssessment(
        damaged_parts=[
            _part("Headlight - (R)", PartSeverity.UNCERTAIN, PartAssessmentStatus.REVIEW_REQUIRED),
        ]
    )
    assert vision.overall_severity is None


def test_part_damage_assessment_has_no_pricing_field():
    # Pins the ai-service/backend pricing boundary at the schema level:
    # the vision contract must never carry a cost field, even if a raw
    # ai-service payload (or an older client) still sends one — pricing
    # is computed downstream by services/cost_model, never accepted as
    # vision-supplied data.
    assert "estimated_cost" not in PartDamageAssessment.model_fields

    part = PartDamageAssessment.model_validate(
        {
            "part": "Front bumper",
            "severity": "Moderate",
            "damage_percentage": 20.0,
            "damage_confidence": 0.5,
            "part_confidence": 0.8,
            "status": "Accepted",
            "recommended_action": "Repair",
            "estimated_cost": {"min": 2500, "max": 7000, "currency": "INR"},
        }
    )
    assert not hasattr(part, "estimated_cost")


def test_part_cost_estimate_rejects_inverted_range():
    try:
        PartCostEstimate(min_inr=50_000, max_inr=30_000, vehicle_category="Sedan")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for max_inr < min_inr")


def test_format_inr_uses_indian_digit_grouping():
    assert format_inr(1234567) == "₹12,34,567"
    assert format_inr(999) == "₹999"


def test_needs_human_review_on_high_fraud_risk():
    state = ClaimState.new(_intake())
    state.fraud = FraudAssessment(fraud_risk=FraudRisk.HIGH, fraud_reasons=["Weather mismatch"])
    assert state.needs_human_review is True


def test_policy_details_display_helpers():
    policy = PolicyDetails(covered=True, deductible_inr=5000, idv_inr=850_000, zero_dep=True)
    assert policy.deductible_display == "₹5,000"
    assert policy.idv_display == "₹8,50,000"
