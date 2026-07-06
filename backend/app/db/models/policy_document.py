"""Persisted policy document uploaded for a claim.

This is genuinely new — despite `app/schemas/claim_state.py`'s aspirational
`PolicyDetails`/`PolicyType` contracts and the `easyocr`/`llama-index`/
`pgvector` dependencies already declared in `pyproject.toml`, no policy
upload/extraction path was actually wired up before this. See
`app/services/policy/` for the extraction pipeline that populates this
table.

One policy document per claim (a claimant uploads their own policy once);
`claim_id` is therefore unique, not just indexed.
"""

import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PolicyDocumentStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class PolicyExtractionMethod(str, enum.Enum):
    PDF_TEXT = "pdf_text"
    OCR = "ocr"
    NONE = "none"


def _jsonb_or_json() -> JSON:
    # Same dialect-fallback rationale as app/db/models/claim.py: real JSONB
    # on Postgres, generic JSON on SQLite for tests/local dev.
    return JSON().with_variant(JSONB(), "postgresql")


class PolicyDocumentRecord(Base):
    __tablename__ = "policy_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claim_id: Mapped[int] = mapped_column(
        ForeignKey("claims.id"), unique=True, nullable=False, index=True
    )
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=PolicyDocumentStatus.UPLOADED.value
    )
    extraction_method: Mapped[str | None] = mapped_column(String(16), nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Full extracted text, kept for re-chunking if the chunking strategy
    # ever changes without re-running OCR/PDF extraction. Never returned
    # verbatim over the API (see app/schemas/policy_api.py) — only
    # structured_data and retrieved excerpts are.
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # PolicyStructuredData (app/schemas/policy_state.py), LLM- or
    # regex-extracted. Optional/uncertain fields stay None rather than
    # guessed — see that schema's docstring.
    structured_data: Mapped[dict | None] = mapped_column(_jsonb_or_json(), nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
