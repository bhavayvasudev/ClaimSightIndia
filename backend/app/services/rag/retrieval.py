"""Retrieval entry point: given the current damage assessment + vehicle
metadata, builds a query, embeds it, and retrieves the policy chunks most
relevant to it. Used by `app/services/policy/coverage_analysis.py`.

`MIN_RELEVANCE_SCORE` is a deliberate floor — a low-relevance top match is
not the same as "no relevant clause exists", and callers must be able to
tell the two apart (see `CoverageStatus.UNCLEAR` vs a confident finding)
rather than always citing whatever scored highest even when nothing
actually matched.
"""

from __future__ import annotations

from typing import List, Optional

from app.observability.timing import timed_block

from app.schemas.policy_state import RetrievedClause
from app.services.rag.embeddings import embed_text
from app.services.rag.vector_store import top_k_similar

MIN_RELEVANCE_SCORE = 0.08
TOP_K = 5


def build_query_text(
    *,
    part: Optional[str] = None,
    severity: Optional[str] = None,
    recommended_action: Optional[str] = None,
    vehicle_type: Optional[str] = None,
    extra_terms: Optional[List[str]] = None,
) -> str:
    terms = [
        part or "",
        severity or "",
        recommended_action or "",
        vehicle_type or "",
        "own damage accidental damage coverage exclusion",
    ]
    if extra_terms:
        terms.extend(extra_terms)
    return " ".join(t for t in terms if t)


def retrieve_relevant_clauses(chunks, query_text: str, *, top_k: int = TOP_K) -> List[RetrievedClause]:
    """`chunks` is the claim's policy document's `PolicyChunkRecord` list.
    Returns an empty list — never a low-quality forced match — when
    nothing clears `MIN_RELEVANCE_SCORE`."""

    if not chunks or not query_text.strip():
        return []

    with timed_block("policy_rag_retrieval"):
        query_vector = embed_text(query_text)
        scored = top_k_similar(query_vector, chunks, k=top_k)

    return [
        RetrievedClause(
            page=s.page_number,
            section=s.section,
            excerpt=s.text[:600],
            score=round(s.score, 4),
        )
        for s in scored
        if s.score >= MIN_RELEVANCE_SCORE
    ]
