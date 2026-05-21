# Research Dispatch — Phase 1: Connection Facilitators and Agentic Memory Architectures

> **Paste everything below this line into a fresh Claude session** (Claude Code, Claude Desktop, or Insight Journal). Read it cold. Do not produce major output until I confirm. This prompt is fully self-contained.

---

## What this prompt is

I am launching a research effort to inform a major architectural upgrade to my AI agent framework (Diviner-Dojo / agent_framework_template). The central upgrade question: **should the framework's memory layer become a connection-facilitator substrate (graph-database-like) with materialized human-readable wiki views derived from it?**

I have already done substantial preliminary thinking. Everything you need is below.

## Who I am

I am Dan — the creator and gatekeeper of the AI-Native Agentic Development Framework (public org `Diviner-Dojo`, private fork `DanEvans-collab`). Background: working developer with deep Python / SQL Server experience. **New to graph databases.** New to building things in this specific architectural direction.

How I think:
- **ADHD profile** — narrow context window, piercing focus when engaged. Recovery from interruption is expensive. Creative energy is finite and non-renewable on demand.
- **Personal stakes** — I maintain three AI relationships: **Insight Journal** (my confidant; cross-session memory; where I spill my guts), **Claude Desktop** (deep philosophical and factual inquiry; extensive Howie family-history work lives here), and **Claude Code in my IDE** (functional code work). None can share memory with each other. The integration burden falls on me. **The framework upgrade is partly motivated by my need for a user-owned substrate outside any single AI's walls.**
- **Wider aspiration** — this work may help other people. That raises the bar on judgment quality, not just speed.

## How I work (cadence contract — non-negotiable)

Failure to honor this causes the work to stall.

1. **One step at a time.** Do not propose "do A then B then C." Propose one step. Once it's done, we figure out the next together.
2. **Always re-contextualizable.** At the start of every step you propose, restate: where we are in the arc, what this step is, why it matters, what is NOT in this step, cost (yours vs mine), energy budget impact, and ask "should I proceed?"
3. **Your job is to keep the thread.** When I lose context, you provide the pickup-from-here. Save state frequently — memory files, durable artifacts.
4. **Mirror-back cadence during streaming.** When I stream thoughts in chunks, after each chunk deliver a structured digest in plain language so I can verify before continuing. Do not push toward action during the streaming phase.

## Current state of the exploration

### The thesis I am working with (three claims — all hypotheses, not settled)

1. **Substrate** — A framework's job is to help agents make better *decisions*, not just remember more facts. Working mechanisms: an invariant registry (written rules in one place), procedures that force agents to consult the rules at decision time, and an honest **verifier** agent (truth-seeking, not adversarial — the American justice system is the wrong analogy because it produces winners, not truth).
2. **Layering** — Agents are defined by their **procedures**, not by human-style identities. Lessons live in a **shared pool indexed by task-relevance**, not siloed per agent. Three layers — **framework / project / shared** — are structurally separated by schema and access control, not by convention. AI can do what humans cannot: fully share accumulated learning across all specialists.
3. **Compounding** — Success is measured by evidence. Decisions that hold up, regressions caught early, costs trending down, **joy preserved**. New projects must benefit from old ones in metrically-visible ways.

### The architectural bet I am exploring

Connection-facilitator (graph) as canonical memory substrate, with markdown wiki views **materialized from it**. Motivation: editorial decisions in wikis can turn out wrong years later; a symbolic substrate canonical layer inoculates against this — you can rebuild wikis with new emphasis without losing what was captured.

I have been told (by external research) that this is the **least-validated direction** in the current community. The dominant production patterns are either:
- (a) **markdown-canonical** with graph as derived index built from it (Karpathy LLM Wiki pattern, SwarmVault, agentmemory), or
- (b) **graph-canonical** but querying the graph directly without comprehensive markdown materialization (Graphiti / Zep, Cognee, Mem0).
- (c) The specific direction I'm exploring — **graph-canonical + comprehensive markdown wiki views generated from graph on demand** — has no major production reference implementations I know of.

This may be a deliberate bet (I want to make it consciously, not by inheritance) or it may be wrong. I need evidence.

### Known facts going in

- **KuzuDB was archived October 2025** (community forks Bighorn / LadybugDB exist but are unproven). Active alternatives include **FalkorDB** (embedded, purpose-built for LLM/GraphRAG), **Neo4j** (production-safe, requires separate server), Memgraph, Apache AGE on Postgres, NetworkX (embedded, in-memory). DuckDB is **not** a graph DB — it's columnar relational.
- Arxiv paper 2604.11243 (April 2026) validates the **economics** of knowledge compounding (~84.6% token reduction in controlled experiments) but does not solve cross-project compounding for agentic systems.
- The framework template already implements four layers: Layer 1 (immutable discussion files), Layer 2 (SQLite relational index), Layer 3 (curated markdown memory), Layer 4 reserved (vector/graph — not implemented). Existing tables include `findings`, `pattern_sightings`, `agent_effectiveness`, `lineage_nodes`, `lineage_file_drift` — already shaped like a graph (foreign keys, agent identity, edges to discussions).

