# Research Dispatch — Phase 3: Tooling for a Sourced-Assertion Memory Architecture

> **Paste everything below this line into a fresh Claude session** (Claude Code, Claude Desktop, or another AI tool). Read it cold. This prompt is fully self-contained — Phase 1 and Phase 2 findings have been distilled in; you do not need access to prior reports.

---

## What this prompt is

The third phase of an architectural exploration for the persistent-memory layer of an AI agent framework. Phase 1 surveyed the field (graph-canonical vs markdown-canonical, etc.). Phase 2 sanity-checked alternatives (bitemporal stores, factoid prosopography, the graph-as-query-model-vs-storage distinction). The architectural shape has now stabilized. **Phase 3 is about specific tooling: what to actually build with.**

## Who I am

Dan — solo developer, gatekeeper of an AI-native agentic development framework (Diviner-Dojo / agent_framework_template). Background: working developer with deep Python and SQL Server experience. **New to graph databases.** ADHD piercing-focus profile — tooling friction at the install / setup stage disproportionately kills momentum. I clear evenings to push on this; the tooling has to honor the energy budget.

## How to engage with me (cadence contract, non-negotiable)

1. **One step at a time.** Don't propose "do A then B then C." Propose one step. Once it's done, we figure out the next together.
2. **Always re-contextualizable.** At the start of every step you propose, restate: where we are in the arc, what this step is, why it matters, what is NOT in this step, cost (yours vs mine), energy budget impact, and ask "should I proceed?"
3. **Your job is to keep the thread.** When I lose context, you provide pickup-from-here.
4. **Mirror-back cadence during streaming.** When I stream thoughts in chunks, after each chunk deliver a structured digest in plain language before continuing.

## What we've already settled (do NOT re-derive these)

### The philosophical commitments

- **Sources are canonical.** Original sources — agent discussions the framework produces, primary-source documents like John Howie's *Scots Worthies* — are the only canonical truth. Everything else (graph, wiki, summary, index) is a *vehicle for engaging with sources*, never truth itself.
- **Suchness preservation is load-bearing.** From the Buddhist concept — the essence that language can only approximate. Symbolic abstraction is necessary but always lossy. The system must always preserve the path back to the source so the user can *challenge* (not just view) the symbolic version. Source-resurfacing must be a first-class user-facing action, not a buried metadata link.
- **Reasoning is the primary artifact.** Decisions and their lineage are durable assets; code is output. The architecture serves reasoning over time.

### The three open concerns that drive design

1. **Re-extraction** — can the substrate be re-derived from sources as understanding evolves, rather than ossifying at first extraction?
2. **Texture preservation** — can the symbolic layer capture tone, meta-information, rhetorical positioning?
3. **Suchness preservation** — even at maximum richness, symbols are lossy; can the system always resurface the source so the user can challenge what was abstracted away?

Re-extraction and suchness preservation collapse to a single architectural move: **preserve raw sources alongside extracted assertions, keep them linked, allow re-extraction as a normal operation.**

### Working terminology

- **Sourced assertion** = the atomic unit of extracted meaning. The raw text *asserts* something; tying it to a source disambiguates "claim's" double meaning in English. (The historical digital-humanities term is "factoid" / "factoid prosopography" — retained when referencing that body of work; our working term is **sourced assertion**.)
- **Source binding** = the link between source and assertion. The context binds the source to the assertion; the binding is not a passive pointer but carries the contextual relationship.
- **Verb form**: *"the source asserts X."* (e.g., *"the Family Bible asserts Andrew Howie was born in 1735."*)

### The sharpened architectural picture

