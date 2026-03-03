"""Shared utilities for the knowledge pipeline scripts.

Contains the canonical tokenization and pattern hashing functions
used by mine_patterns.py and unify_sightings.py. These MUST produce
identical output for the same input — cross-source Rule of Three
counting depends on hash consistency.
"""

import hashlib
import re


def tokenize(text: str) -> set[str]:
    """Tokenize text into lowercase word tokens, filtering short words.

    Args:
        text: The text to tokenize.

    Returns:
        Set of lowercase tokens with length > 2.
    """
    words = re.findall(r"[a-z][a-z0-9_]+", text.lower())
    return {w for w in words if len(w) > 2}


def pattern_hash(category: str, summary: str) -> str:
    """Generate a stable hash for a pattern based on category and key tokens.

    Uses the first 10 sorted tokens from the summary combined with
    the category to produce a 16-character hex digest.

    Args:
        category: The pattern category.
        summary: The pattern summary text.

    Returns:
        A 16-character hex hash string.
    """
    tokens = sorted(tokenize(summary))
    key = f"{category}:{':'.join(tokens[:10])}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]
