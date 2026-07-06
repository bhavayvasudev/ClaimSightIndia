"""Local filesystem storage for uploaded policy documents.

Same `settings.upload_dir` root the rest of the app is documented to use
for uploads (`app/config.py`). Local disk is explicitly NOT
production-safe for multi-instance deployment — see the production
readiness notes in `docs/architecture.md` for the object-storage
migration path (S3/GCS-compatible, one bucket per environment).
"""

from __future__ import annotations

import uuid
from pathlib import Path

from app.config import get_settings


def _policies_dir() -> Path:
    settings = get_settings()
    path = Path(settings.upload_dir) / "policies"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_policy_file(claim_id: str, filename: str, content: bytes) -> str:
    """Writes the file under `<upload_dir>/policies/<claim_id>/` with a
    random prefix (never trust the client filename alone as a path
    component — it's sanitized to its basename first) and returns the
    relative storage path stored on `PolicyDocumentRecord.storage_path`."""

    safe_name = Path(filename).name or "policy"
    claim_dir = _policies_dir() / claim_id
    claim_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex[:12]}_{safe_name}"
    full_path = claim_dir / stored_name
    full_path.write_bytes(content)
    return str(full_path)


def read_policy_file(storage_path: str) -> bytes:
    return Path(storage_path).read_bytes()
