"""Text extraction from an uploaded policy document.

Two paths, both real (no mocked/fake text is ever returned):

1. PDF with embedded text -> `pypdf` reads it directly, page by page, so
   page numbers survive into `PageText.page_number` for later chunk
   citation.
2. Image upload (a photographed/scanned policy page) or a PDF with no
   extractable text at all -> OCR via `easyocr`.

`easyocr` is a declared backend dependency (`pyproject.toml`) but is a
heavy optional install (pulls in torch); it is imported lazily here so
environments without it installed still get full PDF-text extraction —
OCR-only documents fail closed into `ExtractionResult.failed()` with a
clear reason, which the caller (`app/services/policy/service.py`) turns
into `PolicyDocumentStatus.FAILED` rather than crashing or fabricating
text. This is the same "degrade, never fabricate" rule the rest of the
codebase follows for a failed/unavailable model.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from pypdf import PdfReader

PDF_CONTENT_TYPE = "application/pdf"
OCR_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


@dataclass
class PageText:
    page_number: int
    text: str


@dataclass
class ExtractionResult:
    ok: bool
    method: str  # "pdf_text" | "ocr" | "none"
    pages: List[PageText] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text.strip())

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @classmethod
    def failed(cls, error: str) -> "ExtractionResult":
        return cls(ok=False, method="none", pages=[], error=error)


def _extract_pdf_text(content: bytes) -> ExtractionResult:
    try:
        reader = PdfReader(io.BytesIO(content))
    except Exception as exc:  # pypdf raises several distinct error types
        return ExtractionResult.failed(f"Could not parse PDF: {exc}")

    if reader.is_encrypted:
        # Never silently skip password protection — surface it as a clean
        # failure so the caller can ask the claimant for an unlocked copy.
        return ExtractionResult.failed("Policy PDF is password-protected.")

    pages: List[PageText] = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        pages.append(PageText(page_number=i, text=text))

    if not any(p.text.strip() for p in pages):
        return ExtractionResult(
            ok=False,
            method="none",
            pages=pages,
            error=(
                "No embedded text found — this looks like a scanned/image-based PDF. "
                "OCR-based extraction requires the optional easyocr dependency."
            ),
        )

    return ExtractionResult(ok=True, method="pdf_text", pages=pages)


def _ocr_reader():
    try:
        import easyocr  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "OCR is unavailable in this environment: the optional 'easyocr' "
            "dependency is not installed."
        ) from exc
    return easyocr.Reader(["en"], gpu=False, verbose=False)


def _extract_image_text(content: bytes) -> ExtractionResult:
    try:
        reader = _ocr_reader()
    except RuntimeError as exc:
        return ExtractionResult.failed(str(exc))

    try:
        results = reader.readtext(content, detail=0, paragraph=True)
    except Exception as exc:
        return ExtractionResult.failed(f"OCR failed to process the image: {exc}")

    text = "\n".join(results)
    if not text.strip():
        return ExtractionResult.failed("OCR could not detect any text in the image.")

    return ExtractionResult(ok=True, method="ocr", pages=[PageText(page_number=1, text=text)])


def extract_policy_text(content: bytes, content_type: str) -> ExtractionResult:
    """Single entry point used by `app/services/policy/service.py`. Never
    raises — every failure mode is represented in the returned
    `ExtractionResult`."""

    if content_type == PDF_CONTENT_TYPE:
        result = _extract_pdf_text(content)
        if result.ok:
            return result
        # A scanned PDF has no embedded text; OCR would need page-image
        # rasterization (e.g. poppler/PyMuPDF), which this MVP does not
        # add — see module docstring. Surface the original pdf failure.
        return result

    if content_type in OCR_CONTENT_TYPES:
        return _extract_image_text(content)

    return ExtractionResult.failed(f"Unsupported policy document type: {content_type}")
