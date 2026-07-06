"""Policy RAG tests: chunking, embeddings, and retrieval — the pieces
`app/services/rag/` is built from. Covers: successful retrieval, no
policy chunks, empty extraction, relevant clause retrieval, no relevant
clause, and a retrieval-failure-shaped input (embedding on empty text).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.services.policy.extraction import PageText
from app.services.rag.chunking import chunk_policy_text
from app.services.rag.embeddings import EMBEDDING_DIM, embed_text
from app.services.rag.retrieval import build_query_text, retrieve_relevant_clauses
from app.services.rag.vector_store import top_k_similar


@dataclass
class _FakeChunk:
    id: int
    page_number: Optional[int]
    section: Optional[str]
    text: str
    embedding: Optional[list] = None


def test_embed_text_is_unit_length_and_deterministic():
    v1 = embed_text("own damage accidental damage cover")
    v2 = embed_text("own damage accidental damage cover")
    assert v1 == v2
    assert len(v1) == EMBEDDING_DIM
    norm = sum(x * x for x in v1) ** 0.5
    assert abs(norm - 1.0) < 1e-6


def test_embed_text_empty_text_returns_zero_vector():
    assert embed_text("") == [0.0] * EMBEDDING_DIM
    assert embed_text("   ") == [0.0] * EMBEDDING_DIM


def test_chunk_policy_text_preserves_page_and_detects_section():
    pages = [
        PageText(page_number=1, text="POLICY SCHEDULE\n\nSome intro text about the policyholder."),
        PageText(
            page_number=2,
            text=(
                "Own Damage Coverage\n\n"
                "The Company shall indemnify the insured against loss or damage to the vehicle "
                "caused by accidental external means, including collision, subject to the terms "
                "below. This section covers own damage and accidental damage."
            ),
        ),
        PageText(
            page_number=3,
            text=(
                "Exclusions\n\n"
                "1. Consequential loss of any kind.\n"
                "2. Damage while driving under the influence of alcohol.\n"
                "3. Wear and tear or mechanical breakdown.\n"
            ),
        ),
    ]
    chunks = chunk_policy_text(pages)
    assert len(chunks) >= 1
    assert any(c.page_number == 2 for c in chunks)
    exclusion_chunk = next((c for c in chunks if c.page_number == 3), None)
    assert exclusion_chunk is not None
    assert exclusion_chunk.section is not None
    assert "exclusion" in exclusion_chunk.section.lower()


def test_top_k_similar_ranks_relevant_chunk_highest():
    query = embed_text("front bumper accidental damage coverage")
    chunks = [
        _FakeChunk(1, 1, "Own Damage Coverage", "own damage accidental damage front bumper covered"),
        _FakeChunk(2, 2, "Exclusions", "wear and tear mechanical breakdown excluded"),
    ]
    for c in chunks:
        c.embedding = embed_text(c.text)

    scored = top_k_similar(query, chunks, k=2)
    assert scored[0].chunk_id == 1
    assert scored[0].score > scored[1].score


def test_retrieve_relevant_clauses_returns_relevant_match():
    chunks = [
        _FakeChunk(
            1, 4, "Own Damage Coverage",
            "own damage accidental damage front bumper collision covered under this policy",
        )
    ]
    for c in chunks:
        c.embedding = embed_text(c.text)

    query = build_query_text(part="Front bumper", severity="Moderate", recommended_action="Repair")
    clauses = retrieve_relevant_clauses(chunks, query)
    assert len(clauses) == 1
    assert clauses[0].page == 4
    assert clauses[0].section == "Own Damage Coverage"


def test_retrieve_relevant_clauses_no_relevant_match_returns_empty():
    chunks = [
        _FakeChunk(1, 1, "Contact Information", "call our helpline for assistance at any time")
    ]
    for c in chunks:
        c.embedding = embed_text(c.text)

    query = build_query_text(part="Front bumper", severity="Moderate", recommended_action="Repair")
    clauses = retrieve_relevant_clauses(chunks, query)
    assert clauses == []


def test_retrieve_relevant_clauses_no_policy_chunks_returns_empty():
    assert retrieve_relevant_clauses([], "front bumper") == []


def test_retrieve_relevant_clauses_empty_query_returns_empty():
    chunks = [_FakeChunk(1, 1, None, "some clause text")]
    chunks[0].embedding = embed_text(chunks[0].text)
    assert retrieve_relevant_clauses(chunks, "") == []
