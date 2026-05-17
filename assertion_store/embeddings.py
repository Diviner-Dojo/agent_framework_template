"""Local embedding helper for the memory substrate.

Wraps sentence-transformers with a single ``embed(text)`` function. Lazy-loads
the model on first call so import time stays fast. Defaults to
``all-MiniLM-L6-v2`` (384-dim, ~80MB, runs on CPU).

For Insight Journal use case (#3, future), this is the only embedding path —
no API client is imported, satisfying the privacy-by-architecture commitment.
"""

from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    """Lazy-load the embedding model on first use."""
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed(text: str) -> np.ndarray:
    """Compute a 384-dimensional embedding for ``text``.

    Args:
        text: Input text to embed. Truncated silently to the model's max
            sequence length (~256 tokens for all-MiniLM-L6-v2).

    Returns:
        A numpy array of shape (384,), dtype float32. Suitable for direct
        ``.tobytes()`` into sqlite-vec.
    """
    return _get_model().encode(text, convert_to_numpy=True).astype("float32")
