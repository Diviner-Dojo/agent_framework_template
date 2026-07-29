"""Local embedding helper for the memory substrate.

Wraps sentence-transformers with a single ``embed(text)`` function. Defaults to
``all-MiniLM-L6-v2`` (384-dim, ~80MB, runs on CPU).

For Insight Journal use case (#3, future), this is the only embedding path —
no API client is imported, satisfying the privacy-by-architecture commitment.

**Both heavy imports are deferred to first call.** They used to sit at module
scope while this docstring claimed the module was lazy, which made importing
anything downstream — including ``assertion_store.substrate`` and
``mcp_server.server`` — require torch. That in turn forced whole-module test
skips, silently disabling three regression guards listed in the ledger
(thread-local isolation and two path-traversal checks). Import cost belongs to
the caller that actually embeds something. See ADR-0029 and REV-20260728-140000.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only, never imported at runtime
    import numpy as np
    from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    """Load the embedding model on first use.

    Raises:
        ImportError: with an actionable message if the optional memory-substrate
            extras are not installed.
    """
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise ImportError(
                "The memory substrate needs the optional extras. Install with: "
                "pip install sentence-transformers sqlite-vec"
            ) from exc
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


def __getattr__(name: str) -> Any:
    """Expose ``np`` for callers that reference it, without importing it eagerly."""
    if name == "np":
        import numpy as np

        return np
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