- **Input primitive** — sourced assertions (subject, predicate, object, source-passage with byte-range, framing/texture properties, vector embedding, external authority refs).
- **Substrate** — graph-like connection layer (substrate choice is the locus of THIS research). Holds sourced assertions with typed relationships, supports multi-hop traversal, bitemporal queries, graph-style filters, vector similarity search.
- **Vectors as complementary primitive.** Structure for questions the schema anticipates; vectors for semantic-gap questions. GraphRAG pattern.
- **External authority references designed in from day one.** Entities (Place, Person, Event, Organization) carry slots for external authority IDs (Wikidata Q-numbers, GeoNames IDs, VIAF, FamilySearch, Pleiades, PeriodO). Enables enrichment AND cross-validation (e.g., flag assertions where the place name didn't exist until after the claimed date).
- **Multiple derived views.** A wiki is one form. Others: on-demand narrative synthesis, dashboards, timelines, maps. Same substrate, many projection shapes.
- **Tiered extraction.** Tier 0 deterministic (Tree-sitter, regex, parsers). Tier 1 cheap LLM (executes compiled templates at volume). Tier 2 expensive LLM (writes the templates, audits, handles keystone sources).
- **Reflexive use via MCP.** Substrate exposed as MCP tool calls. Memory files become sparse indexes pointing to where rich knowledge lives, not walls of facts.

### Use cases the architecture must serve

1. **Framework's own memory** — agent discussions, findings, patterns over time. Smallest delta from existing capture pipeline.
2. **Code-as-concept graph** — semantic navigation of the framework's own code (Tree-sitter + LLM concept extraction) for token-efficient agent recall in daily work.
3. **Personal Insight Journal** — private memory work. **Strict privacy boundary: no reflexive external lookups for this domain.**
4. **Howie family history** — genealogy + primary-source documents like *Scots Worthies*, with rich external authority linking and cross-validation.

### Substrate candidates currently on the table (from Phase 1 + 2)

- **Native graph DBs**: Neo4j Community, FalkorDB (embedded, LLM-tuned), Memgraph, Apache AGE (on Postgres)
- **Bitemporal immutable-fact stores**: Datomic, XTDB
- **Graph-query-over-relational**: SQLite + Datalog (Logseq's choice), Postgres + Apache AGE
- **Typed-object stores**: Capacities-style, Heurist-style
- **In-memory + export**: NetworkX (what Graphify uses)
- **Kuzu forks (unproven)**: Bighorn, LadybugDB

## The research mission

Survey **specific tooling** for each layer of the architecture. For each layer, the question is: *what's available, what's mature, what fits the constraints, what doesn't?*

### Layer 1 — Substrate (the core decision)

For each substrate candidate above, produce a spec sheet:

- **Setup complexity** — what does it take to install and run locally on Windows / WSL2?
- **License** — CC0, Apache, AGPL, commercial?
- **Query capabilities** — what query language? Multi-hop traversal? Bitemporal queries? Graph-style filters?
- **Vector integration** — native, plugin, or external? What embedding sizes? Performance?
- **MCP support** — is there a maintained MCP server for this substrate, or would one need building?
- **Schema flexibility** — strict (RDF/OWL) vs property graphs vs schema-less?
- **External authority handling** — can entities carry URI references natively? Federated queries?
- **Python ecosystem** — quality of Python client/SDK?
- **Maintenance status** — active commits, last release, community size?
- **Notable failure modes** — what breaks in practice?
- **Fit for our four use cases** — which substrate fits which use case best, and why?

Look especially hard at substrates that fit a **solo Python developer on Windows**, not enterprise deployments.

### Layer 2 — Vector encoding

- What embedding models are appropriate? (sentence-transformers? OpenAI? local-only options like nomic-embed-text-v1.5?)
- How do different substrates handle vector storage? Native (Neo4j 5.20+, Postgres+pgvector, FalkorDB)? Plugin? Separate vector DB alongside the substrate?
- Cost/quality tradeoff at the embedding step.
- Strategy: embed *source passages* vs *extracted assertions* vs both — what's the practical guidance?

### Layer 3 — Extraction pipeline

- LLM-driven extraction frameworks: DSPy (compiled prompts, the Stanford one), LangChain (heavy but known), Instructor (Pydantic + structured output), Anthropic SDK direct (lightweight). Which fits the tiered-extraction model?
- Tree-sitter Python bindings — maturity, supported languages, ergonomics
- Authority resolution: tools for matching extracted entity strings against Wikidata/GeoNames/VIAF (Reconciliation Service API? OpenRefine? custom Python?)
- Validation: tools for checking extracted output against a schema (Pydantic, JSON Schema, others)

### Layer 4 — MCP server tooling

- Off-the-shelf MCP servers for graph databases? (There IS a Neo4j MCP server. Others?)
- Frameworks for writing MCP servers in Python (FastMCP? Anthropic's official MCP SDK?)
- The Skills + MCP combined pattern — examples in the wild?
- Token-efficiency best practices for MCP tool design — how to expose 4-8 focused tools that minimize per-session overhead

### Layer 5 — Derived view generators

- Tools for materializing markdown wikis from graph queries (Graphify is one; what else?)
- LLM-prose-rendering frameworks for keystone pages
- Static site generators that can take graph queries as inputs (Hugo, mkdocs, something graph-aware?)
- Citation-aware rendering (academic publishing tools — Pandoc with citation styles? CSL?)

### Layer 6 — Code-as-concept graph

This is a first-class research area, not an afterthought. The user wants efficient semantic code navigation as a daily-use tool.

- **Graphify** — deep look at its architecture, limitations, install on Windows
- **Sourcegraph self-hosted** — feasible for a solo developer?
- AST graph tools beyond Tree-sitter (semgrep? language-server-protocol-based tools?)
- Code-specific embedding models (code-bert, jina-code-v2, voyage-code, others)
- Tools that combine structural (AST) + semantic (LLM) code extraction
- MCP servers exposing code-as-graph queries — exist? would need building?

### Layer 7 — External authority resolution

- **Wikidata**: SPARQL endpoints, Python clients (qwikidata, SPARQLWrapper, others). Rate limits? Local mirror feasibility?
- **GeoNames**: API + Python clients. License compatibility?
- **VIAF**: API access
- **FamilySearch API**: licensing terms, especially for non-LDS use
- **PeriodO**: gazetteer of time periods
- **Pleiades**: ancient places
- **Reconciliation tools**: OpenRefine, others
- Note license of every tool surveyed and any incompatibilities for publishing the work later

### Layer 8 — Candidate stacks

Beyond surveying each layer independently, propose **2–4 concrete candidate stacks** that fit the constraints. For each stack:

- What it's good for, what it sacrifices
- Rough effort to set up (minutes? hours? days?)
- Rough ongoing cost (in attention, in dollars)
- Where it'd hit a wall

Suggested stack profiles to compare:

- A **minimum-viable / fastest-setup** stack — quickest path to a working prototype this evening
- A **production-quality / least-lock-in** stack — what would scale and stay open over years
- A **bitemporal-first** stack centered on Datomic or XTDB
- A **graph-native** stack centered on Neo4j or FalkorDB

## Constraints to be explicit about

- **Solo developer.** Operational complexity matters. Anything requiring a dedicated DBA or DevOps is wrong-shaped.
- **Windows primary, WSL2 available.** Substrate availability and friction on Windows matters.
- **Python primary language.** Quality of Python SDKs weighs more than absolute substrate capability.
- **Existing framework uses**: SQLite (`metrics/evaluation.db`), Python scripts (`scripts/`), MCP, Claude Code as the primary interface. The existing capture pipeline already produces structured outputs to SQLite — they would migrate or coexist with the new substrate.
- **Privacy boundary for Insight Journal**: substrate must support a deployment mode that doesn't reflexively reach out to external services. Per-project enrichment policy.
- **License compatibility** matters if work is ever published. Note license of every tool surveyed.
- **Local-first preferred.** Substrate runs locally, not cloud-dependent. Cloud services are acceptable as references but shouldn't be the primary recommendation.
- **Cost ceiling**: prefer free/open-source. Paid services need a strong reason and a free local development path.

## What is NOT in scope

- Re-surveying architectural alternatives (Phase 1 and Phase 2 covered this thoroughly)
- Deciding whether to build this (already committed directionally)
- Cloud-only managed services that require permanent account keys as the primary recommendation
- Tools without Python SDKs (unless they're so important they justify a different stack)
- Schema design itself (downstream of substrate choice)
- Deep dives into the patterns/frameworks already covered in Phase 1: Graphiti, Cognee, Mem0, Letta, AriGraph, MemoryGraph, OpenMemory, OriginTrail, AutoGen, CrewAI, LangGraph, etc. — those are not the focus of this phase; tools are.

## Output expectations

Single plain-markdown report at `docs/research/phase3-tooling.md` (create the directory if it doesn't exist).

Structure:

1. **Lead summary** — 3-5 sentences on what the survey found that genuinely shifts the tooling picture. Be honest. If nothing dramatic surfaced, say so.
2. **Per-layer surveys** — one section per layer (substrate, vectors, extraction, MCP, derived views, code-graph, authority resolution). Spec-sheet format where it fits; prose where it doesn't.
3. **Candidate stacks** — 2-4 concrete combinations with tradeoffs and effort estimates.
4. **Recommendation for tonight's prototype** — if someone wanted to build a small validation prototype this evening focused on **agent discussions** as the smallest end-to-end domain, what specific stack would minimize friction while still being a real test? Be specific about install commands and file paths.
5. **Open questions** — things the survey couldn't answer and that would only become clear by trying.
6. **Sources** — URLs.

Honest quality bar: if a category has no good options, say so. If everything is mid, say so. Don't pad.

## How to engage with the developer when reporting back

Same cadence as Phase 1 / 2:
- Lead with the meta-view; don't dump everything at once.
- Highlight what shifts the decision space, not everything that exists.
- Be honest about tradeoffs.
- Note what would only become clear by actually trying, not by surveying.
- One step at a time. Re-contextualize. Mirror back. Don't push toward decisions during streaming.

---

*End of dispatch. Begin when I say "begin."*
