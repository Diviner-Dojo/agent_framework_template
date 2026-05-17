"""FastMCP transport exposing the assertion_store Substrate to Claude Code.

A thin layer over ``assertion_store.substrate.Substrate``. Tools are 1-line
wrappers that delegate to a configured Substrate instance — the substrate's
logic (schema, connection lifecycle, URI canonicalisation, validation) lives
in the substrate package, transport-agnostic.

Three tools registered with the ``agent-memory`` MCP server:

- ``assert_fact``     — record a sourced assertion (subject, predicate, object).
- ``search_semantic`` — vector-similarity search over recorded assertions.
- ``get_source``      — Suchness preservation primitive; return the original
                        passage at a ``project://`` URI.

Configuration via environment variables (with script-anchored defaults):

- ``AGENT_MEMORY_DB``         — overrides the default SQLite path.
- ``AGENT_MEMORY_PROJECT_ID`` — overrides ``resolve_project_id()``.

See ADR-0014 for the decision record and the contract derived projects
(Howie, Insight Journal) must preserve — particularly the thread-local
connection model under FastMCP threading.
"""
