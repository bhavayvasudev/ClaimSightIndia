"""Policy document text extraction — real pypdf text extraction over a
genuinely generated PDF (not a mock), plus the documented failure modes:
scanned/no-text PDF, unsupported content type, and OCR-unavailable
degradation for image uploads in an environment without easyocr
installed."""

from __future__ import annotations

import io

from fpdf import FPDF, XPos, YPos
from pypdf import PdfWriter

from app.services.policy.extraction import extract_policy_text


def _make_simple_text_pdf(lines: list[str]) -> bytes:
    """Builds a real, valid single-page PDF containing real, extractable
    text using `fpdf2` (already a dependency for PDF report export) — a
    genuine PDF, not a mock."""

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    for line in lines:
        pdf.cell(0, 10, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    return bytes(pdf.output())


def test_extract_pdf_text_reads_real_embedded_text():
    pdf_bytes = _make_simple_text_pdf(["Policy Schedule", "Own Damage Coverage Applies"])
    result = extract_policy_text(pdf_bytes, "application/pdf")
    assert result.ok
    assert result.method == "pdf_text"
    assert "Policy Schedule" in result.full_text or "Own Damage" in result.full_text


def test_extract_pdf_text_no_embedded_text_fails_closed():
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)

    result = extract_policy_text(buf.getvalue(), "application/pdf")
    assert not result.ok
    assert result.method == "none"
    assert "scanned" in (result.error or "").lower()


def test_extract_policy_text_rejects_unsupported_content_type():
    result = extract_policy_text(b"not a real file", "text/plain")
    assert not result.ok
    assert "unsupported" in (result.error or "").lower()


def test_extract_policy_text_corrupted_pdf_fails_closed():
    result = extract_policy_text(b"this-is-not-a-pdf-at-all", "application/pdf")
    assert not result.ok


def test_extract_image_ocr_unavailable_in_this_environment_fails_closed():
    # easyocr is a declared-but-not-installed optional dependency in this
    # sandbox (see extraction.py module docstring) — verifies the
    # documented graceful degradation rather than a crash.
    result = extract_policy_text(b"\x89PNG\r\n\x1a\n" + b"0" * 100, "image/png")
    assert not result.ok
    assert result.method == "none"
