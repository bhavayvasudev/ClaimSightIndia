"""Chunked, embedded policy text used for retrieval (`app/services/rag/`).

Vector storage note: production is expected to run Postgres with the
`pgvector` extension (`pgvector` is already a declared backend dependency)
so `embedding` can be a real indexed vector column. This sandbox/dev/test
environment has no Postgres available at all (see backend/.env's sandbox
note), so — mirroring the exact `_jsonb_or_json()` fallback already
established in `app/db/models/claim.py` — `embedding` is a plain JSON
float array on any non-Postgres dialect. `app/services/rag/vector_store.py`
does the similarity search in Python either way (see that module for why
this is fine at this data volume), so the fallback never changes behavior,
only where the vector is stored.
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PolicyChunkRecord(Base):
    __tablename__ = "policy_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_document_id: Mapped[int] = mapped_column(
        ForeignKey("policy_documents.id"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str | None] = mapped_column(String(255), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # List[float]. See module docstring — JSON everywhere in this sandbox,
    # a real pgvector column in a Postgres deployment.
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
