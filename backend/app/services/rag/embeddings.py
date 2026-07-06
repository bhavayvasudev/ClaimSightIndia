"""Text embeddings for policy-clause retrieval.

No embedding-model API key is configured anywhere in this project
(`Settings.anthropic_api_key` is the only LLM credential, and Anthropic
does not serve an embeddings endpoint). Rather than force a new paid
dependency/secret the deployment hasn't provisioned, this uses a
deterministic **feature-hashing vectorizer**: tokens (unigrams + bigrams)
are hashed into a fixed-width vector with TF weighting and L2-normalized,
the same "hashing trick" production text-classification systems have used
for years (e.g. Vowpal Wabbit, scikit-learn's `HashingVectorizer`). It
requires no model download, no network call, and no GPU — appropriate for
retrieval over the fairly lexical, keyword-heavy vocabulary of insurance
policy clauses ("own damage", "third party", "exclusion", part names).

This is an intentionally swappable MVP choice, not a permanent
architectural commitment — see `docs/architecture.md`'s production
readiness notes for upgrading to a hosted embedding model (e.g. Voyage AI,
which Anthropic recommends for embeddings) once that dependency/secret is
actually provisioned. Swapping it out only requires changing this module;
`vector_store.py`/`retrieval.py` just consume fixed-length float vectors.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from typing import List

EMBEDDING_DIM = 256

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> List[str]:
    tokens = _TOKEN_RE.findall(text.lower())
    bigrams = [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
    return tokens + bigrams


def _hash_index(token: str) -> int:
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % EMBEDDING_DIM


def embed_text(text: str) -> List[float]:
    """Returns a unit-length `EMBEDDING_DIM`-dimensional vector. Empty/
    whitespace-only text yields an all-zero vector (cosine similarity
    against it is always 0, which is the correct "no signal" behavior)."""

    tokens = _tokenize(text)
    if not tokens:
        return [0.0] * EMBEDDING_DIM

    counts = Counter(_hash_index(t) for t in tokens)
    vector = [0.0] * EMBEDDING_DIM
    for index, count in counts.items():
        # log-TF dampens the effect of one very repetitive clause dominating
        # the vector, without needing corpus-wide IDF statistics.
        vector[index] = 1.0 + math.log(count)

    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0:
        return vector
    return [v / norm for v in vector]
