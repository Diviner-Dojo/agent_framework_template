---
adr_id: ADR-0014
title: "Sourced-assertion memory substrate (Phase 4)"
status: accepted
date: 2026-05-12
decision_makers: [architecture-consultant, security-specialist, qa-specialist, performance-analyst, docs-knowledge, history-analyst, facilitator]
discussion_id: DISC-20260512-131824-phase4-assertion-store-substrate
supersedes: null
risk_level: medium
scope: framework
confidence: 0.89
tags: [substrate, memory, mcp, sqlite, vector-search, suchness, sourced-assertion]
---

## Context

The framework's existing memory architecture has three layers:

- **Layer 1 — Immutable Files** (`discussions/`): event logs + transcripts from agent reviews, deliberations, retros. The canonical record of *what was discussed*.
- **Layer 2 — Relational Index** (`metrics/evaluation.db`): SQLite, event-oriented schema for querying *who said what when*.
- **Layer 3 — Curated Memory** (`memory/`): hand-promoted patterns, decisions, lessons. The canonical record of *what we learned*.

What was missing: a substrate that lets agents reflexively answer *"what does the project know about X?"* — semantic recall over assertions, not event timestamps. The existing telemetry-shaped Layer 2 is the wrong shape for this; promoting every interesting claim by hand into Layer 3 is the wrong cadence.

Phase 1–3 research (2026-04 → 2026-05-11) established the framing:

- **Sources are canonical.** Everything else (graph, wiki, summary, index) is a *vehicle* for engaging with sources.
- **Suchness preservation is load-bearing.** Symbolic abstractions are necessarily lossy; the system must always preserve the path back to the source so users (and agents) can challenge what was abstracted away. Source-resurfacing must be a first-class action, not a buried metadata link.
- **Sourced assertions are the atomic unit.** Each unit is (subject, predicate, object, source_ref, framing) — the *source* asserts something; the system records that the source asserts it. Conclusions are not stored; conclusions are derived views over assertions.

Phase 3 surveyed nine candidate stacks (`docs/research/phase3-tooling-decision-brief.md`) and recommended Stack A′. Phase 4 built it, validated it via end-to-end MCP transport test (DISC-20260512-025323 → DISC-20260512-131824), and surfaced defects the smoke test could not catch (cross-thread SQLite, path traversal). REV-20260512-132622 captured the multi-specialist review; this ADR records the resulting architectural commitments.

## Decision

Adopt **Stack A′** as the per-project memory substrate, with a transport-agnostic `Substrate` class owning all substrate logic.

**Components:**

- **SQLite + sqlite-vec** — file-on-disk store with native vector index. Portability commitment: one file = the entire substrate.
- **sentence-transformers** (`all-MiniLM-L6-v2`, 384-dim, ~80MB, CPU) — local embedding model. No network call at inference; privacy-by-architecture for Insight Journal.
- **FastMCP** — stdio transport exposing three tools to Claude Code.

**Code organisation:**

- **`assertion_store/`** is the substrate package. The `Substrate` class owns schema, connection lifecycle (thread-local SQLite per worker thread), URI canonicalisation, input validation, and three methods: `assert_fact`, `search_semantic`, `get_source`. The substrate is transport-agnostic — a CLI script, batch ingest job, or HTTP API can use it without invoking FastMCP.
- **`mcp_server/`** is a thin transport over `Substrate`. Three `@mcp.tool()` decorators that delegate to the configured instance. Configuration via env vars (`AGENT_MEMORY_DB`, `AGENT_MEMORY_PROJECT_ID`) with script-anchored defaults.

**Three Phase 4 modifications baked in** to keep cross-project futures unblocked:

1. **`project_id` on every assertion.** Indexed at write time. Future shared layer filters by it. No schema migration needed when the shared store appears.
2. **Portable `source_ref` URI.** Form: `project://<project_id>/<relative_path>#L<start>-L<end>`. Source refs from project A become resolvable in project B (when B knows about A) without rewriting.
3. **`scope` parameter in MCP signatures.** Only `"local"` implemented this round; other values raise `NotImplementedError`. Locks the contract; future shared-layer expansion does not break the tool signature.

**Suchness primitive — `get_source`.** First-class architectural action, not a metadata-lookup afterthought. Returns the raw passage at a line range from a `project://` URI. Containment-checked against a substrate-configured allow-list (`source_roots`) of citable directories — defaults to `sources/`, `discussions/`, `docs/`, `memory/`, `src/`. Vehicles (`data/`, `.git/`, `.env`, `.claude/`) are not citable.

## Alternatives Considered

The Phase 3 brief surveyed nine stacks (A, A′, B, C, D, E, F, G, H). Five were assessed in depth; condensed here.

### Stack B: Neo4j (or other native graph DB)
- **Pros**: Native graph traversal; mature query language (Cypher); proven at scale.
- **Cons**: Heavy operational footprint (JVM, separate process); overkill for personal-scale memory; substrate-as-one-file commitment lost.
- **Reason rejected**: The architecture's graph-shape can be expressed relationally without buying a graph engine. Migration path stays open if traversal performance ever bites at the shared-knowledge layer.

### Stack C: DuckDB + custom vector module
- **Pros**: Excellent analytics performance; columnar; can JOIN over Parquet.
- **Cons**: Vector ecosystem less mature than SQLite's; FTS less native; smaller community for assertion-store-shaped workloads.
- **Reason rejected**: sqlite-vec is more proven for this exact shape (small corpus, single-writer, similarity search + relational JOIN).

### Stack D: ChromaDB / Pinecone / Weaviate (vector-first)
- **Pros**: Purpose-built for vector similarity; ergonomic Python APIs.
- **Cons**: Vector-only — assertion metadata (project_id, framing, source_ref, valid-time) has to live elsewhere; second store + a sync problem.
- **Reason rejected**: Architecture treats vector similarity as *complementary* to graph-shaped queries, not primary. Two-store designs always drift.

