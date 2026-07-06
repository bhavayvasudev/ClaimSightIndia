"""Orchestrates the policy document pipeline: upload -> extract -> chunk
-> embed -> structured-extract -> persist.

Deliberately synchronous within the request (no background task queue
exists in this codebase yet) — extraction and the heuristic/LLM
structured-extraction call are fast enough for a single policy document
that a request-scoped call is acceptable for this MVP. A production
deployment with a task queue could move this behind `PolicyDocumentStatus.
PROCESSING` and a webhook/poll, without changing the pipeline itself.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.db.models.policy_document import PolicyDocumentRecord, PolicyDocumentStatus
from app.db.policy_repository import PolicyDocumentRepository
from app.services.policy import storage
from app.services.policy.extraction import extract_policy_text
from app.services.policy.structured_extraction import extract_structured_data
from app.services.rag.chunking import chunk_policy_text
from app.services.rag.embeddings import embed_text
from app.db.models.policy_chunk import PolicyChunkRecord

logger = logging.getLogger(__name__)

MAX_POLICY_BYTES = 15 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/webp"}


class PolicyUploadRejected(Exception):
    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


async def upload_and_process_policy(
    repo: PolicyDocumentRepository,
    *,
    claim_id: int,
    claim_public_id: str,
    user_id: Optional[int],
    filename: str,
    content_type: str,
    content: bytes,
) -> PolicyDocumentRecord:
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise PolicyUploadRejected("unsupported_file_type", f"Unsupported file type: {content_type}")
    if len(content) > MAX_POLICY_BYTES:
        raise PolicyUploadRejected(
            "file_too_large", f"Policy document exceeds the {MAX_POLICY_BYTES // (1024*1024)}MB limit."
        )
    if len(content) == 0:
        raise PolicyUploadRejected("empty_file", "Uploaded file is empty.")

    storage_path = storage.save_policy_file(claim_public_id, filename, content)

    record = await repo.upsert_for_claim(
        claim_id=claim_id,
        user_id=user_id,
        filename=filename,
        content_type=content_type,
        byte_size=len(content),
        storage_path=storage_path,
    )

    record.status = PolicyDocumentStatus.PROCESSING.value
    record = await repo.save(record)

    extraction = extract_policy_text(content, content_type)
    if not extraction.ok:
        record.status = PolicyDocumentStatus.FAILED.value
        record.error_message = extraction.error
        record.extraction_method = extraction.method
        return await repo.save(record)

    record.extraction_method = extraction.method
    record.page_count = extraction.page_count
    record.extracted_text = extraction.full_text

    try:
        structured = extract_structured_data(extraction.full_text)
        record.structured_data = structured.model_dump(mode="json")

        chunks = chunk_policy_text(extraction.pages)
        chunk_records = [
            PolicyChunkRecord(
                policy_document_id=record.id,
                chunk_index=c.index,
                page_number=c.page_number,
                section=c.section,
                text=c.text,
                embedding=embed_text(c.text),
            )
            for c in chunks
        ]
        record.status = PolicyDocumentStatus.PROCESSED.value
    except Exception:
        # Extraction succeeded but downstream chunking/embedding/structuring
        # failed — the claim must still have damage assessment + pricing
        # survive untouched (see graph failure-handling rules); this
        # policy document alone is marked failed.
        logger.exception("Policy structuring/chunking failed for claim %s", claim_public_id)
        record.status = PolicyDocumentStatus.FAILED.value
        record.error_message = "Policy processing failed after text extraction."
        return await repo.save(record)

    record = await repo.save(record)
    await repo.replace_chunks(record.id, chunk_records)
    return record
