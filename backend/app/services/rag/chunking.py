"""Chunks extracted policy text while preserving page/section metadata,
so every retrieved clause can cite exactly where it came from
(`RetrievedClause.page`/`.section` in `app/schemas/policy_state.py`).

Strategy: paragraph-aware greedy accumulation up to `_TARGET_CHARS` per
chunk, never splitting a paragraph across chunks unless the paragraph
itself exceeds the target (rare for policy schedules, common enough for
long clause blocks that it's still handled). A simple heading heuristic
(a short Title Case / ALL CAPS line, or a line matching a known policy
section vocabulary) tracks the "current section" so every chunk knows
which clause heading it fell under, even though headings themselves
aren't split into their own chunk.

Chunks never span a page boundary — always flushed at the end of each
page — so `Chunk.page_number` is always an accurate citation. A page
whose accumulated text is too short to justify its own chunk
(`_MIN_CHARS`) is merged into the *previous* chunk's text (keeping that
chunk's own page/section citation, which stays accurate for the bulk of
its content) rather than merged forward into a later page, which would
mislabel that later page's content under an earlier page's citation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

_TARGET_CHARS = 900
_MIN_CHARS = 200

_KNOWN_SECTION_TERMS = (
    "own damage", "third party", "own damage cover", "add-on", "add on",
    "exclusions", "exclusion", "conditions", "general conditions",
    "policy schedule", "coverage", "deductible", "endorsement",
    "personal accident", "no claim bonus", "idv", "declaration",
)


@dataclass
class Chunk:
    index: int
    page_number: Optional[int]
    section: Optional[str]
    text: str


def _looks_like_heading(line: str) -> bool:
    stripped = line.strip()
    if not (3 <= len(stripped) <= 80):
        return False
    if stripped.endswith(('.', ',')):
        return False
    lowered = stripped.lower()
    if any(term in lowered for term in _KNOWN_SECTION_TERMS):
        return True
    # All-caps heading (allow digits/punctuation, require at least one letter)
    letters = [c for c in stripped if c.isalpha()]
    return bool(letters) and stripped.upper() == stripped


def chunk_policy_text(pages) -> List[Chunk]:
    """`pages` is a list of objects with `.page_number` / `.text`
    (`PageText` from `app/services/policy/extraction.py`)."""

    chunks: List[Chunk] = []
    current_section: Optional[str] = None

    for page in pages:
        buffer_parts: List[str] = []
        buffer_section: Optional[str] = current_section

        def flush_page_buffer():
            nonlocal buffer_parts, buffer_section
            text = "\n".join(buffer_parts).strip()
            if not text:
                buffer_parts = []
                return

            # Only fold a too-short buffer into the previous chunk when
            # that chunk is a same-page overflow continuation (a trailing
            # scrap left over after this page already flushed once past
            # _TARGET_CHARS) — never into a chunk from a *different* page,
            # which would mislabel this page's content under another
            # page's citation (see module docstring).
            can_merge_into_previous = (
                chunks and chunks[-1].page_number == page.page_number and len(text) < _MIN_CHARS
            )
            if can_merge_into_previous:
                chunks[-1].text = f"{chunks[-1].text}\n{text}"
            else:
                chunks.append(
                    Chunk(index=len(chunks), page_number=page.page_number, section=buffer_section, text=text)
                )
            buffer_parts = []
            buffer_section = current_section

        paragraphs = [p for p in re.split(r"\n\s*\n", page.text) if p.strip()]
        for para in paragraphs:
            first_line = para.strip().splitlines()[0] if para.strip() else ""
            if _looks_like_heading(first_line):
                current_section = first_line.strip()
                if not buffer_parts:
                    buffer_section = current_section

            candidate_len = sum(len(p) for p in buffer_parts) + len(para)
            if buffer_parts and candidate_len > _TARGET_CHARS:
                flush_page_buffer()

            buffer_parts.append(para.strip())

        flush_page_buffer()

    return chunks
