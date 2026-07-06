"""Structured field extraction from a policy document's raw text.

Two extraction paths:

1. `anthropic_api_key` configured -> ask Claude for the fields as JSON,
   with an explicit instruction to leave a field null rather than guess.
   The model only ever sees the already-extracted policy text (never
   sees the full request/response of anything else) — this is a single,
   narrow, structured-extraction call, not an open-ended agent.
2. No API key configured -> a deterministic regex/keyword heuristic over
   common Indian motor-policy phrasing (IDV, deductible, policy period,
   coverage type, exclusions heading). Lower recall than the LLM path,
   but same guarantee: a field it isn't confident about stays `None`,
   never fabricated.

Both paths are exercised by `test_structured_extraction.py` — the
heuristic path always runs in tests/CI (no network, no API key needed),
the LLM path is exercised with a mocked client.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import Optional

from app.config import get_settings
from app.schemas.policy_state import PolicyStructuredData, PolicyType

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You extract structured fields from an Indian motor insurance policy \
document's text. Only report a field if it is explicitly present in the text — if a field \
is absent, ambiguous, or you are not confident, set it to null. Never invent a value. \
Respond with ONLY a JSON object with these exact keys: policy_type (one of \
"Third-Party", "Comprehensive", "Standalone Own-Damage", or null), policy_number, \
insurer_name, coverage_start (YYYY-MM-DD or null), coverage_end (YYYY-MM-DD or null), \
idv_inr (integer rupees or null), deductible_inr (integer rupees or null), \
zero_dep (true/false), add_ons (array of strings), exclusions (array of strings), \
vehicle_make, vehicle_model, vehicle_year (integer or null), registration_number."""


def _count_fields(data: PolicyStructuredData) -> int:
    count = 0
    for field_name in (
        "policy_type", "policy_number", "insurer_name", "coverage_start", "coverage_end",
        "idv_inr", "deductible_inr", "vehicle_make", "vehicle_model", "vehicle_year",
        "registration_number",
    ):
        if getattr(data, field_name) is not None:
            count += 1
    count += len(data.add_ons) + len(data.exclusions)
    return count


def _extract_via_llm(text: str) -> Optional[PolicyStructuredData]:
    settings = get_settings()
    if not settings.anthropic_api_key:
        return None

    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic package not installed; falling back to heuristic extraction")
        return None

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text[:12000]}],
        )
        raw = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
        payload = json.loads(raw)
        data = PolicyStructuredData.model_validate(payload)
        data.extraction_method = "llm"
        data.fields_found = _count_fields(data)
        return data
    except Exception:
        # Never let an LLM/network hiccup crash policy processing — fall
        # through to the heuristic extractor instead.
        logger.exception("LLM structured extraction failed; falling back to heuristic")
        return None


# ---------------------------------------------------------------------------
# Deterministic heuristic fallback — no API key, no network required.
# ---------------------------------------------------------------------------

_IDV_RE = re.compile(r"(?:IDV|Insured'?s?\s+Declared\s+Value)\D{0,20}?([\d,]{4,})", re.IGNORECASE)
_DEDUCTIBLE_RE = re.compile(
    r"(?:Compulsory\s+Deductible|Voluntary\s+Deductible|Deductible)\D{0,20}?([\d,]{2,})",
    re.IGNORECASE,
)
_POLICY_NUMBER_RE = re.compile(r"Policy\s*(?:No\.?|Number)\s*[:\-]?\s*([A-Z0-9\/\-]{6,})", re.IGNORECASE)
_REG_NUMBER_RE = re.compile(r"\b([A-Z]{2}[\s\-]?[0-9]{1,2}[\s\-]?[A-Z]{1,3}[\s\-]?[0-9]{4})\b")
_DATE_RE = r"(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})"
_PERIOD_RE = re.compile(
    rf"(?:Policy\s+Period|Period\s+of\s+Insurance)\D{{0,20}}?{_DATE_RE}\D{{1,15}}?{_DATE_RE}",
    re.IGNORECASE,
)


def _parse_date(raw: str) -> Optional[date]:
    for sep in ("/", "-", "."):
        if sep in raw:
            parts = raw.split(sep)
            if len(parts) == 3:
                try:
                    day, month, year = (int(p) for p in parts)
                    if year < 100:
                        year += 2000
                    return date(year, month, day)
                except ValueError:
                    return None
    return None


def _detect_policy_type(text: str) -> Optional[PolicyType]:
    lowered = text.lower()
    if "standalone" in lowered and "own damage" in lowered:
        return PolicyType.STANDALONE_OD
    if "comprehensive" in lowered:
        return PolicyType.COMPREHENSIVE
    if "third-party" in lowered or "third party" in lowered:
        return PolicyType.THIRD_PARTY
    return None


def _extract_exclusions(text: str) -> list[str]:
    """Pulls bullet/numbered lines following an 'Exclusions' heading — a
    common structural pattern in Indian policy schedules. Deliberately
    conservative: only lines that look like list items are captured, and
    at most 10, to avoid accidentally swallowing unrelated document text."""

    match = re.search(r"Exclusions?\b[:\s]*\n", text, re.IGNORECASE)
    if not match:
        return []
    tail = text[match.end():]
    lines = []
    for line in tail.splitlines():
        stripped = line.strip(" \t-•*")
        if not stripped:
            if lines:
                break
            continue
        if re.match(r"^(\d+[\.\)]|[a-z][\.\)])\s*.+", stripped, re.IGNORECASE) or line.strip().startswith(("-", "•", "*")):
            lines.append(stripped)
            if len(lines) >= 10:
                break
        elif lines:
            break
    return lines


def _extract_via_heuristic(text: str) -> PolicyStructuredData:
    data = PolicyStructuredData(extraction_method="heuristic")

    if (m := _IDV_RE.search(text)) is not None:
        try:
            data.idv_inr = int(m.group(1).replace(",", ""))
        except ValueError:
            pass
    if (m := _DEDUCTIBLE_RE.search(text)) is not None:
        try:
            data.deductible_inr = int(m.group(1).replace(",", ""))
        except ValueError:
            pass
    if (m := _POLICY_NUMBER_RE.search(text)) is not None:
        data.policy_number = m.group(1)
    if (m := _REG_NUMBER_RE.search(text)) is not None:
        data.registration_number = re.sub(r"[\s\-]", "", m.group(1)).upper()
    if (m := _PERIOD_RE.search(text)) is not None:
        data.coverage_start = _parse_date(m.group(1))
        data.coverage_end = _parse_date(m.group(2))

    data.policy_type = _detect_policy_type(text)
    data.zero_dep = bool(re.search(r"zero[\s\-]?dep(?:reciation)?", text, re.IGNORECASE))
    data.exclusions = _extract_exclusions(text)
    data.fields_found = _count_fields(data)
    return data


def extract_structured_data(text: str) -> PolicyStructuredData:
    """Single entry point used by `app/services/policy/service.py`. Tries
    the LLM path first (if configured), falls back to the heuristic
    extractor — never raises, never returns a fabricated field."""

    if not text.strip():
        return PolicyStructuredData(extraction_method="heuristic", fields_found=0)

    llm_result = _extract_via_llm(text)
    if llm_result is not None:
        return llm_result

    return _extract_via_heuristic(text)
