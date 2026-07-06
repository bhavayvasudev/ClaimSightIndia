"""Structured policy field extraction — the deterministic heuristic path
(no API key configured, exercised in every test run) plus the LLM path
(exercised with a mocked anthropic client)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.policy.structured_extraction import extract_structured_data

SAMPLE_POLICY_TEXT = """
POLICY SCHEDULE

Policy No: 3001/PVT/2026/00012345
Policy Period: 01/01/2026 To 31/12/2026

Vehicle Make: Hyundai
Vehicle Model: Verna
Registration Number: MH12AB1234

This is a Comprehensive policy.

Insured's Declared Value (IDV): 8,50,000
Compulsory Deductible: 1,000

Own Damage Coverage
The Company shall indemnify the insured against accidental damage.

Exclusions
1. Consequential loss of any kind.
2. Wear and tear or mechanical breakdown.
3. Damage while driving under the influence of alcohol.
"""


def test_heuristic_extraction_finds_idv_and_deductible():
    data = extract_structured_data(SAMPLE_POLICY_TEXT)
    assert data.extraction_method == "heuristic"
    assert data.idv_inr == 850000
    assert data.deductible_inr == 1000
    assert data.fields_found > 0


def test_heuristic_extraction_finds_policy_type():
    data = extract_structured_data(SAMPLE_POLICY_TEXT)
    assert data.policy_type is not None
    assert data.policy_type.value == "Comprehensive"


def test_heuristic_extraction_finds_registration_number():
    data = extract_structured_data(SAMPLE_POLICY_TEXT)
    assert data.registration_number == "MH12AB1234"


def test_heuristic_extraction_finds_coverage_dates():
    data = extract_structured_data(SAMPLE_POLICY_TEXT)
    assert data.coverage_start is not None
    assert data.coverage_end is not None
    assert data.coverage_start.year == 2026
    assert data.coverage_end.month == 12


def test_heuristic_extraction_finds_exclusions():
    data = extract_structured_data(SAMPLE_POLICY_TEXT)
    assert len(data.exclusions) >= 2


def test_heuristic_extraction_missing_fields_stay_none_not_guessed():
    data = extract_structured_data("This document has no recognizable policy fields at all.")
    assert data.idv_inr is None
    assert data.deductible_inr is None
    assert data.policy_type is None
    assert data.fields_found == 0


def test_extract_structured_data_empty_text_returns_empty_result():
    data = extract_structured_data("")
    assert data.fields_found == 0
    assert data.idv_inr is None


def test_llm_extraction_used_when_api_key_configured():
    fake_settings = MagicMock(anthropic_api_key="fake-key", claude_model="claude-test")

    fake_block = MagicMock()
    fake_block.type = "text"
    fake_block.text = (
        '{"policy_type": "Comprehensive", "policy_number": "POL123", "insurer_name": "Acme", '
        '"coverage_start": "2026-01-01", "coverage_end": "2026-12-31", "idv_inr": 500000, '
        '"deductible_inr": 2000, "zero_dep": true, "add_ons": ["Zero Depreciation"], '
        '"exclusions": ["Wear and tear"], "vehicle_make": "Honda", "vehicle_model": "City", '
        '"vehicle_year": 2022, "registration_number": "KA01AB1234"}'
    )
    fake_response = MagicMock(content=[fake_block])
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_response

    with patch("app.services.policy.structured_extraction.get_settings", return_value=fake_settings):
        with patch("anthropic.Anthropic", return_value=fake_client):
            data = extract_structured_data(SAMPLE_POLICY_TEXT)

    assert data.extraction_method == "llm"
    assert data.idv_inr == 500000
    assert data.vehicle_make == "Honda"


def test_llm_extraction_failure_falls_back_to_heuristic():
    fake_settings = MagicMock(anthropic_api_key="fake-key", claude_model="claude-test")
    fake_client = MagicMock()
    fake_client.messages.create.side_effect = RuntimeError("network error")

    with patch("app.services.policy.structured_extraction.get_settings", return_value=fake_settings):
        with patch("anthropic.Anthropic", return_value=fake_client):
            data = extract_structured_data(SAMPLE_POLICY_TEXT)

    assert data.extraction_method == "heuristic"
    assert data.idv_inr == 850000
