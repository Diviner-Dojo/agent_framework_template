# Phase 3 Tooling Decision Brief

**For:** Diviner-Dojo / agent_framework_template — persistent-memory layer
**Suggested repo path:** `docs/research/phase3-tooling-decision-brief.md`
**Date compiled:** 2026-05-11
**Synthesis of:** Claude Phase 3 research run + cross-check against an independent Gemini research run on the same prompt

---

## Intent & Constraints

This brief picks the specific tooling for the sourced-assertion memory architecture settled in Phases 1 and 2. Decision constraints, restated so any reader of this document can audit a recommendation:

- **Solo developer**, Windows primary, WSL2 available, Python primary, VS Code + Claude Code as the daily interface.
- **ADHD piercing-focus profile** — install/setup friction at the start of a session disproportionately kills momentum. "Spin up elegantly" is a hard requirement, not nice-to-have.
- **Portability for downstream framework users** — this becomes part of `agent_framework_template`; whatever's chosen must be easy for someone else to clone-and-run.
- **License-clean preferred** — if the framework is ever published, SSPL/BSL/GPL choices add friction or block adoption. Apache 2.0 / MIT / MPL preferred.
- **Local-first preferred** — cloud services acceptable as references, never as the primary recommendation.
- **Privacy boundary on Insight Journal** — strict; no reflexive external lookups for that domain.
- **Four use cases** must be served (one substrate doesn't have to serve all four):
  1. Framework's own memory of agent discussions
  2. Code-as-concept graph for the framework's own code
  3. Personal Insight Journal (strict privacy)
  4. Howie family history with rich authority cross-validation

**The architectural commitments these recommendations serve** (settled in Phases 1–2, not re-derived here):
- Sources are canonical; everything else is a vehicle for engaging with them.
- Suchness preservation is load-bearing — the path back to source must always be a first-class action, not a buried link.
- Reasoning is the primary artifact; substrate decisions serve reasoning over time.
- The atomic unit is the **sourced assertion** (subject, predicate, object, source-passage with byte-range, framing, embedding, external authority refs).

---

## Headline decisions

If you only read one table, read this one:

| Decision | Recommendation | Confidence |
|---|---|---|
| **Tonight's prototype** | Stack A′: SQLite + sqlite-vec + sentence-transformers + FastMCP, scoped to use case #1 (agent discussions) | High |
| **Production substrate for #1 framework memory at scale** | Migrate from SQLite to **Kuzu-fork** (RyuGraph or LadybugDB) **or ArcadeDB-embedded** when traversal performance bites | Medium — Kuzu-fork governance is unsettled; ArcadeDB-embedded is the safer bet |
| **Substrate for #2 code-as-concept graph** | Kuzu-fork or ArcadeDB-embedded; evaluate **Serena MCP** off-the-shelf first | Medium — Serena needs a one-week hands-on trial before committing |
| **Substrate for #3 Insight Journal** | Stack A′ permanently. Strict privacy boundary enforced architecturally: separate MCP server instance, separate DB file, no authority-resolution tools registered | High |
| **Substrate for #4 Howie family history** | Three-way decision: **ArcadeDB** (multi-model, Apache 2.0) **or Postgres + AGE + pgvector** (familiar SQL story) **or Oxigraph** (native federated SPARQL for authorities). See Section "Per-use-case substrate map." | Medium |
| **Extraction pipeline** | DSPy (Tier 2 template generation with GEPA optimizer) → BAML (Tier 1 high-volume execution) → Instructor (Tier 2 ad-hoc) → Tree-sitter (Tier 0 deterministic) | High |
| **MCP framework** | FastMCP; expose 4–8 focused tools, not 30 fine-grained ones | High |
| **Embedding default** | `all-MiniLM-L6-v2` for prototype and Insight Journal; consider `nomic-embed-text-v1.5` (Matryoshka-downsamplable, Apache 2.0) for scale; `voyage-code-3` for use case #2 only | High |
| **Derived views** | Markdown-from-Python-script → Quartz or MkDocs for general use; **Hugo with data-driven page generation** for Howie family history at scale | Medium |

---

## The license cliff (front-loaded because it shapes everything else)

For a framework you intend others to adopt, license is a first-order constraint, not a footnote. Here's the honest map:

**Apache 2.0 / MIT / MPL — fully redistributable, no downstream friction:**
- SQLite, sqlite-vec, DuckDB (and `vss` extension)
- Kuzu-forks (RyuGraph, LadybugDB, Bighorn) — MIT
- **ArcadeDB** — Apache 2.0, with a public commitment never to relicense
- Apache AGE (Postgres extension) — Apache 2.0
- XTDB v2 — MPL 2.0
- Oxigraph — MIT/Apache
- FastMCP, BAML, DSPy, Instructor, sentence-transformers, Pydantic — all Apache 2.0 / MIT

**Source-available / restrictive — paperwork tax to redistribute:**
- **FalkorDB — SSPL** (NOT BSL 1.1 as some sources state). Anti-cloud clause similar to MongoDB's. Fine for personal/internal use, friction if anyone wants to wrap your framework as a hosted service.
- **Memgraph Community — BSL 1.1** (converts to Apache 2.0 four years after each version's first publication; "non-production" use language in the BSL header is the practical concern for downstream redistribution).

**Copyleft — viral if you distribute binaries:**
- **Neo4j Community — GPLv3** with some AGPLv3+Commons-Clause pieces. Using it yourself is fine; embedding it in software you ship can spread the obligation.

**Practical rule for this framework:** prefer the Apache/MIT/MPL set. The license-clean substrates are not theoretically weaker than the source-available ones — ArcadeDB in particular is a credible peer to FalkorDB and Memgraph on capability, while sitting in the clean column.

---

## Layer 1 — Substrate spec sheets

### Kuzu (archived) + its forks: RyuGraph, LadybugDB, Bighorn, Vela-Engineering/kuzu

| Field | Detail |
|---|---|
| Status | **Original repo archived October 10, 2025.** ArcadeDB's blog asserts Apple acquired Kuzu in that timeframe; this would explain the archival. *Confidence on the Apple acquisition: ~70% — plausible timing but I have not independently verified outside ArcadeDB's marketing.* Three to four active forks exist as of late 2025. |
| License | MIT (all forks) |
| Setup on Win/WSL2 | `pip install` from any fork's wheel. **Single-process embedded library, no service.** Drops into a VS Code Python project as cleanly as SQLite. |
| Query | Cypher. Multi-hop. Columnar storage, factorized joins. No bitemporal. |
| Vector | **Native HNSW vector index extension pre-bundled in 0.11.3** alongside `algo`, `fts`, `json` extensions. |
| MCP | Archived `kuzu-mcp-server`. Community `kuzu-memory-graph-mcp` (jkear) combines Kuzu + sentence-transformers in Python. |
| Schema | Property graph, *required* typed schema (more rigid than Neo4j). |
| Authority refs | URIs as string properties — no federation, no SPARQL. |
| Python ecosystem | First-class. Sync + LangChain + LlamaIndex + Graphiti integration. |
| Maintenance | **Governance is the asterisk.** Original team gone. LadybugDB (Arun Sharma — ex-Facebook/Google) and RyuGraph (Akon Dey — former Dgraph CEO, Predictable Labs) are the two most credible. Vela-Engineering fork specifically addresses concurrent multi-writer for multi-agent use cases. |
| Failure modes | Single-writer constraint in original and most forks (Vela addresses this). Weeks of fork-maintenance history, not years. |
| Portability for downstream users | Excellent *if* the fork survives. The "clone and it works" promise is real here. The "is this still maintained" question is a real liability for a published framework. |
| Use-case fit | Best for **#1** and **#3** (privacy: no service, no network, file-on-disk). Strong for **#2** because columnar + factorized joins fit multi-hop traversal. |

### ArcadeDB (the substrate Phase 3 v1 missed — added on review)

| Field | Detail |
|---|---|
| License | **Apache 2.0** with a public commitment never to relicense. Cleanest license profile in the survey for a *full-featured* substrate. |
| Setup on Win/WSL2 | Docker one-liner (`docker run -p 2480:2480 arcadedata/arcadedb:latest`) OR embedded mode (JVM library inside your application) OR local unpack-and-run. |
| Query | **OpenCypher 25 at 97.8% TCK compliance**, plus SQL, Gremlin, GraphQL, MongoDB QL, Redis API — all against the same data. The Cypher 25 score is high enough that Neo4j Cypher queries typically work as-is. |
| Vector | **Native JVector engine** (DiskANN + HNSW hybrid with SIMD acceleration). Vector embeddings stored directly on graph nodes. |
| MCP | **Built-in MCP server** ships with the database. This is rare. |
| Schema | Multi-model: graph + document + key-value + vector + full-text + time-series in one engine. Schema-flexible. |
| Authority refs | URIs as properties; no native federated SPARQL but `SERVICE`-style patterns possible via HTTP. |
| Python ecosystem | Postgres wire-protocol driver works; HTTP/JSON API; no dedicated `arcadedb` PyPI client as polished as Neo4j's `neo4j` driver — verify before committing. *Confidence on Python client polish: ~75%.* |
| Maintenance | Conceptual fork of OrientDB (lineage from 2009). Backed by Arcade Data Ltd, bootstrapped (not VC-funded — they cite this as the reason the license commitment is credible). |
| Failure modes | JVM footprint (Java 21+). "Low Level Java" coding style is performance-oriented but the JVM dependency is real — similar weight to Neo4j or XTDB. |
| Portability for downstream users | **Strong story** — Apache 2.0 + Docker + embedded mode covers most adoption scenarios. JVM requirement is the friction. |
| Use-case fit | Strong for **#1** at scale, **#2** (embedded mode), **#3** (embedded mode honors privacy), and **#4** (multi-model time-series + graph + vector is genuinely useful for genealogy with valid-time attestations). |

### FalkorDB

| Field | Detail |
|---|---|
| License | **SSPL v1** — source-available, not OSI-open-source. **Note: some references (including Gemini's research run) misreport this as BSL 1.1 — do not propagate that error.** |
| Setup | `docker run -p 6379:6379 -p 3000:3000 falkordb/falkordb` — best out-of-box experience, includes UI on :3000. |
| Query | OpenCypher. Sparse-matrix / GraphBLAS implementation. |
| Vector | Native HNSW. Cosine + Euclidean. Both node and relationship vectors. |
| MCP | Strong via Graphiti (Graphiti MCP server defaults to FalkorDB; ships them together in one Docker container). |
| Python ecosystem | `falkordb` PyPI client; LangChain/LlamaIndex integrations. |
| Maintenance | Active, well-funded, GraphRAG-marketing-focused. |
| Portability for downstream users | One-command Docker is friction-light; SSPL means you should warn downstream users explicitly. |
| Use-case fit | Excellent for **#4** when Docker is acceptable and SSPL is acceptable. Overkill for **#3**. |

### Neo4j Community Edition

| Field | Detail |
|---|---|
| License | **GPLv3** + some AGPLv3 + Commons Clause. Viral implications for redistribution. |
| Setup | Docker fine; native pulls JVM; heaviest of the popular Cypher DBs. |
| Query | Cypher 5 (frozen as of 2025.06) and Cypher 25 (current). |
| Vector | Mature: vector-1.0 (5.11), vector-2.0 (5.18, 4096-dim), vector-3.0 (2025.09). Built-in `ai.text.embed()` Cypher functions. |
| MCP | **Most mature MCP ecosystem in the survey** — `neo4j/mcp` (official) plus `neo4j-contrib/mcp-neo4j` family (`mcp-neo4j-cypher`, `mcp-neo4j-memory`, `mcp-neo4j-data-modeling`). STDIO and HTTP transports. |
| Python ecosystem | Rock-solid `neo4j` driver. LangChain `langchain-neo4j`, LlamaIndex first-class. |
| Portability for downstream users | Docker-friendly but GPLv3 + Community-edition single-instance limitation is real. |
| Use-case fit | Default choice for **#4** if you want maximum ecosystem and accept the GPL. Heavy for **#1**/**#3**. |

### Memgraph

| Field | Detail |
|---|---|
| License | **BSL 1.1** — source-available, converts to Apache 2.0 four years after each version's first publication. |
| Setup | Docker with `--experimental-enabled=vector-search` flag. |
| Query | Cypher (Neo4j-compatible). MAGE algorithm library (40+ algorithms). Streaming ingest. **"Atomic GraphRAG"** single-query pivot+expand+rank. |
| Vector | Native USearch HNSW. Cypher composition with traversal in one query is genuinely elegant. |
| MCP | Memgraph MCP server in their "AI Toolkit"; less ecosystem mass than Neo4j's. |
| Portability for downstream users | BSL header in every source file is a paperwork tax for redistribution. |
| Use-case fit | Strong alternative to Neo4j for **#1** and **#4** with better vector ergonomics. BSL is the cost. |

### Apache AGE (Postgres extension)

| Field | Detail |
|---|---|
| License | **Apache 2.0** — clean. |
| Setup | Docker (`docker run apache/age`) is the easy path. Native build requires matching PostgreSQL 11–18. |
| Query | OpenCypher via `cypher('graph', $$ ... $$)` SQL function calls. Multi-hop yes. No bitemporal. |
| Vector | **None native — pair with pgvector in the same Postgres database.** Same DB, two extensions, one query plan. |
| MCP | No mature AGE-aware MCP server; build with FastMCP + `age` Python driver. |
| Python ecosystem | `age` Python driver (psycopg2-based); LangChain `AGEGraph` works. |
| Maintenance | Apache top-level project; pace slower than commercial alternatives. |
| Failure modes | **Transaction semantics gotcha with psycopg v3 / JDBC** documented in README — graphs can appear created but not visible in new connections without correct autocommit. |
| Use-case fit | Best when **#4** needs serious relational reporting alongside graph queries. Strong for **#1** if Postgres is already in your stack. Heavy for **#3**. |

### XTDB v2

| Field | Detail |
|---|---|
| License | **MPL 2.0** — clean, file-level copyleft. |
| Setup | Docker. JVM under the hood. v2 on Apache Arrow with object-storage separation. |
| Query | **Full bitemporal queries (SQL:2011 + XTQL).** As-of queries across system + valid time without snapshots. SQL via **PostgreSQL wire protocol** — SQL Server-style tooling works. |
| Vector | **None native.** Pair with sqlite-vec or LanceDB. |
| MCP | No first-class server; generic Postgres MCP servers can handle SQL parts via pg-wire. |
| Python ecosystem | Community `pyxtdb` (REST wrapper); plus standard pg drivers via wire protocol. **Less polished than JVM/Clojure-native experience.** |
| Use-case fit | **The only candidate with native bitemporal.** If "what did the agent believe at T about source S" is a real query, XTDB earns its keep. Otherwise overkill. |

### Oxigraph (RDF / SPARQL)

| Field | Detail |
|---|---|
| License | MIT/Apache (Rust crate; `pyoxigraph` Python bindings). |
| Setup | `pip install pyoxigraph` — single wheel. Or `oxigraph serve` CLI for HTTP+SPARQL. |
| Query | **SPARQL 1.1** with Federated Query — `SERVICE <https://query.wikidata.org/sparql>` pulls live context from Wikidata into local queries. |
| Vector | None. |
| MCP | None mature; build with FastMCP. |
| Authority refs | **Native and free** — URIs *are* the data model. Wikidata Q-numbers, GeoNames URIs, VIAF, Pleiades, PeriodO interop with zero conversion. |
| Python ecosystem | `pyoxigraph` solid; `oxrdflib` bridges to RDFLib. |
| Maintenance | Active, single-maintainer-driven (Tpt) — bus-factor concern. |
| Use-case fit | **The dark-horse winner for #4** when external authority interop is the central concern. Bad fit for #2 and #3. |

### DuckDB + vss + DuckPGQ

| Field | Detail |
|---|---|
| License | MIT. |
| Setup | `pip install duckdb` + `INSTALL vss; LOAD vss;`. |
| Query | SQL + SQL/PGQ graph syntax via the DuckPGQ community extension. Analytical, columnar. |
| Vector | `vss` extension with HNSW (USearch). **Persistence experimental** — needs `SET hnsw_enable_experimental_persistence = true`. |
| Use-case fit | Strong for **#2** as an analytical store. Weaker as primary substrate; DuckPGQ is community, not core. |

### Skipped candidates (briefly noted to avoid padding)

- **Datomic** — Closed-source, Clojure-centric.
- **SurrealDB** — Active and polyglot, but BSL-1.1-style license + genuine query-language churn make it poor fit for "set up once, port to others."
- **TerminusDB** — Real community concerns about governance.
- **TypeDB** — Strong-typed but unique query language is a learning-curve mismatch.

---

## Layer 2 — Vector encoding

### Embedding model choice

| Use case | Model | Dim | Why |
|---|---|---|---|
| Prototype (any) | `all-MiniLM-L6-v2` | 384 | Fast on CPU, ~80MB, de-facto baseline in every example in the survey |
| **#3 Insight Journal** (strict local) | `all-MiniLM-L6-v2` or `nomic-embed-text-v1.5` | 384 / 768 | Both fully local, Apache 2.0. Nomic's Matryoshka representation lets you downsample 768→256 if storage matters |
| **#1 / #4** at scale | `nomic-embed-text-v1.5` (local) or `text-embedding-3-small` (API) | 768 / 1536 | Cost/quality sweet spot |
| **#2 code-as-concept** | `voyage-code-3` or `nomic-embed-code` | varies | Code-trained models outperform general-purpose on code retrieval. **Do not use `all-MiniLM-L6-v2` for code-graph** — it was trained on prose |

**Dimension hygiene:** Pick once, write it down, enforce in code. Mixing 384 and 1536 across stores will haunt you.

### What to embed: source passages vs extracted assertions vs both

**Embed both, but with different lifetimes.** Source-passage embeddings are durable (don't change unless the source changes). Assertion embeddings are derived — regenerate them when extraction prompts change. Tag each vector with its provenance (`source_passage_id` + `extraction_run_id`). This is the cheapest insurance against "I changed my prompt and now all my embeddings are slightly wrong."

### Vector storage matched to substrate

| Substrate | Vector path | Verdict |
|---|---|---|
| Kuzu-forks | Native vector extension (pre-bundled in 0.11.3+) | Use it |
| ArcadeDB | Native JVector | Use it |
| FalkorDB | Native HNSW | Use it |
| Neo4j | Native vector-3.0 | Use it |
| Memgraph | Native USearch HNSW | Use it |
| Apache AGE | **pgvector in same Postgres** | Same DB, two extensions |
| XTDB | None — pair with `sqlite-vec` or LanceDB | Friction unless bitemporal matters enough |
| Oxigraph | None — pair with sidecar | Same friction |
| DuckDB | `vss` extension (experimental persistence) | OK for analytical use |
| SQLite | `sqlite-vec` | **Excellent for prototype** |

### Embedded sidecar vector stores

- **sqlite-vec** (Apache 2.0): smallest footprint, plays well alongside an existing SQLite (`metrics/evaluation.db` already in your tree). Brute-force scan currently, ANN on the roadmap. Best fit for the prototype.
- **LanceDB** (Apache 2.0): Rust core, Python binding, columnar Lance format. Persistent, no server, supports versioning, billion-scale claimed. Best technical option when you exceed ~100k vectors.
- **Chroma** (Apache 2.0): Most familiar from LangChain examples; less performant than LanceDB at scale.

### Privacy boundary architectural enforcement for Insight Journal

Concrete enforcement (not a documentation promise):
1. Register a separate Python module (`memory/journal_substrate.py`) that imports a stub `embed_local()` only and refuses to import any API-based embedding client.
2. Use `sentence-transformers` with the model cached to a local path so re-runs never hit the network.
3. The Journal-domain MCP server must not register any authority-resolution tools.

This is an architectural commitment, not just a config flag.

---

## Layer 3 — Extraction pipeline

### Framework selection — opinionated

The structured-output benchmark evidence is clear enough to take a position:

- **Tier 0 (deterministic):** Tree-sitter via `py-tree-sitter` + `tree-sitter-languages` (pre-built wheels for all major languages on Windows). Use for AST extraction from code and structured text.
- **Tier 1 (cheap LLM, high volume):** **BAML.** BAML's schema representation is more token-efficient than DSPy's default JSON schema in published benchmarks; the Schema-Aligned Parser handles malformed JSON without retry — exactly what you want when running thousands of extractions on a small model.
- **Tier 2 (expensive LLM, writes templates):** **DSPy with GEPA optimizer.** Lets the framework optimize prompts against a holdout of human-validated extractions. The output of a Tier-2 run is the prompt+schema artifact Tier-1 then executes.
- **Tier 2 ad-hoc:** **Instructor.** Right default when you don't need template compilation — Pydantic-based, integrates seamlessly with Anthropic SDK and prompt caching.

**The honest caveat:** DSPy is a Stanford research framework that changes rapidly. BAML has its own DSL you'll learn. If you only want one, **BAML is the more stable single bet.**

**Skip Outlines** unless you decide to run a local model for Tier 1 (Outlines constrains generation via logit manipulation, which doesn't work against the Anthropic API — degrades to JSON-mode where BAML's parser is better anyway).

### Validation

Pydantic v2 as the default. Don't add JSON Schema separately unless you need cross-language contracts (BAML's schema files give you cross-language anyway).

### Authority resolution stack

- **Reconciliation Service API** (W3C-incubated spec, used by OpenRefine; Wikidata and VIAF expose reconciliation endpoints).
- **OpenRefine** for batch bootstrapping; don't make it a runtime dependency.
- **qwikidata / SPARQLWrapper** for Wikidata access from Python.
- **pyld** for JSON-LD processing (concrete library for Wikidata/VIAF/Pleiades/PeriodO record handling).

---

## Layer 4 — MCP server tooling

### Available off-the-shelf MCP servers

- **Neo4j**: `neo4j/mcp` (official) + `neo4j-contrib/mcp-neo4j` family. Most mature ecosystem.
- **FalkorDB via Graphiti**: bundled Docker container, episode + entity + semantic + hybrid search tools.
- **Kuzu**: archived `kuzu-mcp-server`; community `jkear/kuzu-memory-graph-mcp` is active.
- **ArcadeDB**: built-in MCP server ships with the database.
- **Apache AGE / XTDB / Oxigraph**: no mature dedicated MCP servers — build with FastMCP.

### Writing your own MCP server

**FastMCP** (jlowin's higher-level wrapper, decorator-style) is the right default unless you hit something it doesn't support, in which case dropping to Anthropic's official `mcp` Python SDK is one import change. Both Apache 2.0.

### Tool design

**Expose 4–8 focused tools, not 30 fine-grained ones.** Servers exposing 50–90 tools can consume 20,000–40,000 tokens just in tool definitions per request. A good shape for the substrate layer:

1. `assert_fact(subject, predicate, object, source_ref, framing)` — write path
2. `query_graph(cypher_or_sparql, params)` — graph read
3. `search_semantic(query, k, filters)` — vector read
4. `get_source(source_ref, byte_range)` — **Suchness preservation primitive: the user can always pull the original passage back**
5. `list_authority_candidates(entity, type)` — Wikidata/VIAF/GeoNames lookup
6. `traverse(start_node, predicate_path, max_hops)` — multi-hop convenience
7. `bitemporal_as_of(query, valid_time, system_time)` — only if XTDB adopted

The Suchness primitive (`get_source`) is a first-class commitment in this architecture, not a metadata lookup. It exists because the user should always be able to *challenge* the symbolic version, not just view it.

### Lifecycle inside VS Code + Claude Code

Claude Code reads `.mcp.json` at the project root. STDIO transports launch on demand. Pattern: substrate DB in `./data/`, MCP server in `./mcp_server/`, `.mcp.json` at project root with relative paths. Opening the VS Code workspace automatically makes the MCP server discoverable.

### Skills + MCP combined pattern

Anthropic's Claude Skills define reusable agent behaviors; MCP servers expose tools. Combined: **Skills define what the agent should do; MCP servers provide the tools to do it.** Example for this framework: a `record_sourced_assertion` Skill describes the workflow; the MCP server provides `assert_fact`, `search_semantic`, `get_source`. The pattern is months old; **don't over-invest** until tool shapes settle.

---

## Layer 5 — Derived view generators

*Confidence on this layer: ~70%. Less freshly sourced than Layers 1–4. Verify before publishing as part of the framework.*

### Recommended pattern

**Treat derived views as code-generated outputs of substrate queries**, written to a `./derived/` directory, consumed by Quartz or MkDocs as ordinary Markdown. Don't try to find one tool that "is graph-aware and publishes" — separate concerns: substrate→Markdown is your Python script, Markdown→site is a static generator's job.

### Generator selection

| Tool | Best fit | Notes |
|---|---|---|
| **Quartz** (jackyzha0, Apache 2.0) | General wiki view, graph-link visualization | Builds static site from Markdown + frontmatter; includes a graph view |
| **MkDocs Material** | Technical documentation | Robust plugin ecosystem; custom hooks let Python query the substrate and inject results at build time |
| **mkdocs-network-graph-plugin** | Interactive graph visualizations within MkDocs | *Verify active maintenance before committing.* |
| **mkrefs** (DerwenAI) | Semantic reference Markdown pages from RDF/TTL knowledge graphs | Useful for #4 if the substrate is Oxigraph or carries RDF exports |
| **Hugo** | **High-volume #4 Howie genealogy with thousands of biography pages** | Data-driven page generation: ingest one `graph.json`, generate N pages, build in seconds. Avoids the "bookkeeping second job" of maintaining thousands of Markdown files |
| **Pandoc + CSL** | Citation-aware rendering of keystone pages | The right tool when you need scholarly formatting (Chicago, MLA, footnotes-with-Ibid behavior) |

### Live/regenerable vs static

The architectural decision isn't which tool — it's whether `derived/` is a **cache** (regenerate on schedule from substrate) or a **snapshot** (regenerate intentionally for publication). For #4 Howie with citations, treat it as snapshot; for #1 framework memory, treat it as cache.

---

## Layer 6 — Code-as-concept graph

*Confidence on this layer: ~70%. Verify by running candidates, not by surveying.*

### Strong evidence available

- Tree-sitter Python bindings work well; ship pre-built wheels.
- Kuzu-forks / ArcadeDB are well-suited to AST-as-graph shape because columnar storage + factorized joins reward 2nd-degree path queries.
- Memgraph's vector search + traversal in one Cypher query is elegant for "find functions semantically similar to this docstring, then traverse to their callers."

### Tool assessments

- **Serena MCP server** (LSP-driven semantic code search): community reports strong. **Recommendation: try standalone for a week before building your own.** If Serena fits, Layer 6 disappears from your build list. Caveat: it inherits LSP quality (Python LSP is good; others vary).
- **Sourcegraph self-hosted**: install footprint is heavier than the rest of your stack; optimized for org-scale code search across many repos. Probably wrong fit for a per-project tool.
- **semgrep / Opengrep** (Apache 2.0): structural pattern matcher with Extended AST. Use as a *complement* to Tree-sitter when you want pattern queries rather than graph traversal. *Verify Opengrep fork status independently.*
- **scip-python** (Apache 2.0): Sourcegraph's SCIP indexer for Python; gives precise symbol-to-symbol references Tree-sitter alone misses (Tree-sitter is syntactic; SCIP/LSP-based tools resolve semantics).
- **Graphify**: implements Karpathy's "codebase as queryable graph" philosophy — Tree-sitter + Claude-driven semantic pass, identifying "Grand Central Stations" (high-connectivity nodes) and "Rationale Nodes" (comments explaining why code exists). Matches the tiered extraction model directly.
- **Aider repo-map / Cline mentions / Continue RAG / Cursor indexing**: cross-cutting observation — they all do (a) Tree-sitter AST → symbol graph, (b) embed docstrings/comments/identifiers, (c) at retrieval time, expand from "what the user mentioned" via the graph by 1–2 hops, (d) feed a budget-bounded slice to the LLM. **This is the same shape your tiered extraction wants.** Reimplementing on top of Kuzu-fork or ArcadeDB + sentence-transformers is a weekend of work.

---

## Layer 7 — External authority resolution

*Confidence: ~70% on rate-limit and licensing specifics; verify before publishing.*

- **Wikidata** — SPARQL endpoint at `query.wikidata.org/sparql`. Rate-limited (roughly 60s CPU per query, ~30 queries/minute per IP — verify current numbers). Python clients: `qwikidata`, `SPARQLWrapper`. Full dump is ~150GB compressed (Qlever is the fastest open-source engine to host it; not realistic for solo developer, not necessary). Data is **CC0**.
- **GeoNames** — Free account required (username), generous limits. **CC BY 4.0** — attribution required when redistributing.
- **VIAF** — Open API, rate-limited but generous.
- **FamilySearch API** — Registration required. **License needs direct verification by Dan** — developer terms allow non-commercial use under specific conditions; storage/redistribution of certain record types is restricted. **Don't ship the framework as a "FamilySearch integration" without reading their current terms.**
- **Pleiades** — CC BY 3.0 / CC BY-SA. JSON+RDF dumps, RESTful API.
- **PeriodO** — CC0. JSON-LD + SPARQL.
- **OpenRefine + Reconciliation API** — W3C-incubated spec is the right runtime contract.

**License compatibility for downstream publication:** GeoNames bundling owes attribution. FamilySearch is the one to read carefully. Rest are CC0/CC BY compatible with most uses.

---

## Layer 8 — Candidate stacks

Six stacks, ordered by friction profile. Effort estimates calibrated to "Dan with strong Python/SQL background, new to graph DBs."

### Stack A′ — Embedded-first / portability-optimized (RECOMMENDED FOR TONIGHT)

- **Substrate:** SQLite with a deliberately graph-shaped schema (`assertions`, `entities`, `relationships`)
- **Vector:** sqlite-vec on the same DB file
- **Graph traversal:** Recursive CTEs (good for 2-hop; expensive at 5+ hops)
- **Extraction:** Instructor + Anthropic SDK to start
- **MCP:** FastMCP, custom Python server

**Good for:** Maximum portability — one file on disk = entire substrate. Zero install for downstream users beyond `pip install`. SQL Server muscle memory transfers 1:1.
**Sacrifices:** Multi-hop traversal performance; will outgrow itself for #4 with deep genealogy queries.
**Effort:** 1 hour to working prototype.
**Walls:** Traversal depth >3 hops or graph >~100k nodes — query latency becomes noticeable.

### Stack A — Embedded graph DB (when A′ outgrows itself)

- **Substrate:** RyuGraph or LadybugDB (Kuzu-fork) — or **ArcadeDB-embedded** as the safer-governance alternative
- **Vector:** Native vector extension (Kuzu) or JVector (ArcadeDB)
- **Extraction:** BAML + DSPy
- **MCP:** FastMCP; ArcadeDB ships one built-in if you go that route
- **Derived view:** Python script → Markdown → Quartz

**Good for:** Real Cypher queries, real multi-hop performance, still embedded (no service).
**Sacrifices:** Kuzu-fork governance risk; ArcadeDB adds JVM dependency.
**Effort:** 2–3 hours.
**Walls:** Multi-agent concurrent writes (Kuzu single-writer; ArcadeDB is fine here).

### Stack B — GraphRAG-optimized (FalkorDB + Graphiti)

- **Substrate:** FalkorDB in Docker
- **Vector:** Native HNSW
- **Extraction:** Graphiti's built-in OR BAML for template control
- **MCP:** Graphiti's bundled MCP server (FalkorDB + MCP in one container)

**Good for:** Fastest GraphRAG validation. One `docker run`, one `pip install graphiti`. UI at :3000.
**Sacrifices:** **SSPL license tax.** Docker dependency. Graphiti's opinionated abstractions (episodes, group_ids).
**Effort:** 1 hour.
**Best for:** #4 Howie if Docker + SSPL are acceptable.

### Stack C — Production / least lock-in (Postgres-anchored)

- **Substrate:** Postgres + Apache AGE + pgvector
- **Vector:** pgvector
- **Extraction:** DSPy + GEPA → BAML
- **MCP:** Custom FastMCP wrapping AGE's `cypher()` + pgvector
- **Derived view:** Quartz or Pandoc+CSL

**Good for:** Boring, durable, Apache 2.0. SQL Server muscle memory transfers directly. Backups, replication, monitoring are solved problems.
**Sacrifices:** AGE transaction-semantics gotcha is real. No bitemporal. Vector + graph in same DB but queried separately.
**Effort:** 2–4 hours.

### Stack C-alt — Production / least lock-in (ArcadeDB-anchored) [NEW]

- **Substrate:** ArcadeDB (Apache 2.0, Docker or embedded)
- **Vector:** Native JVector
- **Extraction:** DSPy + GEPA → BAML
- **MCP:** Built-in ArcadeDB MCP server
- **Derived view:** Quartz / MkDocs / Hugo (Hugo for #4 at scale)

**Good for:** Single engine for graph + document + vector + time-series + full-text. Apache 2.0 forever. Built-in MCP server. OpenCypher 25 + SQL + Gremlin on same data. Embedded mode available.
**Sacrifices:** JVM footprint. Python client ecosystem less polished than Neo4j's (verify before committing). Smaller battle-tested-ops community than Postgres.
**Effort:** 2–4 hours.

**Choice between C and C-alt:** If Postgres is already in your stack, stick with C. If you're picking from a blank slate and want the multi-model story in one engine, C-alt. Both are Apache 2.0 and both are credible.

### Stack D — Bitemporal-first (XTDB)

- **Substrate:** XTDB v2 (Docker, pg-wire protocol)
- **Vector:** sqlite-vec sidecar or LanceDB
- **Extraction:** Same DSPy + BAML pattern
- **MCP:** Custom; generic Postgres MCP works via pg-wire

**Good for:** **Only stack with native bitemporal.** Pg-wire means SQL Server skills are nearly directly applicable.
**Sacrifices:** No native graph (SQL or NetworkX import). No native vector. Smaller community. JVM heritage.
**Effort:** 3–5 hours.
**Walls:** Code-graph and multi-hop traversals awkward in SQL.

### Stack E — RDF-native / authority-interop (Oxigraph)

- **Substrate:** Oxigraph
- **Vector:** sqlite-vec or LanceDB sidecar
- **Extraction:** Same DSPy + BAML pattern
- **MCP:** Custom FastMCP

**Good for:** **Only stack with native federated SPARQL** — Wikidata/VIAF/Pleiades/PeriodO URIs *are* the data model, no conversion needed.
**Sacrifices:** No native vector. No mature MCP server. Single-maintainer bus factor.
**Effort:** 2–3 hours.
**Best for:** #4 Howie family history *only* — wrong shape for #1/#2/#3.

---

## Tonight's prototype recipe

**Stack A′ scoped to use case #1 (framework's own memory of agent discussions).** Don't try to validate all four use cases simultaneously — pick the smallest, fully-yours domain.

### Why this and not Stack A or B for tonight

The friction cost of `pip install kuzu-fork` vs `import sqlite3` is small for *you* tonight, but the portability win of "no extra package" for downstream users is permanent. Stack A′ also keeps the migration path open — when traversal performance bites for #1, migrate the substrate; everything else (extraction, MCP, derived views) stays.

### Project structure

```
agent_framework_template/
├── .mcp.json                          # Claude Code MCP config
├── data/
│   ├── metrics/evaluation.db          # existing
│   └── memory.db                      # new — SQLite + sqlite-vec
├── memory/
│   ├── __init__.py
│   ├── substrate.py                   # SQLite wrapper + schema
│   ├── embeddings.py                  # sentence-transformers wrapper
│   └── extraction.py                  # Instructor + Anthropic SDK
├── mcp_server/
│   ├── __init__.py
│   └── server.py                      # FastMCP server
├── sources/                           # canonical: agent-discussion transcripts
│   └── 2026-05-11_*.md
└── pyproject.toml
```

### Install commands

```bash
# Use uv for speed
pip install uv
uv init
uv add sqlite-vec
uv add sentence-transformers
uv add instructor anthropic
uv add fastmcp pydantic
uv add tree-sitter tree-sitter-languages   # for code-graph later
```

### Substrate code (drop-in)

```python
# memory/substrate.py
"""
SQLite substrate for the sourced-assertion memory layer.

Scope:
    - Defines the schema for sourced assertions, entity authority refs,
      and assertion vectors.
    - Provides a single `init(db_path)` entry point that loads the
      sqlite-vec extension and creates schema idempotently.
    - All other modules in `memory/` import this module to acquire a
      configured connection.

Design notes:
    - One file on disk = the entire substrate. This is the portability
      commitment.
    - The schema is graph-shaped (entities + relationships) but stored
      relationally. Migration to a real graph DB later is one schema
      conversion, not a rewrite of the substrate API.
"""
import sqlite3
import sqlite_vec
from pathlib import Path


def init(db_path: str | Path) -> sqlite3.Connection:
    """
    Open (or create) the memory substrate database and ensure schema exists.

    Parameters
    ----------
    db_path : str | Path
        Filesystem path to the SQLite file. Created if absent.

    Returns
    -------
    sqlite3.Connection
        Connection with sqlite-vec loaded and schema applied. Caller is
        responsible for closing it.

    Notes
    -----
    - `enable_load_extension(True)` is required before loading sqlite-vec.
    - All DDL is idempotent (IF NOT EXISTS), so init() is safe to call
      repeatedly.
    """
    conn = sqlite3.connect(str(db_path))
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.executescript("""
        -- Sourced assertions: the atomic unit of extracted meaning.
        -- The combination of (subject, predicate, object, source_ref)
        -- is the natural key, but we use a synthetic id for join cost.
        CREATE TABLE IF NOT EXISTS assertions (
            id                  INTEGER PRIMARY KEY,
            subject             TEXT    NOT NULL,
            predicate           TEXT    NOT NULL,
            object              TEXT    NOT NULL,
            source_ref          TEXT    NOT NULL,    -- e.g. "sources/x.md#L42-L58"
            framing             TEXT    DEFAULT 'asserts',  -- asserts|questions|denies|considers
            valid_from          TEXT,                -- ISO8601, optional valid-time start
            valid_to            TEXT,                -- ISO8601, optional valid-time end
            recorded_at         TEXT    DEFAULT CURRENT_TIMESTAMP,
            extraction_run_id   TEXT                 -- which extraction pass produced this
        );

        -- External authority refs per entity. Designed in from day one
        -- per the architectural commitment to authority cross-validation.
        CREATE TABLE IF NOT EXISTS entity_authorities (
            entity_name TEXT    NOT NULL,
            authority   TEXT    NOT NULL,            -- 'wikidata' | 'viaf' | 'geonames' | ...
            ref         TEXT    NOT NULL,            -- 'Q42' or full URI
            PRIMARY KEY (entity_name, authority)
        );

        -- Vector index for semantic search over assertions.
        -- 384-dim chosen for all-MiniLM-L6-v2 default; change consistently
        -- if you swap models.
        CREATE VIRTUAL TABLE IF NOT EXISTS assertion_vecs USING vec0(
            assertion_id INTEGER PRIMARY KEY,
            embedding    FLOAT[384]
        );

        -- Lookup index for source-based reads (Suchness preservation
        -- primitive: get_source needs to be fast).
        CREATE INDEX IF NOT EXISTS idx_assertions_source
            ON assertions(source_ref);
    """)
    conn.commit()
    return conn
```

### Embedding helper (drop-in)

```python
# memory/embeddings.py
"""
Local embedding helper for the memory substrate.

Scope:
    - Wraps sentence-transformers with a single `embed(text)` function.
    - Lazy-loads the model on first call to keep import time fast.
    - Defaults to all-MiniLM-L6-v2 (384-dim, ~80MB, runs on CPU).
    - For the Insight Journal use case (#3), this is the ONLY embedding
      path; no API client is imported.
"""
import numpy as np
from sentence_transformers import SentenceTransformer

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    """Lazy-load the embedding model on first use."""
    global _model
    if _model is None:
        _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _model


def embed(text: str) -> np.ndarray:
    """
    Compute a 384-dimensional embedding for `text`.

    Parameters
    ----------
    text : str
        Input text to embed. Will be truncated to the model's max sequence
        length (~256 tokens for all-MiniLM-L6-v2) silently.

    Returns
    -------
    np.ndarray
        Shape (384,), dtype float32. Suitable for direct .tobytes() into
        sqlite-vec.
    """
    return _get_model().encode(text, convert_to_numpy=True).astype("float32")
```

### MCP server with three tools (drop-in)

```python
# mcp_server/server.py
"""
MCP server exposing the substrate to Claude Code and other MCP clients.

Scope:
    - Exposes three tools: assert_fact (write), search_semantic (vector
      read), get_source (Suchness preservation primitive).
    - Uses parameterized SQL to prevent injection.
    - Single connection per process; the substrate.init() schema is
      idempotent so concurrent processes are safe.

Future tools to add (in priority order):
    - query_graph: arbitrary recursive CTE for multi-hop reads
    - list_authority_candidates: Wikidata/VIAF/GeoNames reconciliation
    - traverse: convenience wrapper for multi-hop graph walks
"""
from pathlib import Path
from fastmcp import FastMCP
from memory.substrate import init
from memory.embeddings import embed

# Server identity surfaced to MCP clients
mcp = FastMCP("agent-memory")

# Single shared connection; substrate.init() is idempotent.
DB_PATH = Path("./data/memory.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
db = init(DB_PATH)


@mcp.tool()
def assert_fact(
    subject: str,           # entity making the claim's subject (e.g. "Andrew Howie")
    predicate: str,         # the relationship (e.g. "born_in")
    object: str,            # the value or related entity (e.g. "1735")
    source_ref: str,        # source-passage ref, e.g. "sources/2026-05-11_disc.md#L42-L58"
    framing: str = "asserts",  # asserts|questions|denies|considers — captures rhetorical posture
) -> dict:
    """
    Record a sourced assertion. The source asserts X.

    The verb form is deliberate: the source asserts something; the system
    records that the source asserts it. This preserves the distinction
    between primary-source authority and downstream interpretation.

    Returns the inserted id and the source_ref echo for confirmation.
    Parameterized SQL prevents injection on any of the string inputs.
    """
    cur = db.execute(
        "INSERT INTO assertions(subject, predicate, object, source_ref, framing)"
        " VALUES (?, ?, ?, ?, ?) RETURNING id",
        (subject, predicate, object, source_ref, framing),
    )
    fact_id = cur.fetchone()[0]

    # Embed the symbolic form for later semantic retrieval. Separate from
    # source-passage embeddings (which have a different lifetime).
    vec = embed(f"{subject} {predicate} {object}")
    db.execute(
        "INSERT INTO assertion_vecs(assertion_id, embedding) VALUES (?, ?)",
        (fact_id, vec.tobytes()),
    )
    db.commit()
    return {"fact_id": fact_id, "source_ref": source_ref}


@mcp.tool()
def search_semantic(
    query: str,             # natural-language query, e.g. "Howie's family origins"
    k: int = 5,             # how many top results to return
) -> list[dict]:
    """
    Vector-similarity search over recorded assertions.

    Returns up to k assertions ranked by semantic distance to `query`.
    Each result includes the assertion's full content AND its source_ref —
    the agent is expected to follow up with get_source() when validating.
    """
    query_vec = embed(query)
    rows = db.execute("""
        SELECT a.id, a.subject, a.predicate, a.object, a.source_ref,
               a.framing, v.distance
          FROM assertion_vecs v
          JOIN assertions a ON a.id = v.assertion_id
         WHERE v.embedding MATCH ?
           AND k = ?
         ORDER BY v.distance
    """, (query_vec.tobytes(), k)).fetchall()
    return [
        {
            "fact_id": r[0],
            "subject": r[1],
            "predicate": r[2],
            "object": r[3],
            "source_ref": r[4],
            "framing": r[5],
            "distance": r[6],
        }
        for r in rows
    ]


@mcp.tool()
def get_source(
    source_ref: str,        # passage ref of the form "path/to/file.md#L42-L58"
) -> dict:
    """
    Suchness preservation primitive: pull the original source passage back
    so the user (or the agent) can challenge the symbolic version.

    This is a first-class user-facing action by architectural commitment.
    Symbols are lossy; this tool always returns the path back to the
    canonical truth.

    Parses source_ref of the form "path#Lstart-Lend" and returns the
    requested line range. Returns the full file if no line range given.
    """
    if "#" in source_ref:
        path_part, range_part = source_ref.split("#", 1)
    else:
        path_part, range_part = source_ref, ""

    path = Path(path_part)
    if not path.exists():
        return {"error": f"source not found: {path_part}", "source_ref": source_ref}

    lines = path.read_text(encoding="utf-8").splitlines()

    if range_part.startswith("L") and "-L" in range_part:
        start_str, end_str = range_part[1:].split("-L", 1)
        start, end = int(start_str), int(end_str)
        # Convert to 0-indexed; range is inclusive on both ends.
        passage = "\n".join(lines[start - 1 : end])
        return {"source_ref": source_ref, "passage": passage, "start_line": start, "end_line": end}

    return {"source_ref": source_ref, "passage": "\n".join(lines)}


if __name__ == "__main__":
    mcp.run()
```

### `.mcp.json` at project root

```json
{
  "mcpServers": {
    "agent-memory": {
      "command": "uv",
      "args": ["run", "python", "-m", "mcp_server.server"]
    }
  }
}
```

### Acceptance test for the evening

1. Open the project in VS Code. Launch Claude Code.
2. Drop one real agent-discussion transcript at `sources/2026-05-11_discussion.md`.
3. Ask Claude to use `assert_fact` to record three claims from the transcript, including byte-range source refs.
4. Ask Claude to use `search_semantic` to retrieve assertions related to a paraphrased version of one claim.
5. Ask Claude to use `get_source` to read the original passage for that claim.

If that round-trip works, the architectural shape is validated end-to-end in one evening.

---

## Per-use-case substrate map

| Use case | First choice | Reasoning | Fallback |
|---|---|---|---|
| **#1 Framework memory** | Stack A′ (SQLite + sqlite-vec) starting; migrate to Stack A (Kuzu-fork or **ArcadeDB-embedded**) when traversal performance bites | Embedded, no service, fast iteration. Volume small initially | Stack C-alt at scale |
| **#2 Code-as-concept graph** | **Serena MCP off-the-shelf first** (one-week trial); else Stack A (Kuzu-fork or ArcadeDB-embedded) | If Serena fits, Layer 6 disappears from your build list. If not, columnar storage + factorized joins reward 2nd-degree path queries | DuckDB + DuckPGQ as analytical alternative |
| **#3 Insight Journal** | Stack A′ permanently | Privacy boundary architecturally enforced: separate MCP server, separate DB file, no authority tools registered, local embeddings only | Stack A (Kuzu-fork or ArcadeDB-embedded) if needed — still local, still file-on-disk |
| **#4 Howie family history** | Three-way decision depending on what matters most: <br>**ArcadeDB** (multi-model, Apache 2.0, valid-time via time-series) <br>**Postgres + AGE + pgvector** (SQL ergonomics, familiar) <br>**Oxigraph** (native federated SPARQL, perfect URI-as-data model) | Each has a different strength — see below | Stack B (FalkorDB + Graphiti) if SSPL is acceptable |

### How to pick between the three #4 candidates

| Concern | Winner |
|---|---|
| "I want to query Wikidata in real time from inside my graph query" | **Oxigraph** — native federated SPARQL |
| "I want one engine for graph + document + vector + time-series" | **ArcadeDB** — multi-model in one |
| "I want maximum SQL ergonomics and battle-tested ops" | **Postgres + AGE + pgvector** |
| "I want valid-time / system-time on every assertion" | **XTDB v2** (Stack D) — only native bitemporal |
| "I'm okay with SSPL and want the fastest Graphiti integration" | **FalkorDB** (Stack B) |

**Recommendation: test ArcadeDB against your real Howie dataset for a weekend before committing.** Its time-series + graph + vector combination is theoretically the best fit but the practical Python client maturity is the unknown.

### Can one substrate serve all four?

Yes, if you accept some suboptimality. Best single-substrate choices:
- **Stack A′** does all four acceptably; #4 outgrows it
- **Stack A (Kuzu-fork)** does all four well except #4's authority weakness
- **Stack A (ArcadeDB-embedded)** does all four well — best single-substrate answer
- **Stack C/C-alt** does all four well except #2 (slower for code-graph)

**My recommendation if you want one substrate for everything: ArcadeDB-embedded.** It's the only candidate that combines embedded mode, Apache 2.0, multi-model, native vector, and built-in MCP. The Python client maturity caveat applies.

---

## Confidence notes (per cautious-mode preference)

Below-85% confidence flags called out explicitly:

| Claim | Confidence | Why |
|---|---|---|
| Apple acquired Kuzu in October 2025 | ~70% | Asserted by ArcadeDB's marketing; timing matches the archival but no independent verification surfaced |
| ArcadeDB Python client polish | ~75% | The HTTP/JSON API and pg-wire protocol are confirmed; a polished native `arcadedb` PyPI client comparable to Neo4j's `neo4j` driver is not. Verify before committing |
| Memgraph BSL exact terms | ~80% | BSL 1.1 with 4-year-to-Apache-2.0 conversion confirmed; the exact "non-production" language interpretation for redistribution is worth a lawyer's read |
| FamilySearch API license terms | ~60% | Stated terms exist but change; verify *before* shipping any framework feature that depends on them |
| Wikidata exact rate limits | ~70% | The ~60s CPU and ~30 q/min figures are typical; published numbers shift |
| `mkdocs-network-graph-plugin` and `mkrefs` active maintenance | ~70% | Both real projects; recent commit cadence not verified in this run |
| Opengrep fork of Semgrep is the right alternative | ~70% | Both exist; relative quality not verified hands-on |
| Vela-Engineering Kuzu fork concurrent-write claim | ~75% | Claim exists; haven't tested it |
| FalkorDB's vendor benchmarks (3.5–6× Neo4j, p99 140ms vs 46,900ms) | Treat as marketing ceiling, not floor | Vendor benchmarks on vendor-designed workloads |

**Tools / data sources that would improve accuracy:**
- For Apple/Kuzu: contact a Kuzu-team member directly or wait for press confirmation
- For ArcadeDB Python: run the Stack C-alt prototype for a weekend
- For Memgraph BSL specifics: an IP lawyer's read on the exact license header
- For FamilySearch: register a developer account and read current terms

---

## Open questions (only resolvable by trying)

1. **Which Kuzu fork governs well over 12 months?** Three to four forks now; one or two will dominate by mid-2026. Mitigation: write your substrate wrapper (`memory/substrate.py`) so the fork is one import.
2. **Does ArcadeDB's Python ecosystem hold up in practice?** The pg-wire protocol works; whether a native client matches Neo4j's `neo4j` driver polish is unknown until tested.
3. **Does FalkorDB's GraphRAG p99 advantage over Neo4j hold at your data shapes?** Vendor benchmark; only your data tells you.
4. **Does bitemporal pay rent for #1?** "What did the agent believe at T" sounds great architecturally. Until you've shipped six months of agent discussions and tried to debug a misattribution, you won't know if XTDB earns its cost.
5. **Will Serena MCP eat your code-graph problem?** Quick test: install in your repo, work for a week. If yes, Layer 6 disappears.
6. **At what corpus size does sqlite-vec stop being enough?** Author's benchmarks suggest brute-force fine to ~100k vectors. Scots Worthies (one book) is fine; years of agent discussions eventually needs HNSW.
7. **Does AGE's psycopg v3 transaction-semantics gotcha bite you?** Documented but trips real developers; only your first migration shows it.
8. **Quartz vs MkDocs vs Hugo for the derived view — which feels right?** Build one page in each; the one that doesn't make you want to stop wins.
9. **Skills + MCP — is the combined pattern materially better than MCP tools alone?** Pattern is months old; wins are anecdotal so far.
10. **WSL2 GPU/CUDA memory bottleneck for local embeddings.** If you scale beyond `all-MiniLM-L6-v2` to larger local models, monitor for CUDA IPC handle failures and shared-memory issues between Windows host and WSL2 — real GitHub issues exist (e.g. triton-inference-server/server#8670, microsoft/WSL#7198). For CPU-only embedding workloads, you'll never notice.

---

## Decision sequence (one-step-at-a-time honoring)

Per your cadence preference, here's the sequence I'd propose. Stop after any step; the next decision becomes natural once the current step's results are in hand:

1. **Tonight:** Build Stack A′ end-to-end with `assert_fact`, `search_semantic`, `get_source`. Validate the architectural shape. (Cost: ~2 hours your time.)
2. **Next session:** Add Tier-1 BAML-based extraction. Compile one extraction template from a Tier-2 manual extraction. Validate template-compilation pattern. (Cost: ~3 hours.)
3. **Next session:** Decide whether to evaluate Serena MCP for #2 code-graph before building anything new. (Cost: ~1 hour to install and try.)
4. **Next session:** Add `list_authority_candidates` tool stub (Wikidata SPARQL via `qwikidata`). Validate authority-resolution layer for #4. (Cost: ~2 hours.)
5. **Later this month:** Run a Howie-data weekend on ArcadeDB to test Stack A or Stack C-alt for #4. Decide between ArcadeDB / AGE / Oxigraph. (Cost: one weekend.)
6. **Later:** Migrate #1 from Stack A′ to whichever Stack-A variant wins when traversal performance bites. Substrate wrapper makes this a one-import change.

---

## Sources

**Substrate**
- Kuzu archival and forks: https://github.com/kuzudb/kuzu ; https://github.com/predictable-labs/ryugraph ; https://blog.ladybugdb.com/ ; https://vela.partners/blog/kuzudb-ai-agent-memory-graph-database ; https://gdotv.com/blog/yearly-edge-graph-technology-news-recap-2025/
- ArcadeDB: https://arcadedb.com/ ; https://github.com/ArcadeData/arcadedb ; https://arcadedb.com/embedded.html ; https://arcadedb.com/knowledge-graphs.html ; https://arcadedb.com/blog/open-source-forever-why-arcadedb-will-never-change-its-license/ ; https://arcadedb.com/blog/neo4j-alternatives-in-2026-a-fair-look-at-the-open-source-options/ ; https://arcadedb.com/neo4j.html
- FalkorDB: https://github.com/falkordb/falkordb ; https://docs.falkordb.com/ ; https://docs.falkordb.com/cypher/indexing/vector-index.html ; https://www.falkordb.com/blog/graph-memory-llm-agents-mem0-falkordb/
- Neo4j: https://neo4j.com/product/community-edition/ ; https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/vector-indexes/ ; https://neo4j.com/developer/genai-ecosystem/model-context-protocol-mcp/ ; https://github.com/neo4j-contrib/mcp-neo4j
- Memgraph: https://github.com/memgraph/memgraph ; https://memgraph.com/blog/build-movie-similarity-search-vector-search-memgraph ; https://deepwiki.com/memgraph/memgraph/9-licensing-and-legal
- Apache AGE: https://github.com/apache/age ; https://age.apache.org/age-manual/master/intro/cypher.html
- XTDB: https://xtdb.com/ ; https://github.com/xtdb/xtdb ; https://github.com/countable/pyxtdb
- Oxigraph: https://github.com/oxigraph/oxigraph ; https://pypi.org/project/pyoxigraph/
- DuckDB VSS: https://duckdb.org/docs/current/core_extensions/vss ; https://duckdb.org/2024/05/03/vector-similarity-search-vss

**Vector layer**
- sqlite-vec: https://github.com/asg017/sqlite-vec ; https://alexgarcia.xyz/blog/2024/sqlite-vec-stable-release/index.html ; https://docs.langchain.com/oss/python/integrations/vectorstores/sqlitevec
- Embedding model comparison: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2 ; https://huggingface.co/nomic-ai/nomic-embed-text-v1.5

**Extraction**
- Structured-output benchmarks: https://github.com/prrao87/structured-outputs ; https://github.com/thedataquarry/structured-outputs ; https://kmad.ai/DSPy-Optimization ; https://medium.com/@rajkundalia/how-baml-brings-engineering-discipline-to-llm-powered-systems-983c06d31bf8

**MCP**
- Neo4j MCP: https://github.com/neo4j/mcp ; https://github.com/neo4j-contrib/mcp-neo4j ; https://neo4j.com/blog/developer/claude-converses-neo4j-via-mcp/
- Graphiti: https://github.com/getzep/graphiti/blob/main/mcp_server/README.md

**WSL2 GPU/memory caveat**
- https://github.com/triton-inference-server/server/issues/8670
- https://github.com/microsoft/WSL/issues/7198

---

*End of brief. This document supersedes the original Phase 3 survey by incorporating ArcadeDB as a substrate candidate and the Hugo / MkDocs-plugin additions, while correcting cross-research factual divergences (FalkorDB license is SSPL, not BSL).*
