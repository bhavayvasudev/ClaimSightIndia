"""Coverage analysis tests (Task 3): likely covered, unclear, potential
exclusion, and missing information."""

from __future__ import annotations

from app.schemas.policy_state import CoverageStatus, PolicyStructuredData, VehicleMatchStatus
from app.services.policy.coverage_analysis import analyze_coverage
from app.services.rag.embeddings import embed_text

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


class _Chunk:
    def __init__(self, id_, page, section, text):
        self.id = id_
        self.page_number = page
        self.section = section
        self.text = text
        self.embedding = embed_text(text)


def test_likely_covered_when_coverage_clause_retrieved():
    chunks = [
        _Chunk(1, 4, "Own Damage Coverage", "The policy provides own damage accidental damage coverage for the front bumper and other body parts under collision.")
    ]
    result = analyze_coverage(
        damaged_parts=[ACCEPTED_PART],
        vehicle_type="Sedan",
        vehicle_make="Hyundai",
        vehicle_model="Verna",
        structured=PolicyStructuredData(vehicle_make="Hyundai", vehicle_model="Verna"),
        chunks=chunks,
    )
    assert result.overall_status == CoverageStatus.LIKELY_COVERED
    assert result.part_assessments[0].coverage_status == CoverageStatus.LIKELY_COVERED
    assert result.vehicle_match == VehicleMatchStatus.MATCH


def test_potential_exclusion_when_exclusion_clause_retrieved():
    chunks = [
        _Chunk(
            1, 6, "Exclusions",
            "Damage to the front bumper caused by racing is excluded and not covered under this policy.",
        )
    ]
    result = analyze_coverage(
        damaged_parts=[ACCEPTED_PART],
        vehicle_type="Sedan",
        vehicle_make="Hyundai",
        vehicle_model="Verna",
        structured=PolicyStructuredData(),
        chunks=chunks,
    )
    assert result.overall_status == CoverageStatus.POTENTIAL_EXCLUSION
    assert result.part_assessments[0].coverage_status == CoverageStatus.POTENTIAL_EXCLUSION


def test_unclear_when_retrieved_clause_is_ambiguous():
    chunks = [
        _Chunk(1, 2, "Definitions", "Front bumper means the forward-most panel of the vehicle body.")
    ]
    result = analyze_coverage(
        damaged_parts=[ACCEPTED_PART],
        vehicle_type="Sedan",
        vehicle_make=None,
        vehicle_model=None,
        structured=PolicyStructuredData(),
        chunks=chunks,
    )
    assert result.overall_status == CoverageStatus.UNCLEAR


def test_manual_review_when_no_relevant_clause_found():
    chunks = [_Chunk(1, 1, "Contact", "Call our helpline for roadside assistance any time.")]
    result = analyze_coverage(
        damaged_parts=[ACCEPTED_PART],
        vehicle_type="Sedan",
        vehicle_make=None,
        vehicle_model=None,
        structured=PolicyStructuredData(),
        chunks=chunks,
    )
    assert result.overall_status == CoverageStatus.MANUAL_REVIEW
    assert result.part_assessments[0].relevant_clauses == []


def test_missing_information_no_chunks_and_no_accepted_parts():
    result = analyze_coverage(
        damaged_parts=[],
        vehicle_type="Sedan",
        vehicle_make=None,
        vehicle_model=None,
        structured=PolicyStructuredData(),
        chunks=[],
    )
    assert result.overall_status == CoverageStatus.MANUAL_REVIEW
    assert result.part_assessments == []


def test_vehicle_mismatch_flagged_as_warning():
    chunks = [_Chunk(1, 4, "Own Damage Coverage", "own damage accidental damage coverage applies")]
    result = analyze_coverage(
        damaged_parts=[ACCEPTED_PART],
        vehicle_type="Sedan",
        vehicle_make="Hyundai",
        vehicle_model="Verna",
        structured=PolicyStructuredData(vehicle_make="Maruti", vehicle_model="Swift"),
        chunks=chunks,
    )
    assert result.vehicle_match == VehicleMatchStatus.MISMATCH
    assert any("policy document" in w for w in result.warnings)


def test_review_required_parts_are_excluded_from_coverage_findings():
    review_required_part = dict(ACCEPTED_PART, status="Review Required")
    result = analyze_coverage(
        damaged_parts=[review_required_part],
        vehicle_type="Sedan",
        vehicle_make=None,
        vehicle_model=None,
        structured=PolicyStructuredData(),
        chunks=[_Chunk(1, 1, None, "own damage accidental damage coverage")],
    )
    assert result.part_assessments == []
    assert result.overall_status == CoverageStatus.MANUAL_REVIEW
