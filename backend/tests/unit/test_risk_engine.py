"""Risk Signal Engine tests (Task 4): no signals, vehicle mismatch, policy
date mismatch when valid dates exist, duplicate exact image, and
insufficient data."""

from __future__ import annotations

from datetime import date

from app.schemas.policy_state import PolicyStructuredData, RiskLevel, RiskSignalCode
from app.services.risk.risk_engine import assess_risk

ACCEPTED_PART = {
    "part": "Front bumper",
    "severity": "Moderate",
    "damage_percentage": 20.0,
    "damage_confidence": 0.8,
    "part_confidence": 0.9,
    "status": "Accepted",
    "recommended_action": "Repair",
    "detected_in_images": ["front.jpg"],
    "observation_count": 1,
    "max_damage_confidence_seen": 0.8,
    "max_part_confidence_seen": 0.9,
}


def test_insufficient_data_when_no_damage_assessment():
    result = assess_risk(
        vehicle_make="Hyundai",
        vehicle_model="Verna",
        vehicle_year=2021,
        incident_date=None,
        damaged_parts=[],
        image_hashes=None,
        structured=None,
    )
    assert result.risk_level == RiskLevel.INSUFFICIENT_DATA
    assert result.signals == []


def test_no_signals_is_low_risk():
    result = assess_risk(
        vehicle_make="Hyundai",
        vehicle_model="Verna",
        vehicle_year=2021,
        incident_date=None,
        damaged_parts=[ACCEPTED_PART],
        image_hashes=["abc123"],
        structured=None,
    )
    assert result.risk_level == RiskLevel.LOW
    assert result.signals == []


def test_vehicle_model_mismatch_signal():
    result = assess_risk(
        vehicle_make="Hyundai",
        vehicle_model="Verna",
        vehicle_year=2021,
        incident_date=None,
        damaged_parts=[ACCEPTED_PART],
        image_hashes=None,
        structured=PolicyStructuredData(vehicle_make="Maruti", vehicle_model="Swift"),
    )
    assert result.risk_level == RiskLevel.MEDIUM
    codes = [s.code for s in result.signals]
    assert RiskSignalCode.VEHICLE_MODEL_MISMATCH in codes


def test_policy_date_inconsistency_when_incident_outside_coverage_period():
    result = assess_risk(
        vehicle_make="Hyundai",
        vehicle_model="Verna",
        vehicle_year=2021,
        incident_date=date(2027, 1, 1),
        damaged_parts=[ACCEPTED_PART],
        image_hashes=None,
        structured=PolicyStructuredData(
            coverage_start=date(2026, 1, 1), coverage_end=date(2026, 12, 31)
        ),
    )
    assert result.risk_level == RiskLevel.HIGH
    codes = [s.code for s in result.signals]
    assert RiskSignalCode.POLICY_DATE_INCONSISTENCY in codes


def test_policy_date_check_skipped_when_no_incident_date():
    # No incident date collected -> the check must never be invented.
    result = assess_risk(
        vehicle_make="Hyundai",
        vehicle_model="Verna",
        vehicle_year=2021,
        incident_date=None,
        damaged_parts=[ACCEPTED_PART],
        image_hashes=None,
        structured=PolicyStructuredData(
            coverage_start=date(2020, 1, 1), coverage_end=date(2020, 12, 31)
        ),
    )
    codes = [s.code for s in result.signals]
    assert RiskSignalCode.POLICY_DATE_INCONSISTENCY not in codes


def test_duplicate_exact_image_signal():
    result = assess_risk(
        vehicle_make="Hyundai",
        vehicle_model="Verna",
        vehicle_year=2021,
        incident_date=None,
        damaged_parts=[ACCEPTED_PART],
        image_hashes=["hash-a", "hash-b", "hash-a"],
        structured=None,
    )
    assert result.risk_level == RiskLevel.MEDIUM
    codes = [s.code for s in result.signals]
    assert RiskSignalCode.DUPLICATE_IMAGE_DETECTED in codes


def test_no_duplicate_when_all_hashes_distinct():
    result = assess_risk(
        vehicle_make="Hyundai",
        vehicle_model="Verna",
        vehicle_year=2021,
        incident_date=None,
        damaged_parts=[ACCEPTED_PART],
        image_hashes=["hash-a", "hash-b"],
        structured=None,
    )
    codes = [s.code for s in result.signals]
    assert RiskSignalCode.DUPLICATE_IMAGE_DETECTED not in codes


def test_inconsistent_visual_assessment_signal():
    inconsistent_part = dict(
        ACCEPTED_PART,
        observation_count=3,
        damage_confidence=0.2,
        max_damage_confidence_seen=0.9,
    )
    result = assess_risk(
        vehicle_make="Hyundai",
        vehicle_model="Verna",
        vehicle_year=2021,
        incident_date=None,
        damaged_parts=[inconsistent_part],
        image_hashes=None,
        structured=None,
    )
    codes = [s.code for s in result.signals]
    assert RiskSignalCode.INCONSISTENT_VISUAL_ASSESSMENT in codes


def test_high_severity_signal_dominates_risk_level():
    result = assess_risk(
        vehicle_make="Hyundai",
        vehicle_model="Verna",
        vehicle_year=2021,
        incident_date=date(2027, 6, 1),
        damaged_parts=[ACCEPTED_PART],
        image_hashes=["a", "a"],
        structured=PolicyStructuredData(
            vehicle_make="Maruti",
            coverage_start=date(2026, 1, 1),
            coverage_end=date(2026, 12, 31),
        ),
    )
    assert result.risk_level == RiskLevel.HIGH
    assert len(result.signals) >= 2
