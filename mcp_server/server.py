"""FastMCP transport exposing the assertion_store Substrate to Claude Code.

This file is a thin transport layer. All substrate logic — schema, connection
management, URI parsing, validation, the three primitives — lives in
``assertion_store/substrate.py``. The MCP tools here are 1-line wrappers that
delegate to the configured Substrate instance.

Why the split: the Substrate class is transport-agnostic. The same logic
can be invoked from a CLI script, a batch ingestion job, an HTTP API, or
unit tests — without going through MCP. See ADR-0014 (forthcoming) for the
boundary commitment derived projects must preserve.

Configuration via environment, anchored to the script location so the server
behaves predictably regardless of where it is launched from:
    - AGENT_MEMORY_DB         — overrides the default db_path
    - AGENT_MEMORY_PROJECT_ID — overrides resolve_project_id()
"""

from __future__ import annotations

import os
from pathlib import Path

from fastmcp import FastMCP

from assertion_store.embeddings import embed
from assertion_store.substrate import Substrate, resolve_project_id

# Script-anchored project root so the server is location-independent.
_SERVER_DIR = Path(__file__).resolve().parent.parent

# Configuration via environment with script-anchored defaults. Derived projects
# (Howie, Insight Journal) and tests can override without editing this file.
# Insight Journal's privacy-by-architecture commitment uses these overrides
# to point at a separate DB.
DB_PATH = Path(os.environ.get("AGENT_MEMORY_DB") or (_SERVER_DIR / "data" / "memory.db"))
PROJECT_ID = os.environ.get("AGENT_MEMORY_PROJECT_ID") or resolve_project_id(_SERVER_DIR)

# Source roots for get_source. Sources are canonical; "vehicles" (data/, metrics/,
# .git/, .env, .claude/) are not citable. Add a directory here only if it carries
# canonical content derived projects would legitimately want to cite as a source.
SOURCE_ROOTS = [
    (_SERVER_DIR / "sources").resolve(),
    (_SERVER_DIR / "discussions").resolve(),
    (_SERVER_DIR / "docs").resolve(),
    (_SERVER_DIR / "memory").resolve(),
    (_SERVER_DIR / "src").resolve(),
]

# The single substrate instance this MCP server fronts. A separate substrate
# (e.g. Insight Journal) would run as its own MCP server process with its own
# Substrate instance pointing at a different DB.
substrate = Substrate(db_path=DB_PATH, project_id=PROJECT_ID, source_roots=SOURCE_ROOTS)

mcp = FastMCP("agent-memory")


def _warm_embedding_model() -> None:
    """Preload the sentence-transformers model before serving.

    Shifts the 1-3s / ~80MB cold-start tax to boot, where latency is expected,
    instead of onto the first MCP tool call.

    This runs at *serve* time rather than import time. As an import-time side
    effect it made this whole module unimportable without the optional extras,
    which silently disabled three regression guards listed in the ledger — the
    thread-local isolation test named in CLAUDE.md and two path-traversal
    checks. Importing the module to exercise its pure functions must not
    require torch. See ADR-0029 and REV-20260728-140000.
    """
    embed("")


@mcp.tool()
def assert_fact(
    subject: str,
    predicate: str,
    object: str,
    source_ref: str,
    framing: str = "asserts",
) -> dict:
    """Record a sourced assertion. The source asserts X.

    The verb form is deliberate: the source asserts something; the system
    records that the source asserts it. This preserves the distinction
    between primary-source authority and downstream interpretation.

    Args:
        subject: The entity the source is asserting about (e.g. "Andrew Howie").
        predicate: The relationship (e.g. "born_in").
        object: The value or related entity (e.g. "1735").
        source_ref: Either a bare ``path#Lstart-Lend`` reference or an
            already-canonical ``project://...`` URI. Bare refs are tagged
            with the current project_id automatically.
        framing: Rhetorical posture — one of ``asserts``, ``questions``,
            ``denies``, ``considers``. Defaults to ``asserts``.

    Returns:
        A dict with the inserted ``fact_id`` and the canonical ``source_ref``
        URI (echoed back for caller confirmation).
    """
    return substrate.assert_fact(subject, predicate, object, source_ref, framing)


@mcp.tool()
def search_semantic(
    query: str,
    k: int = 5,
    scope: str = "local",
) -> list[dict]:
    """Vector-similarity search over recorded assertions.

    Returns up to ``k`` assertions ranked by semantic distance to ``query``.
    Each result includes the assertion's full content AND its ``source_ref``
    URI — callers should follow up with ``get_source()`` when validating an
    assertion against the original passage.

    Args:
        query: Natural-language query (e.g. "Howie's family origins").
        k: How many top results to return. Defaults to 5.
        scope: ``"local"`` filters to the current project_id. Future values
            (``"shared"`` or a list of project_ids) are accepted in the
            signature but not yet implemented.

    Returns:
        A list of dicts, each containing ``fact_id``, ``subject``,
        ``predicate``, ``object``, ``source_ref``, ``framing``, and
        ``distance`` (lower is closer).

    Raises:
        NotImplementedError: If ``scope`` is anything other than ``"local"``.
    """
    return substrate.search_semantic(query, k, scope)


@mcp.tool()
def get_source(source_ref: str) -> dict:
    """Suchness preservation primitive: pull the original source passage back.

    This tool exists so the user (or the agent) can always *challenge* the
    symbolic version of an assertion, not just view it. It is a first-class
    user-facing action by architectural commitment — symbols are lossy, this
    is the path back to canonical truth.

    Args:
        source_ref: A canonical URI of the form
            ``project://<project_id>/<relative_path>#L<start>-L<end>``. The
            line range is optional; without it, the full file is returned.

    Returns:
        A dict with the parsed ``source_ref``, ``project_id``,
        ``relative_path``, ``passage`` (the requested text), and either
        ``start_line``/``end_line`` (when a range was given) or
        ``full_file=True`` (when the whole file was returned). On error,
        returns a dict with an ``error`` key explaining what went wrong.
    """
    return substrate.get_source(source_ref)


if __name__ == "__main__":
    _warm_embedding_model()
    mcp.run()
