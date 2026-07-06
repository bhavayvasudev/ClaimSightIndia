"""Similarity search over a policy document's chunks.

Brute-force cosine similarity in Python — deliberate, not a stand-in for a
"real" ANN index. A single policy document produces on the order of tens
of chunks (see `_TARGET_CHARS` in `chunking.py`), so scanning all of them
is microseconds of work; an ANN index (or pgvector's own `<=>` operator,
once a real Postgres deployment has the extension enabled — see
`app/db/models/policy_chunk.py`) only starts to matter at a corpus size
this product doesn't have (retrieval is always scoped to one claim's one
policy document, never cross-claim).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Sequence


@dataclass
class ScoredChunk:
    chunk_id: int
    page_number: int | None
    section: str | None
    text: str
    score: float


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def top_k_similar(query_vector: List[float], chunks, k: int = 5) -> List[ScoredChunk]:
    """`chunks` is a list of `PolicyChunkRecord`-shaped objects (id,
    page_number, section, text, embedding)."""

    scored = [
        ScoredChunk(
            chunk_id=c.id,
            page_number=c.page_number,
            section=c.section,
            text=c.text,
            score=_cosine_similarity(query_vector, c.embedding or []),
        )
        for c in chunks
    ]
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored[:k]
