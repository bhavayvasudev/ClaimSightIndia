"""Request/response schemas for the policy document API
(`app/api/routes/policy.py`).

`extracted_text` is deliberately never included here — only the
structured fields derived from it, plus enough status/error information
for the claimant to understand what happened. See
`app/db/models/policy_document.py`."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.db.models.policy_document import PolicyDocumentRecord


class PolicyDocumentResponse(BaseModel):
    status: str
    filename: str
    extraction_method: Optional[str] = None
    page_count: Optional[int] = None
    structured_data: Optional[dict] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: PolicyDocumentRecord) -> "PolicyDocumentResponse":
        return cls(
            status=record.status,
            filename=record.filename,
            extraction_method=record.extraction_method,
            page_count=record.page_count,
            structured_data=record.structured_data,
            error_message=record.error_message,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
