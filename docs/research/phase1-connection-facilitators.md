---
title: Phase 1 Research — Connection Facilitators and Agentic Memory Architectures
date: 2026-05-10
status: research-complete
scope: framework architectural exploration
authors: three independent research dispatches (general-purpose subagents), synthesized by Claude Code
not_in_scope:
  - schema design
  - backend selection
  - Howie genealogy work
  - framework backporting
format_note: |
  Format is intentionally loose. The decision about whether durable findings live in narrative-wiki
  form, structured-claims form, or both is itself an open architectural question being captured
  separately in an ADR. Plain markdown for now. Clarity over structure.
---

# Phase 1 Research Report

## How to read this document

Five sections:

1. **Cross-cutting synthesis** — the meta-view. Patterns across dispatches, contradictions, converged vs contested. Read first.
2. **Outside-the-box value candidates** — concepts the source projects may not have fully exploited. Curiosity inputs, not findings.
3. **Risk delta** — does the external evidence make the graph-canonical-with-materialized-wiki bet riskier or less risky? With justification.
4. **Per-dispatch findings** — full spec sheets and detail from each subagent. Read on demand.
5. **Sources** — consolidated.

The dispatch was structured to prevent cross-contamination: three subagents researched in parallel without seeing each other's outputs. Synthesis is the author's; underlying findings are the subagents'.

---

## 1. Cross-cutting synthesis

### What the community has converged on

