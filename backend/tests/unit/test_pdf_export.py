"""Unit tests for the PDF claim report (`app/services/report/pdf_export.py`)
— parity with the in-app report (claim status, per-part detail, insurer /
masked policy number / policy type / coverage period) and the negative
guarantees (no raw model confidence, no unmasked identifiers, unpriced
parts never rendered as zero-cost).
"""

from __future__ import annotations

import re
import zlib
from datetime import date

from app.schemas.policy_state import UnifiedClaimReport
from app.services.report.pdf_export import generate_claim_report_pdf

# A value that could never occur as a coincidental PDF drawing operator —
# if this appears in the rendered text, model confidence leaked.
SENTINEL_CONFIDENCE = 0.87654321


def _report() -> UnifiedClaimReport:
    return UnifiedClaimReport.model_validate(
        {
            "claim_id": "CLM-PDFTEST1",
            "vehicle": {
                "make": "Tata Motors",
                "model": "Nexon",
                "variant": None,
                "year": 2023,
                "category": "SUV",
                "reference_image_url": None,
            },
            "damage": {
                "damaged_parts": 2,
                "accepted": 1,
                "review_required": 1,
                "overall_severity": "Moderate",
                "recommended_actions": ["Repair"],
            },
            "pricing": {
                "total_min_inr": 12000,
                "total_max_inr": 18000,
                "parts_priced": 1,
                "parts_pending_manual_inspection": 1,
            },
            "policy": {
                "state": "ready",
                "coverage": None,
                "deductible_inr": 1000,
                "idv_inr": 800000,
                "exclusions": ["Wear and tear"],
                "policy_type": "Comprehensive",
                "insurer_name": "Acme General Insurance",
                "policy_number_masked": "XXXX-XX-1234",
                "coverage_start": date(2025, 1, 1),
                "coverage_end": date(2026, 1, 1),
                "policy_vehicle_make": "Tata",
                "policy_vehicle_model": "Nexon",
                "policy_vehicle_year": 2023,
            },
            "risk": {"risk_level": "low", "signals": [], "generated_at": "2026-07-06T00:00:00Z"},
            "summary": "Front bumper damage assessed; headlight routed for manual inspection.",
            "generated_at": "2026-07-06T00:00:00Z",
        }
    )


AI_ASSESSMENT = {
    "damaged_parts": [
        {
            "part": "Front bumper",
            "severity": "Moderate",
            "status": "Accepted",
            "recommended_action": "Repair",
            "damage_confidence": SENTINEL_CONFIDENCE,
            "part_confidence": SENTINEL_CONFIDENCE,
        },
        {
            "part": "Headlight - (R)",
            "severity": "Uncertain",
            "status": "Review Required",
            "recommended_action": "Manual Inspection",
            "damage_confidence": SENTINEL_CONFIDENCE,
            "part_confidence": SENTINEL_CONFIDENCE,
        },
    ]
}

PRICING_ASSESSMENT = {
    "per_part": {"Front bumper": {"min_inr": 12000, "max_inr": 18000}, "Headlight - (R)": None}
}


def _rendered_text(pdf_bytes: bytes) -> bytes:
    """Decompresses every content stream — fpdf2 deflates them, so raw
    substring checks against the PDF bytes prove nothing either way."""
    text = b""
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", pdf_bytes, re.S):
        try:
            text += zlib.decompress(match.group(1))
        except zlib.error:
            continue
    return text


def _generate() -> bytes:
    return generate_claim_report_pdf(
        _report(),
        [],
        claim_status="review_required",
        ai_assessment=AI_ASSESSMENT,
        pricing_assessment=PRICING_ASSESSMENT,
    )


def test_pdf_is_valid_and_carries_parity_fields():
    pdf_bytes = _generate()
    assert pdf_bytes.startswith(b"%PDF")

    text = _rendered_text(pdf_bytes)
    for expected in (
        b"CLM-PDFTEST1",
        b"Review Required",  # claim status label
        b"Tata Motors Nexon 2023",
        b"Damaged Parts",
        b"Front bumper",
        b"Acme General Insurance",
        b"Comprehensive",
        b"XXXX-XX-1234",
        b"Coverage period",
        b"01 Jan 2025 to 01 Jan 2026",
        b"Rs. 12,000 - Rs. 18,000",
    ):
        assert expected in text, expected


def test_unpriced_part_renders_manual_inspection_not_zero():
    text = _rendered_text(_generate())
    assert b"Manual inspection required" in text
    assert b"Rs. 0" not in text


def test_no_raw_confidence_values_leak_into_pdf():
    text = _rendered_text(_generate())
    assert str(SENTINEL_CONFIDENCE).encode() not in text
    assert b"confidence" not in text.lower()
