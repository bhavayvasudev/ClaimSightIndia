"""Smoke tests for the shared ClaimState schema — not agent logic tests.
These exist to pin the contract every agent node relies on."""

from datetime import date

from app.schemas.claim_state import (
    ClaimIntakeInput,
    ClaimState,
    ClaimStatus,
    CostEstimate,
    DamageDetection,
    DamageType,
    FraudAssessment,
    FraudRisk,
    PolicyDetails,
    SeverityLevel,
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


def test_vision_assessment_derives_overall_severity_from_worst_detection():
    vision = VisionAssessment(
        detections=[
            DamageDetection(damage_type=DamageType.SCRATCH, severity=SeverityLevel.MINOR),
            DamageDetection(
                damage_type=DamageType.BROKEN_WINDSHIELD, severity=SeverityLevel.SEVERE
            ),
        ]
    )
    assert vision.overall_severity == SeverityLevel.SEVERE


def test_cost_estimate_rejects_inverted_range():
    try:
        CostEstimate(low_inr=50_000, high_inr=30_000)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for high_inr < low_inr")


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