- **Graph-as-memory-substrate is now mainstream for agentic systems.** Graphiti, Cognee, Mem0, Neo4j Agent Memory, MemoryGraph, OpenMemory, AriGraph, OriginTrail DKG, SwarmVault, Graphify — at least ten public projects, several with active commits in 2026. This is no longer experimental territory.
- **Backend choice is settling.** Neo4j (production, separate server), FalkorDB (embedded, LLM-tuned), and the Kuzu forks are the live options. Most production-leaning systems use a pluggable driver abstraction rather than committing to one backend.
- **LLM-driven extraction is the dominant ingestion pattern.** Most systems extract triples or entity-relation pairs from text via LLM calls. Pure manual entry is rare; pure structured-input is rare; the hybrid LLM-plus-deterministic-pass (Graphify's Tree-sitter + Claude subagents) is the strongest pattern.
- **Bi-temporal validity is widespread.** Graphiti, MemoryGraph, OriginTrail all distinguish "when something was recorded" from "when it was true." Old facts get `invalid_at` rather than deletion. This is closer to standard than the developer may have realized.

### What is still contested

- **Canonical direction.** Markdown-canonical (SwarmVault, Karpathy wiki, agentmemory, Graphify-with-source) and graph-canonical-without-wiki (Graphiti, Cognee, Mem0, AriGraph) are both well-populated camps. The middle position — graph-canonical *with* comprehensive markdown wiki materialization — has essentially no clean reference. The developer's hypothesis on this point holds.
- **Forgetting policy.** Most production systems have none. OpenMemory has sector-typed decay (research-stage rewrite in progress). Research papers describe rich decay policies; production implementations do not. The research–production gap on forgetting is wide.
- **Multi-agent provenance.** Mem0 acknowledges this as a community-known weakness. Cognee has session IDs but limited lineage. Graphiti has episodes tied to source but no agent-identity tagging. The clearest exception is Neo4j Agent Memory's `:TOUCHED` audit-edge pattern, which keeps reasoning lineage in a *separate edge class* from semantic edges. OriginTrail goes furthest by making cryptographic provenance the architectural primitive.
- **Identity vs procedure in agent design.** Peer-reviewed evidence (Zheng et al., PRISM paper) shows personas hurt factual accuracy and help only on alignment/style/safety tasks. CrewAI's identity-first approach has 40k stars and devoted practitioners. The most likely reconciliation: identity scaffolding helps *human developers* (legibility, debuggability, mental model), not LLMs.

### Patterns that appear across all three dispatches

- **The "shared state with typed contract" pattern is everywhere, under different names.** LangGraph calls it state-as-contract. Salesforce calls it Agent Graph. The blackboard architecture research community calls it blackboard. The Linda/tuple-space community has called it shared tuple memory since 1985. The developer's "graph-state-as-contract" framing is reinventing terminology, not a pattern. This is good news — the pattern is well-validated under those other names.
- **Trust boundaries are a different problem from internal coordination.** A2A protocols (Google A2A, AP2, ACP) consistently turn out to be cross-organization tools. Salesforce, SAP, PayPal, Microsoft, Box all use A2A at the org/platform boundary and use orchestrator-with-tools or state-as-contract for internal coordination. The developer's framework is internal — A2A is probably the wrong tool, and recognizing this saves a wasted detour.
- **Cross-project compounding is rare to absent.** Only OriginTrail treats it as a first-class architectural concern. Most systems are per-user or per-tenant. The developer's stated goal of cross-project learning is a real gap in the field, not a solved problem they need to inherit.

### Contradictions worth surfacing

- **Anthropic's internal stance on identity is split.** Skills documentation says procedure ("organized folders of instructions, scripts, and resources" — no persona). Claude Code subagent docs explicitly say "a good subagent is more than a persona" and emphasize tool affordance + success criteria. But Anthropic also publishes a "Persona Selection Model" research piece that takes personas seriously as a theory of assistant character formation. These are not strictly contradictory but they do not give a single canonical answer.
- **CrewAI's role/goal/backstory is praised AND debugged.** Practitioners describe it as the framework's defining strength. But GitHub issue #1048 documents agents ignoring assigned identity in practice, and the framework's logging is widely criticized as the weakest of the major frameworks. Identity scaffolding has UX value but operational fragility.
- **Neo4j Labs publicly frames "markdown filesystem abstraction over Neo4j" as the pattern.** But their public agent-memory repo does not implement a full wiki view — only a `memory.get_context()` summary helper. The major graph-DB vendor is publicly identifying the same gap the developer named, but has not closed it.

---

## 2. Outside-the-box value candidates

These are concepts surfaced by the meta-thinking lens — patterns that source projects may not have fully exploited, or that look transferable beyond the projects that originated them. Candidate frontiers, not findings.

- **Bi-temporal validity + named `invalidated_by` chains.** Graphiti has bi-temporal validity. MemoryGraph adds the directed `invalidated_by` field that names *what fact invalidated this one*. Together they create a navigable provenance chain explaining *why* something stopped being true, not just *when*. Worth considering as a memory-layer primitive.
- **Episodic/semantic node-type split (AriGraph).** Two distinct node classes — one for raw observations, one for extracted semantics — connected by typed provenance edges. Most systems either merge or split via tags; AriGraph splits via node class. Generalizes well beyond text games.
- **`:TOUCHED` audit edges as a separate provenance channel (Neo4j Agent Memory).** Reasoning lineage gets its own edge class, kept distinct from semantic edges. Means you can query "which entities did this reasoning step touch?" without polluting the semantic graph. Cleanest answer in the set to multi-agent provenance.
- **Ontology-grounding as deduplication (Cognee).** Canonical URIs replace LLM-coined entity names, every node tagged `ontology_valid`. Stops "John Smith" and "Smith, John" from becoming separate nodes. Cheap, deterministic, applies regardless of canonical direction.
- **Schema-as-living-markdown-document (SwarmVault).** The schema is a markdown file the LLM reads and revises, rather than code or config. Could sit on top of graph-canonical systems where data is graph-shaped but the schema description is human-and-LLM-readable. Inverts the usual "code is canonical, comments rot" relationship.
- **Tiered durability promotion gates (OriginTrail's WM → SWM → VM).** Working Memory (private, free) → Shared Working Memory (team-visible, TTL-bounded) → Verifiable Memory (on-chain, permanent). Directly mirrors the framework's existing Layer 1/2/3 capture stack — independent convergence on the same architecture from a totally different domain.
- **Constrained operation vocabulary at the write boundary (Mem0's ADD/UPDATE/DELETE/NOOP).** Forcing the LLM to declare *what kind of memory change* it's making creates a free provenance signal without extra plumbing. Memory updates as a typed alphabet, not free-form writes.
- **Graph topology drives wiki page boundaries (Graphify's Leiden communities + "god nodes").** Community detection on the graph computes the wiki's table of contents — the structure of the materialized view is *computed*, not curated. This is the closest existing precedent to the developer's hypothesis and worth a deep read of Graphify's `--wiki` implementation.
- **Sector-typed decay rates (OpenMemory).** Emotional memories age differently from procedural ones. Most systems have either no forgetting or a global decay constant; sector-typed decay maps onto cognitive-science distinctions and may be more honest than uniform policy.
- **Episode-as-provenance-unit (Graphiti).** A unit between raw source and graph fact. Every triple traces back to the episode it was extracted from. Cleaner than per-triple source tagging because the episode preserves context the triple loses.
- **"State-as-contract" + "blackboard" are the names you're already speaking.** If the developer's framework adopts "graph-state-as-contract" as a coordination pattern, renaming to inherit the existing literature (state-as-contract for typed shared state; blackboard for open-shape shared state; tuple space for associative-match shared state) lets future contributors find prior art that already exists. The pattern is sound; the name is reinventing.

---

## 3. Risk delta

The hypothesis being tested: *graph-canonical + comprehensive markdown wiki views materialized from the graph on demand has no major production reference implementation.*

**Confirmed by Dispatch 1.** The closest precedents are partial:

- **Neo4j Agent Memory** — Neo4j's marketing blog describes "markdown filesystem abstraction over Neo4j," but the public repo only provides `memory.get_context()` summaries, not a navigable wiki.
- **Graphify** — Implements `--wiki` materialization from a NetworkX graph using Leiden community detection. But the graph itself is derived from source ingestion, so the graph is not the singular canonical store.
- **OriginTrail DKG** — Graph-canonical with strong cross-agent provenance, but human view is a SPARQL explorer plus chat interface, not a wiki.

So the bet IS the novel direction. The risk delta on it splits into "less risky than estimated" and "riskier than estimated" depending on which sub-question is in view.

### Less risky than estimated

- **The component patterns are all mature.** Graph storage, LLM-driven extraction, markdown rendering — each is individually well-established. The novelty is in the composition, not in any single piece.
- **Major graph-DB vendors see the gap.** Neo4j Labs is publicly framing exactly this pattern. The conceptual move is independently visible to people with deep stakes in graph databases. The developer is not the only person who has noticed.
- **A working partial precedent exists.** Graphify's `--wiki` proves graph→markdown materialization is implementable at production scale. The gap is the wider architectural commitment to graph-as-singular-canonical, not the materialization step itself.
- **The framework's existing four-layer stack already has graph-shape primitives.** SQLite tables for findings, pattern_sightings, agent_effectiveness, lineage_nodes, lineage_file_drift — these have foreign keys, agent identity, edges to discussions. Migration to a true graph backend is structurally smaller than starting from nothing.

### Riskier than previously named

- **Wiki staleness policy has no clean precedent.** When does the materialized wiki regenerate? On commit? On query? Hybrid? Nobody in the surveyed set has answered this for a comprehensive wiki view. The materialization frequency vs cost vs freshness tradeoff is a novel design problem the developer would be inheriting.
- **Wiki page boundary determination is harder than it looks.** Graphify uses Leiden community detection; the broader space (Louvain, Infomap, hierarchical clustering) is underexplored as page-structure driver. The developer would be making structural choices the field hasn't settled.
- **Multi-agent provenance is everyone's weak spot.** If the developer wants this to work robustly, they're inheriting an unsolved problem. The Neo4j `:TOUCHED` pattern and OriginTrail's cryptographic provenance are the only strong precedents — and they solve different sub-problems.
- **Cross-project compounding is virtually unaddressed.** OriginTrail's federation model is the only first-class architectural treatment in the set. Tagging conventions and per-tenant scoping are not adequate substitutes if cross-project learning is a stated goal.

### Risk deltas on adjacent decisions surfaced by the research

- **The 12-named-specialist agent design has weak empirical support.** Peer-reviewed work (Zheng et al., PRISM) suggests personas don't reliably improve factual outcomes and may hurt some. CrewAI's success likely reflects developer-ergonomics benefit, not LLM-performance benefit. The framework's hybrid of Values + procedural Domain Lens has *not* been empirically tested as a distinct pattern — so the question is under-evidenced, not settled. The developer may be over-investing in identity scaffolding for LLM performance reasons that the literature doesn't support, while plausibly retaining real benefit for human-developer-facing legibility.
- **A2A protocols are probably the wrong tool for the framework's internal coordination.** A2A is consistently used at cross-organization trust boundaries. The framework is internal multi-specialist coordination. If A2A was on the candidate list for internal use, this research suggests removing it and using state-as-contract / blackboard / orchestrator-with-tools patterns instead.
- **"Graph-state-as-contract" terminology should be retired in favor of inherited names.** State-as-contract (LangGraph), blackboard (Hearsay-II), tuple space (Linda) are the established names for the developer's pattern. Renaming preserves access to ~40 years of prior research and signals to future contributors what shoulders they're standing on.

### Net assessment

The bet is **less risky than feared on backend choice, pattern implementability, and vendor signal**. It is **more risky on questions the developer had not fully named**: materialization staleness, wiki page boundary computation, multi-agent provenance design, cross-project compounding.

The procedure-vs-identity question is a wholly separate decision worth surfacing. The "graph-state-as-contract" renaming is a low-cost win.

---

## 4. Per-dispatch findings

### Dispatch 1 — Connection facilitators in agentic systems

The territory splits along the line the developer drew. Markdown-canonical systems (SwarmVault, Karpathy LLM Wiki, agentmemory, obsidian-wiki, Graphify) treat the graph as a derived index or export — they generate the graph from markdown via LLM extraction. Graph-canonical systems with no comprehensive markdown view (Graphiti/Zep, Cognee, Mem0, Neo4j Agent Memory, AriGraph, OpenMemory, MemoryGraph, OriginTrail DKG) dominate the research and production side — they query the graph directly via Cypher/SPARQL/MCP tools. The third pattern — graph-canonical with comprehensive materialized markdown wiki views on demand — has essentially no clean reference implementation. Closest partial precedents: Neo4j Agent Memory (blog-level framing only), Graphify's `--wiki` (graph isn't the singular canonical store), OriginTrail (SPARQL UI, not wiki).

#### Graphiti (getzep)

- **Link**: https://github.com/getzep/graphiti
- **Canonical direction**: graph-canonical
- **Backend**: Neo4j (default), FalkorDB, Kuzu, Amazon Neptune (pluggable driver)
- **Schema**: Property graph with hybrid prescribed-and-learned ontology
- **Ingestion**: Incremental, event-driven LLM extraction from "episodes"; no batch recomputation
- **Human view**: None. Query API only
- **Cross-project compounding**: Per-tenant/per-user; not designed for cross-project
- **Provenance**: Every fact traces to source episode; no explicit multi-agent ownership
- **Lifecycle**: Bi-temporal — facts have validity windows; `invalid_at`, not delete
- **Status**: Active. v0.29.0 April 2026. Apache-2.0
- **Failure modes**: Requires LLM with structured-output support; default semaphore=10 for rate limits
- **Frontier candidates**: Bi-temporal validity windows; episodes as provenance unit; "invalidate, don't delete" pattern

#### Cognee (topoteretes)

- **Link**: https://github.com/topoteretes/cognee
- **Canonical direction**: graph-canonical (with vector augmentation)
- **Backend**: Kuzu default — **Kuzu archived October 2025, live concern**; pluggable to Neo4j and others
- **Schema**: Ontology-grounded property graph; canonical URIs replace LLM-derived names
- **Ingestion**: `cognify` pipeline — LLM extraction from 30+ data connectors
- **Human view**: None documented
- **Cross-project compounding**: Dataset parameter scoping
- **Provenance**: Agentic user/tenant isolation; OTEL collector for audit; session IDs
- **Lifecycle**: Manual `forget(dataset=...)` only; no TTL
- **Status**: Very active. v1.0.9 May 2026, 7,164 commits. Apache-2.0
- **Failure modes**: Kuzu archival creates backend uncertainty
- **Frontier candidates**: Ontology-as-deduplication; cognify-as-pipeline-stage distinct from store

#### Mem0 / Mem0-Graph

- **Link**: https://github.com/mem0ai/mem0
- **Canonical direction**: hybrid — vector-canonical with optional graph overlay
- **Backend**: Vector store (Qdrant) + optional graph (Neo4j, FalkorDB, Memgraph, Neptune Analytics)
- **Schema**: Property graph with directed labeled edges; no enforced ontology
- **Ingestion**: Per message-pair extraction; LLM tool-call mechanism with ADD/UPDATE/DELETE/NOOP operations
- **Human view**: None
- **Cross-project compounding**: Per-user isolation
- **Provenance**: Community-acknowledged gap
- **Lifecycle**: Conflict detection + relationship pruning at update time
- **Status**: Active. Apache-2.0
- **Failure modes**: "Context blindness" without graph overlay; provenance weak spot
- **Frontier candidates**: ADD/UPDATE/DELETE/NOOP as constrained memory verbs

#### Neo4j Agent Memory (neo4j-labs)

- **Link**: https://github.com/neo4j-labs/agent-memory
- **Canonical direction**: graph-canonical; **partial markdown-as-abstraction per Neo4j blog**, but public repo only implements `memory.get_context()` summaries
- **Backend**: Neo4j (5.20+ required)
- **Schema**: POLE+O — Persons, Organizations, Locations, Events + Observations
- **Ingestion**: Multi-stage — spaCy + GLiNER for NER, GLiREL for relations, LLM fallback, Wikipedia/Diffbot enrichment
- **Human view**: `memory.get_context()` returns context summary; not a wiki
- **Cross-project compounding**: `user_identifier=` multi-tenant scoping
- **Provenance**: v0.2 introduces `:TOUCHED` audit edges from reasoning steps to entities; `TraceOutcome` indexing — **strongest explicit reasoning-trace provenance in the set**
- **Lifecycle**: Short-term / long-term / reasoning memory tiers
- **Status**: Active, experimental. Apache-2.0
- **Failure modes**: Async-only API; Neo4j 5.20+ required
- **Frontier candidates**: `:TOUCHED` edges as separate provenance channel; POLE+O entity taxonomy as starter ontology

#### SwarmVault (swarmclawai)

- **Link**: https://github.com/swarmclawai/swarmvault
- **Canonical direction**: markdown-canonical (Karpathy pattern); graph is derived `state/graph.json`
- **Backend**: Local JSON; optional Neo4j/GraphML/Obsidian canvas as export
- **Schema**: Per-vault `swarmvault.schema.md` — human-editable, co-evolved with LLM
- **Ingestion**: 30+ source formats → AST/vision/transcription → markdown → parsed for graph
- **Human view**: Markdown wiki IS the canonical artifact
- **Cross-project compounding**: Managed source registration
- **Provenance**: Edges tagged `extracted` / `inferred` / `ambiguous`; task ledger in `state/memory/tasks/`
- **Lifecycle**: Approval queues (`wiki/candidates/` before promotion)
- **Status**: Very active. v3.14.0 May 2026. MIT
- **Frontier candidates**: Candidate-staging pattern; schema-as-markdown-file

#### Graphify (safishamsi)

- **Link**: https://github.com/safishamsi/graphify
- **Canonical direction**: hybrid — NetworkX graph is working canonical structure, materialized from source; markdown wiki is export view
- **Backend**: NetworkX in-memory; exports to Neo4j, GraphML, SVG
- **Schema**: No explicit schema; flexible across 20+ languages plus docs/PDFs/images/video. Edges tagged with confidence
- **Ingestion**: Two-pass — Tree-sitter AST extraction + Claude subagents for PDFs/markdown/images
- **Human view**: `--wiki` flag generates "agent-crawlable markdown wiki" with `index.md` per "god node" and per community (Leiden) — **closest in the set to graph→markdown materialization**
- **Cross-project compounding**: Per-folder vault
- **Provenance**: Confidence tagging on every edge
- **Lifecycle**: Not documented
- **Status**: Active. v0.7.13 May 2026. MIT
- **Frontier candidates**: Leiden community detection as wiki page boundary driver; "god nodes" as high-centrality wiki landing pages

#### OpenMemory (CaviraOSS)

- **Link**: https://github.com/CaviraOSS/OpenMemory
- **Canonical direction**: graph + relational hybrid
- **Backend**: SQLite default; PostgreSQL alternative
- **Schema**: Hierarchical Memory Decomposition — five sectors (episodic, semantic, procedural, emotional, reflective); sparse single-waypoint graph
- **Ingestion**: Connectors for GitHub, Notion, Google Drive, web; migration tool imports from Mem0/Zep/Supermemory
- **Human view**: None documented
- **Cross-project compounding**: Not addressed
- **Provenance**: "Explainable traces" with waypoint graphs; details limited
- **Lifecycle**: Adaptive decay per sector — salience + recency + coactivation composite
- **Status**: v1.2.3 December 2025. Apache-2.0. **Repository banner: "currently being fully rewritten"**
- **Frontier candidates**: Per-sector decay rates; single-waypoint sparse graph as deliberate sparseness

#### OriginTrail DKG v9/v10

- **Link**: https://github.com/OriginTrail/dkg-v9
- **Canonical direction**: graph-canonical (RDF triples)
- **Backend**: RDF store via `@origintrail-official/dkg-storage` abstraction; peer-to-peer; on-chain anchoring
- **Schema**: RDF/OWL ontology; SPO triples
- **Ingestion**: `assertion import-file` accepts PDF/DOCX/HTML/Markdown; Working Memory lifecycle: `created → promoted → published → finalized | discarded`; `_meta` graph for audit
- **Human view**: Dashboard with SPARQL explorer + chat memory interface; graph visualization. No wiki materialization
- **Cross-project compounding**: **Defining feature** — cryptographically verifiable, peer-to-peer, queryable by any agent on network
- **Provenance**: **Strongest in the set.** Cryptographic provenance per claim; M-of-N consensus via "endorsed → consensus-verified" trust levels
- **Lifecycle**: Three-tier — Working Memory (private, free), Shared Working Memory (team-visible, TTL), Verifiable Memory (on-chain, permanent)
- **Status**: Active. 2,755 commits. Apache-2.0. "Release candidate on testnet"
- **Failure modes**: Testnet faucet best-effort; SWM gossip payloads signed but unencrypted
- **Frontier candidates**: Cryptographic provenance vs semantic provenance; tiered durability (WM → SWM → VM); consensus-verified-fact class; Knowledge Assets as unit of shared memory

#### AriGraph (AIRI Institute)

- **Link**: https://github.com/AIRI-Institute/AriGraph
- **Canonical direction**: graph-canonical (research implementation)
- **Backend**: NetworkX (via `TripletGraph`)
- **Schema**: Property graph with **two node classes — semantic (entities) and episodic (full observations)**. Episodic edges link episodic vertices to extracted triplets
- **Ingestion**: Per agent timestep — episodic vertex with full observation; LLM extracts SRO triplets to update semantic graph
- **Human view**: None — research artifact
- **Cross-project compounding**: Not designed for it
- **Provenance**: Not addressed
- **Lifecycle**: Not documented
- **Status**: 157 commits. MIT. Research repo (text-based games)
- **Failure modes**: Multi-hop reasoning weak at small models (14.5% EM with GPT-3.5)
- **Frontier candidates**: Episodic/semantic node-class split as explicit modeling choice; episodic edges as typed provenance channel

#### MemoryGraph

- **Link**: https://github.com/memory-graph/memory-graph
- **Canonical direction**: graph-canonical
- **Backend**: SQLite default; Neo4j, FalkorDB/FalkorDBLite, Memgraph, **LadybugDB (Kuzu fork)**, Turso, cloud
- **Schema**: Property graph with seven relationship categories (causal, solution, context, learning, similarity, workflow, quality) and six memory types
- **Ingestion**: MCP tool-driven; requires explicit agent prompting (not autonomous)
- **Human view**: None
- **Cross-project compounding**: Tagging + project-scoped config; visibility levels (private/project/team/public)
- **Provenance**: Optional multi-tenancy with tenant isolation (v0.10.0+); auth integration planned
- **Lifecycle**: **Bi-temporal tracking with `valid_from`, `valid_until`, `recorded_at`, `invalidated_by`** — time-travel queries supported
- **Status**: Active. v0.12.4 February 2026. MIT
- **Failure modes**: Documented — circuit breaker for network failures; ephemeral storage mitigation; multi-tenancy phased
- **Frontier candidates**: `invalidated_by` lineage as directed invalidation graph; seven-category relationship ontology as starter for code-agent work

#### Coverage gaps (Dispatch 1)

- Graph-canonical systems that materialize comprehensive markdown wiki views on demand from the graph as their primary human-facing surface — **the pattern the developer hypothesized has no clean reference**
- Production graph-canonical systems built on a Kuzu fork (Bighorn, LadybugDB) as primary backend
- Multi-project / cross-codebase graph memory with explicit federation primitives (OriginTrail is the only one)
- Agent memory graphs with explicit "wiki page boundary inferred from graph topology" as a documented pattern
- Schema-as-living-document patterns in graph-canonical systems (SwarmVault has it in markdown-canonical)
- Decay policies combining temporal validity, semantic centrality, and access frequency in production

---

### Dispatch 2 — A2A protocol usage and graph-state-as-contract pattern

**A2A is now Linux Foundation-hosted with 150+ supporting organizations one year in, but the trust boundary it solves is consistently described as cross-organization or cross-platform — not internal team-of-agents coordination.** Inside organizational boundaries, the dominant production patterns are (1) orchestrator-with-isolated-subagents (Anthropic, OpenAI Swarm handoffs, SAP Joule routing inbound through its orchestrator), and (2) shared state via typed schema (LangGraph StateGraph, plus blackboard implementations on top of it). The exact term "graph-state-as-contract" does not appear in public sources; the canonical name in the LangGraph community is "state-as-contract" or "shared state contract," and the underlying CS concept maps cleanly to Linda tuple spaces (1985) and the classical blackboard architecture (Hearsay-II). At least one open-source framework — `agent-contracts` on GitHub — names this explicitly "Contract-Driven Development for LangGraph."

#### A2A in production projects

**Salesforce Agentforce** — Cross-platform/inter-org A2A. Internal coordination uses "Agent Graph" — a topology of agentic nodes with "contracts between them" governing information flow. Active, production.

**SAP Joule** — Cross-org A2A. Inbound routed through the orchestrator (Joule) via Agent Hub; SAP explicitly keeps the orchestrator as the only A2A-exposed surface. Internal: orchestrator-with-tools. Active, production.

**Deutsche Bank** — Cited as the cleanest A2A-as-internal-coordination example (40+ A2A agents for trade reconciliation, KYC, regulatory reporting). **No primary engineering source found.** Repeated across A2A press coverage but unverifiable.

**PayPal (AP2)** — Cross-org payment authorization via AP2 (A2A extension). PCI scope minimized by keeping credentials in PayPal wallet agent. Active, launched September 2025.

**Box (Google Cloud)** — Cross-vendor — Box content agents invokable from Google Workspace/Vertex agents via A2A.

**Hector** — A2A-native Go platform; self-hosted; uses A2A as wire protocol throughout (internal subagents addressed same way as external — unusual).

**E.D.D.I., ContextForge (IBM), UnifAI (Red Hat)** — Orchestration middleware federating MCP and A2A services. Gateway is the boundary.

**Microsoft Agent Framework (.NET)** — A2A v1 first-class for cross-platform communication.

#### Pattern observed

Where A2A is *not* used for internal coordination, the dominant alternatives:
- **Orchestrator-with-tools** (SAP Joule, OpenAI Swarm with handoffs, Anthropic lead-researcher dispatching subagents synchronously)
- **Shared state via typed schema** (LangGraph StateGraph; Salesforce Agent Graph as a variant)
- **Conversational message history** (AutoGen GroupChat, CrewAI sequential context passing)

#### Graph-state-as-contract — direct answer

**The exact phrase "graph-state-as-contract" is not a recognized term in public literature.** Zero hits. The phrase describes a well-established pattern under several canonical names:

| Canonical name | Where used | What it is |
|---|---|---|
| **State as a contract** / **shared state contract** | LangGraph community | Typed state schema (TypedDict/Pydantic) that all nodes read/write; schema IS the inter-agent contract |
| **Blackboard architecture** | AI research since 1980s; modern revival in bMAS (arXiv:2507.01701) | Global shared workspace; agents communicate solely through it |
| **Tuple spaces / Linda** | Coordination languages since Gelernter 1985 | Shared associative memory; processes coordinate by `out`/`in`/`rd` on tuples |
| **Contract-Driven Development for agents** | `agent-contracts` GitHub | "Contract-driven architecture for building LangGraph agents with declarative node definitions" |
| **Agent Graph** | Salesforce Agentforce engineering | "The graph of agents — what agentic nodes exist, the contracts between them, and the transitions" |

The developer's term most naturally maps to **LangGraph's "state-as-contract"** when state is structured (TypedDict/Pydantic) and contract-enforced, or to **blackboard** when state is more open-ended. If "graph" refers to a knowledge/property graph (not workflow DAG) as the shared state representation, that is a less common but real combination — equivalent to a blackboard whose internal representation is graph-shaped rather than tuple-shaped.

#### Pattern comparison

| Pattern | Coordination medium | Schema enforcement | Used by |
|---|---|---|---|
| LangGraph StateGraph | Typed shared state object; deltas with reducers | Strong (TypedDict/Pydantic) | LangGraph, Salesforce Agent Graph |
| Blackboard | Global write-anywhere workspace | Variable; classical = none | Hearsay-II; bMAS, LbMAS |
| Linda / tuple spaces | Associative tuple matching | Tuple templates | Beads, AgentFS, OpenHands |
| CrewAI shared context | Sequential task outputs | None | CrewAI |
| AutoGen GroupChat | Full conversation history | None | AutoGen |
| OpenAI Swarm handoff | Shared messages + `transfer_to_X` | None on shape | OpenAI |
| Anthropic multi-agent research | **No shared state** — lead persists to Memory only | N/A — strict isolation | Anthropic research system |

#### Open questions

- Deutsche Bank's 40+ internal A2A agents — no primary engineering source
- Whether any production system uses a literal graph database (Neo4j etc.) as shared workspace for multi-agent coordination (scoped out per dispatch boundary)
- Salesforce Agent Graph internal architecture — whether contracts are typed-schema-enforced, runtime-validated, or convention
- Whether developer's "graph" refers to workflow-DAG (LangGraph) or knowledge-graph (Neo4j) sense — answer differs by which

---

### Dispatch 3 — Procedure-only vs identity-rich agent design

Major production frameworks split into three camps. **Identity-rich**: CrewAI (most prominent), AutoGen (by convention), Letta/MemGPT (by architecture). **Procedure-only**: LangGraph, smolagents, DSPy, Anthropic Skills. **Hybrid/lightweight**: OpenAI Swarm/Agents SDK, Claude Code subagents — identity is optional decoration around tool-and-instruction core. The empirical literature is contested but converging on a task-dependent answer: personas tend to **hurt accuracy on knowledge-retrieval tasks** and **help on alignment, style, safety, format-following**. No peer-reviewed ablation has isolated whether multi-agent persona framing produces better team-level outcomes than procedurally defined specialists — the question is under-studied.

#### Framework positions

**CrewAI** — Identity-rich. Three required attributes: `role`, `goal`, `backstory`. Self-described as "role-playing autonomous AI agents." Practitioners praise as defining strength; GitHub issue #1048 documents agents ignoring identity in practice. Critique: "task-driven rather than agent-driven" — role framing partly cosmetic.

**AutoGen (Microsoft)** — Identity by convention, procedure by API. Persona usage is a tutorial convention, not enforced by the API. Superseded by Microsoft Agent Framework.

**LangGraph** — Procedure-only, explicitly. "Aims for little to no abstraction at all, instead focusing on control and durability." No `role` or `backstory` field. Authors describe philosophy as "diametrically opposed" to AutoGen-style persona-driven coordination.

**Letta / MemGPT** — Identity-rich by architecture. Persona is a first-class memory primitive (`Persona` core memory block) the agent rewrites over time. Identity persistence across sessions IS the product.

**Anthropic Skills** — Procedure-only, explicitly. Skills are "organized folders of instructions, scripts, and resources." Onboarding-guide-for-a-new-hire analogy — procedural knowledge and organizational context, not identity.

**Claude Code subagents** — Description is routing hint, not persona. Anthropic explicitly: "a good subagent is more than a persona." Tool affordance + success criteria emphasized.

**OpenAI Swarm / Agents SDK** — Lightweight. Persona explicitly optional. Defining innovation is handoffs, not identity.

**smolagents** — Procedure-only. Minimalism is the bet. Intellectual content in action representation (code agents), not identity.

**DSPy** — Procedure-only, anti-prompt. Signatures replace handwritten prompts (including personas) with declarative I/O specs. ReAct accuracy 24% → 51% via MIPROv2 optimization, no persona engineering.

#### Evidence quality

**Strong (peer-reviewed, large-N):**
- Zheng et al., "When 'A Helpful Assistant' Is Not Really Helpful" (arXiv:2311.10054): 162 personas × 2,410 MMLU questions × 9 LLMs. **Adding personas does not improve performance** vs no-persona control. **No automated strategy for picking the right persona beat random selection.** The paper reversed its initial conclusion after broader testing.
- "Expert Personas Improve LLM Alignment but Damage Accuracy" (arXiv:2603.18507, PRISM): expert prompts **consistently improve alignment-dependent tasks** (safety, preference) but **reliably damage pretraining-dependent knowledge retrieval**.
- Learn Prompting's 12-persona × 2000-MMLU: "idiot" persona outperformed "genius"; all clustered near baseline.

**Medium (single study, narrower task):**
- "Evaluating Persona Prompting for QA Tasks": multi-agent persona setups **did not outperform single-agent** and sometimes introduced more hallucinations. Persona gains appeared only for open-ended questions, not factual.
- Kong et al., "Better Zero-Shot Reasoning with Role-Play Prompting": role-play + chain-of-thought → 53% → 63% on math. **Couples role and procedure, no clean isolation.**

**Weak (anecdote/vendor claim):**
- CrewAI "agents perform significantly better when given specialized roles" — claimed in docs, not supported by published ablation
- Practitioner blog posts that role/goal/backstory is "surprisingly effective"

#### Contested or unclear

- **Whether persona/identity helps in multi-specialist orchestration specifically** (the developer's case) — no direct ablation found. The Zheng study tests single-agent persona on factual QA. The multi-agent QA study tested roundtable, not specialist-panel-with-domain-lens.
- **Whether "load-bearing beliefs" (Values sections) function like personas or like procedural constraints.** A value that says "prefer X over Y" arguably encodes procedure (a tiebreaker rule) under identity framing. The persona literature does not test this hybrid.
- **Whether the Domain Lens pattern (reasoning sequence applied before analysis) is independent of identity framing.** Kong et al. couples role and procedure; no clean isolation.
- **Whether persona robustness varies by model generation.** Informal reports suggest persona effects diminish with larger/newer models; no systematic longitudinal study.
- **Whether identity-rich definitions improve human-developer outcomes (legibility, debuggability) even if they don't improve model outputs.** CrewAI's ~40k stars suggest a real mental-model benefit to humans separate from any LLM-side gain. No study isolates this effect.
- **Anthropic's own position is internally split.** Skills says procedure; subagent docs say "more than a persona"; Persona Selection Model research takes personas seriously as theory of assistant character.

---

## 5. Sources

### Connection facilitators (Dispatch 1)

- [Graphiti — getzep/graphiti](https://github.com/getzep/graphiti)
- [Cognee — topoteretes/cognee](https://github.com/topoteretes/cognee)
- [Neo4j Agent Memory — neo4j-labs/agent-memory](https://github.com/neo4j-labs/agent-memory)
- [SwarmVault — swarmclawai/swarmvault](https://github.com/swarmclawai/swarmvault)
- [Graphify — safishamsi/graphify](https://github.com/safishamsi/graphify)
- [From Karpathy's LLM Wiki to Graphify (Analytics Vidhya)](https://www.analyticsvidhya.com/blog/2026/04/graphify-guide/)
- [OpenMemory — CaviraOSS/OpenMemory](https://github.com/CaviraOSS/OpenMemory)
- [OriginTrail DKG v9 — OriginTrail/dkg-v9](https://github.com/OriginTrail/dkg-v9)
- [AriGraph — AIRI-Institute/AriGraph](https://github.com/AIRI-Institute/AriGraph)
- [AriGraph paper (arxiv 2407.04363)](https://arxiv.org/abs/2407.04363)
- [MemoryGraph — memory-graph/memory-graph](https://github.com/memory-graph/memory-graph)
- [Mem0 — mem0ai/mem0](https://github.com/mem0ai/mem0)
- [Zep paper (arxiv 2501.13956)](https://arxiv.org/abs/2501.13956)
- [Graphiti + FalkorDB integration (FalkorDB blog)](https://www.falkordb.com/blog/graphiti-falkordb-multi-agent-performance/)
- [Meet Lenny's Memory: Building Context Graphs (Neo4j blog)](https://neo4j.com/blog/developer/meet-lennys-memory-building-context-graphs-for-ai-agents/)
- [Awesome-GraphMemory survey — DEEP-PolyU](https://github.com/DEEP-PolyU/Awesome-GraphMemory)
- [Graph-based Agent Memory survey paper (arxiv 2602.05665)](https://arxiv.org/abs/2602.05665)
- [Karpathy LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- [agentic-memory research repo — lhl/agentic-memory](https://github.com/lhl/agentic-memory)
- [PROV-AGENT provenance paper (arxiv 2508.02866)](https://arxiv.org/abs/2508.02866)
- [Letta MemGPT docs](https://docs.letta.com/concepts/memgpt/)
- [Mem0 graph store breakdown (Dwarves Memo)](https://memo.d.foundation/breakdown/mem0)
- [Graphiti vs Mem0 benchmark (dev.to)](https://dev.to/juandastic/i-benchmarked-graphiti-vs-mem0-the-hidden-cost-of-context-blindness-in-ai-memory-4le3)

### A2A and graph-state-as-contract (Dispatch 2)

- [Linux Foundation: A2A surpasses 150 organizations](https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year)
- [A2A Protocol official docs](https://a2a-protocol.org/latest/)
- [a2aproject/A2A GitHub](https://github.com/a2aproject/A2A)
- [a2aproject/a2a-samples GitHub](https://github.com/a2aproject/a2a-samples)
- [awesome-a2a (ai-boost)](https://github.com/ai-boost/awesome-a2a)
- [Salesforce A2A Semantic Layer blog](https://www.salesforce.com/blog/agent-to-agent-interaction/)
- [Salesforce Agentforce A2A page](https://www.salesforce.com/agentforce/ai-agents/agent2agent-protocol/)
- [Salesforce Engineering: Agentforce Agent Graph](https://engineering.salesforce.com/agentforces-agent-graph-toward-guided-determinism-with-hybrid-reasoning/)
- [SAP Architecture Center: A2A in Enterprise AI](https://architecture.learning.sap.com/docs/ref-arch/e5eb3b9b1d/8)
- [SAP Community: Joule A2A](https://community.sap.com/t5/technology-blog-posts-by-sap/joule-a2a-connect-code-based-agents-into-joule/ba-p/14329279)
- [PayPal AP2 protocol blog](https://developer.paypal.com/community/blog/PayPal-Agent-Payments-Protocol/)
- [Google Cloud: AP2 announcement](https://cloud.google.com/blog/products/ai-machine-learning/announcing-agents-to-payments-ap2-protocol)
- [Microsoft Agent Framework A2A v1](https://devblogs.microsoft.com/agent-framework/a2a-v1-is-here-cross-platform-agent-communication-in-microsoft-agent-framework-for-net/)
- [Rapid Claw 2026 A2A guide](https://rapidclaw.dev/blog/a2a-protocol-complete-guide-2026)
- [Stellagent: A2A explained](https://stellagent.ai/insights/a2a-protocol-google-agent-to-agent)
- [Otávio Carvalho: AI Orchestration Reinventing Linda (1985)](https://otavio.cat/posts/ai-orchestration-reinventing-linda/)
- [bMAS paper: Blackboard Architecture for LLM Multi-Agent (arXiv 2507.01701)](https://arxiv.org/html/2507.01701v1)
- [Edoardo Schepis: Blackboard Architecture for Multi-Agent AI](https://medium.com/@edoardo.schepis/patterns-for-democratic-multi-agent-ai-blackboard-architecture-part-1-69fed2b958b4)
- [Denis Petelin: MCPs and Blackboard Pattern](https://medium.com/@dp2580/building-intelligent-multi-agent-systems-with-mcps-and-the-blackboard-pattern-to-build-systems-a454705d5672)
- [LangGraph docs: Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [LangGraph multi-agent docs](https://langchain-ai.github.io/langgraph/tutorials/multi_agent/multi-agent-collaboration/)
- [SurePrompts: LangGraph Prompting Guide 2026 (state-as-contract framing)](https://sureprompts.com/blog/langgraph-prompting-guide)
- [yatarousan0227/agent-contracts: Contract-Driven LangGraph](https://github.com/yatarousan0227/agent-contracts)
- [AutoGen Swarm docs](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/swarm.html)
- [Anthropic: How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- [Wikipedia: Linda (coordination language)](https://en.wikipedia.org/wiki/Linda_(coordination_language))
- [Wikipedia: Tuple space](https://en.wikipedia.org/wiki/Tuple_space)
- [Strands Agents: Graph Multi-Agent Pattern](https://strandsagents.com/docs/user-guide/concepts/multi-agent/graph/)

### Procedure vs identity (Dispatch 3)

- [CrewAI — Crafting Effective Agents](https://docs.crewai.com/en/guides/agents/crafting-effective-agents)
- [CrewAI-Style Role-Based Agents (mgx.dev)](https://mgx.dev/insights/crewai-style-role-based-agents-architecture-applications-and-future-trends/b708b00080c34c9bbeb9f680e26fb2d0)
- [CrewAI GitHub Issue #1048 — agents not following role/goal/backstory](https://github.com/crewAIInc/crewAI/issues/1048)
- [Aaron Yu — Comparison of LangGraph, CrewAI, AutoGen](https://aaronyuqi.medium.com/first-hand-comparison-of-langgraph-crewai-and-autogen-30026e60b563)
- [Truefoundry — CrewAI vs LangGraph](https://www.truefoundry.com/blog/crewai-vs-langgraph)
- [Microsoft AutoGen GitHub](https://github.com/microsoft/autogen)
- [Wu et al. — AutoGen paper (arXiv 2308.08155)](https://arxiv.org/abs/2308.08155)
- [QubitTool — LangGraph vs AutoGen](https://qubittool.com/blog/langgraph-vs-autogen-multi-agent-frameworks)
- [LangChain — Building LangGraph: First Principles](https://blog.langchain.com/building-langgraph/)
- [Letta / MemGPT Docs](https://docs.letta.com/concepts/memgpt/)
- [Letta — Memory Blocks](https://www.letta.com/blog/memory-blocks)
- [Anthropic — Equipping Agents with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
- [Anthropic — Agent Skills Overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
- [Anthropic — Persona Selection Model](https://www.anthropic.com/research/persona-selection-model)
- [Claude Code — Custom Subagents](https://docs.anthropic.com/en/docs/claude-code/sub-agents)
- [Anthropic — Claude Code Advanced Patterns (PDF)](https://resources.anthropic.com/hubfs/Claude%20Code%20Advanced%20Patterns_%20Subagents,%20MCP,%20and%20Scaling%20to%20Real%20Codebases.pdf)
- [OpenAI Swarm GitHub](https://github.com/openai/swarm)
- [Galileo — OpenAI Swarm Framework Guide](https://galileo.ai/blog/openai-swarm-framework-multi-agents)
- [HuggingFace smolagents GitHub](https://github.com/huggingface/smolagents)
- [HuggingFace blog — Introducing smolagents](https://huggingface.co/blog/smolagents)
- [DSPy](https://dspy.ai/)
- [Stanford DSPy GitHub](https://github.com/stanfordnlp/dspy)
- [Zheng et al. — When "A Helpful Assistant" Is Not Really Helpful (arXiv 2311.10054)](https://arxiv.org/abs/2311.10054)
- [Expert Personas Improve LLM Alignment but Damage Accuracy — PRISM (arXiv 2603.18507)](https://arxiv.org/abs/2603.18507)
- [PromptHub — Does Role-Prompting Make a Difference?](https://www.prompthub.us/blog/role-prompting-does-adding-personas-to-your-prompts-really-make-a-difference)
- [Learn Prompting — Role Prompting](https://learnprompting.org/docs/advanced/zero_shot/role_prompting)
- [Evaluating Persona Prompting for QA Tasks (ResearchGate)](https://www.researchgate.net/publication/382063490_Evaluating_Persona_Prompting_for_Question_Answering_Tasks)