### Stack E: LanceDB / Qdrant local mode
- **Pros**: Modern; good performance; designed for embedding-first workloads.
- **Cons**: Newer ecosystems; less proven at the "personal substrate" scale; storage layout more complex than a single SQLite file.
- **Reason rejected**: Maturity gap relative to SQLite; portability commitment favours one-file substrate.

### Stack A (parent of A′): pure-Python alternatives (no sqlite-vec)
- **Pros**: Fewer dependencies; no C extension.
- **Cons**: Brute-force similarity over a growing corpus is quadratic; no native index.
- **Reason rejected**: sqlite-vec's incremental cost is one C extension; the benefit is bounded similarity-search latency as the corpus grows.

### Connection-management: module-level connection vs thread-local vs `check_same_thread=False`
- **Module-level (original)**: simplest. Rejected: `sqlite3` forbids cross-thread reuse; surfaced as a runtime defect during Phase 4 canonical MCP test (one SQL call per worker thread → all calls failed).
- **`check_same_thread=False` + explicit lock**: works but trades thread-safety enforcement for a lock the substrate has to reason about.
- **Thread-local (chosen)**: each worker thread opens its own connection lazily; `Substrate.init()` is idempotent so per-thread DDL is a no-op. Cleaner semantics; no lock; matches FastMCP's threading model exactly. Surfaced as a substrate contract derived projects must preserve (Insight Journal, Howie).

### Code organisation: substrate logic in MCP server vs in `assertion_store/`
- **Initial (rejected)**: `mcp_server/server.py` owned thread-local cache, SQL bodies, URI parsing, validation. The substrate exposed only `init()`.
- **Substrate class (chosen)**: `assertion_store/substrate.Substrate` owns everything; `mcp_server/server.py` is a thin transport. Reason: the brief explicitly anticipates other transports (CLI, HTTP, in-process import for batch jobs). Tying the logic to MCP forces every future transport to either reinvent or copy-paste. Refactor cost is small; alternative is silent duplication later.

## Consequences

### Positive

- **Transport-agnostic substrate.** Howie's extraction pipeline (batch script) can import `Substrate` directly without invoking FastMCP. Insight Journal can subclass or instantiate with `promotion_disabled` policy. Future CLI tooling (`python -m assertion_store query "..."`) is one wrapper away.
- **Per-instance configuration.** Multiple substrates can coexist in one process — each with its own DB, project_id, and source-roots allow-list. Critical for the eventual shared-knowledge layer.
- **Suchness as enforceable architecture, not aspiration.** `get_source` is a real tool with parameterized URI parsing, containment-checked file reads, and first-class error returns. The architectural commitment is not "we promise to preserve the source," it is "the source is one tool call away by construction."
- **Designed-in for cross-project future.** `project_id` tag, portable URI, and `scope` parameter are present from day one. The shared-knowledge layer build (after Howie) does not require schema migration — only writing the shared instance.
- **Validated end-to-end.** 27 tests at 97% coverage. Canonical MCP-transport acceptance test (5 steps: assert_fact × 3 → search_semantic paraphrase → get_source round-trip → suchness check) passed cleanly post-fixes.

### Negative

- **Three new external dependencies.** `sqlite-vec` (C extension, full process privileges), `sentence-transformers` (PyTorch transitive chain, ~80MB model download on first use), `fastmcp` (relatively young library). Currently pinned with `>=`, consistent with the project's prior pattern but extending an unbounded transitive chain. Worth re-evaluating during ship.
- **EMBEDDING_DIM is schema-frozen.** Switching embedding models (e.g., to `nomic-embed-text-v1.5` at 768-dim) requires a schema migration and full re-embedding of existing assertions — not a config change. Documented in CLAUDE.md Known Limitations.
- **Vector search post-filters by `project_id`.** sqlite-vec's ANN scan runs first; the project_id constraint is applied at the JOIN. At single-project scale this is correct and efficient. At cross-project (Phase 5+) scale, `k` may under-deliver in mixed corpora — a `TODO(phase5)` is in place to revisit when the shared layer lands.
- **First Python-launched MCP server in the repo.** Prior `.mcp.json` registrations used `npx`. The Python-launch pattern's environment assumptions (cwd, module path) are now load-bearing for the framework.

### Neutral

- **Boundary discipline locked in.** The substrate/transport split is now the framework's pattern; derived projects inheriting this code inherit the pattern. The Substrate class is the substrate's public API; `mcp_server/server.py` is one of (eventually) several transports.
- **Smoke test fidelity lesson captured.** The smoke test passed end-to-end via direct Python calls but missed the SQLite cross-thread defect (only surfaces under MCP transport). Saved as `feedback_smoke_test_fidelity.md` in auto-memory: smoke tests must declare what transport-layer concerns they do not exercise.
- **Path-traversal pattern named.** "Suchness primitives that touch the filesystem must enforce containment" is now a class of vulnerability captured in `memory/bugs/regression-ledger.md`. Future tools that resurface source content inherit the pattern (containment against an explicit allow-list).

## Linked Discussion

See: `discussions/2026-05-12/DISC-20260512-131824-phase4-assertion-store-substrate/`

Related artifacts:
- Phase 1 research: `docs/research/phase1-connection-facilitators.md`
- Phase 3 decision brief: `docs/research/phase3-tooling-decision-brief.md`
- Canonical-test handoff: `docs/dispatches/phase4-canonical-test-handoff.md`
- Review report: `docs/reviews/REV-20260512-132622.md`
- Architecture framing memory: `~/.claude/projects/<slug>/memory/project_memory_architecture_framing.md`