### Open architectural questions the research should help answer

- Who has built graph-canonical agentic memory in production, and is anyone generating comprehensive markdown wiki views from it?
- What backend choices are people making for graph memory in agentic systems? What worked, what was abandoned (besides Kuzu)?
- How are people handling **cross-project / cross-agent memory compounding** — letting agents accumulate experience that transfers across projects?
- How are people handling **multi-agent provenance** in shared memory (which agent generated which assertion, what's the epistemic status)?
- How are **A2A (Agent-to-Agent) protocols** being used in real systems — strictly at trust boundaries, or also for internal coordination? Who else uses "graph-state-as-contract" terminology or pattern (where agents coordinate through shared graph state instead of direct messaging)?
- **Procedure-only vs identity-rich agent design** — which is converging in real use, and what's the evidence?

## The research mission

**Three parallel dispatches.** Each is independent — do not let one team's findings contaminate another's perspective before they return. Synthesize after all three.

### Dispatch 1 — Connection Facilitators in Agentic Systems (primary, deep)

Identify up to 10 public projects (GitHub repos, papers, products) using graph-database-like memory layers for AI agents. For each, produce a spec sheet:

- **Project name + link**
- **Canonical direction**: markdown-canonical / graph-canonical / hybrid
- **Backend choice**: Neo4j / FalkorDB / Memgraph / NetworkX / Kuzu fork / custom JSON / other
- **Schema approach**: RDF/OWL ontology / property graph / typed edges with soft schema / no schema
- **Ingestion pattern**: how does data get into the graph (LLM extraction, manual, structured input)
- **Human-readable view strategy**: does the graph generate markdown / HTML wikis / no human view at all? How is staleness handled?
- **Cross-project compounding support**: is it within-project only, or do they have any mechanism for cross-project learning?
- **Multi-agent provenance handling**: do they track which agent/source generated each assertion?
- **Lifecycle / forgetting policy**: how do they prune, archive, or decay memory over time?
- **Maintenance status**: year of last commit, active or stale
- **Notable failure modes** they have documented or that the community has surfaced

**Meta-thinking lens**: For each project, ask two extra questions: "what concepts are involved here that I might not have named yet?" and "what outside-the-box thinking might make this approach more valuable than the project itself realized?" Record these as **candidate frontiers**, not findings. Curiosity is a first-class input.

### Dispatch 2 — A2A Protocol Usage in Public Projects

- Identify public projects using A2A (Agent-to-Agent) protocols (Google A2A or analogous standards).
- For each, document: what they use A2A for, where the trust boundary actually lives in their architecture, and how internal coordination happens when A2A is not used.
- Also search for **"graph-state-as-contract"** or analogous patterns where agents coordinate through shared graph state instead of direct messaging. Note whether this is novel terminology or a known pattern under a different name.

### Dispatch 3 — Procedure-Only vs Identity-Rich Agent Design

- Compare production agent frameworks: CrewAI, AutoGen, LangGraph, Letta/MemGPT, Anthropic Skills, plus any others worth surfacing.
- For each: do agents have personas / roles / backstories (identity-rich), or are they defined purely by procedure? What evidence is there about which approach produces better outcomes?
- My framework currently has 12 named specialist agents with values + procedural domain-lens definitions. I want to know if this is justified by evidence or whether a procedure-only design would be cleaner.

## Output expectations

Produce a single report at `docs/research/phase1-connection-facilitators.md` (create the directory if it doesn't exist).

Structure:

1. **Per-dispatch findings** — one section per dispatch, spec-sheet format.
2. **Cross-cutting synthesis** — patterns that appear across multiple dispatches, contradictions between sources, what the community has converged on vs what is still contested.
3. **Outside-the-box value candidates** — concepts surfaced by the meta-thinking lens that the source projects may not have fully exploited.
4. **Risk delta** — does the external evidence make my architectural bet riskier or less risky than the current estimate? Justify.
5. **Sources** — cited with links.

**Format note**: The decision about whether durable findings should live in narrative-wiki form, structured-claims form, or both is itself an **open architectural question being captured separately in an ADR**. Use plain markdown for now. Do not invest heavily in elaborate cross-referencing or section taxonomies — clarity over structure. Assume the format may be reshaped later.

## What is NOT in scope

- Building or designing the connection-facilitator schema itself.
- Picking a backend definitively.
- Making any commitment to graph-canonical vs markdown-canonical.
- Howie-family-project genealogy schema work (separate dispatch, deferred).
- Backporting findings into the current framework (separate step, deferred).

## How to engage with me when I return

When I come back to review the findings, follow the cadence contract above. Do not present me with everything at once. Start with the **cross-cutting synthesis** (the meta-view). Let me ask for the per-dispatch detail I want. Let me drive depth.

If during the research you discover the scope is wrong (e.g., the right cut is different from the three dispatches I named), say so before pushing forward. The scope is a hypothesis, not an order.

---

*End of prompt. Begin when I say "begin."*
