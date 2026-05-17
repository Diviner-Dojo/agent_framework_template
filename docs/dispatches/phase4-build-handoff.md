# Handoff Prompt — Phase 4: Build the Sourced-Assertion Memory Substrate

> **Paste this into a fresh Claude Code session in this repo when you pick this work back up.** Read it cold. The architecture is settled — your job in this session is to BUILD, not to re-deliberate.

---

## What this is

Continuation of an architectural exploration that's been running through Phase 1 (broad survey), Phase 2 (sanity check on alternatives), and Phase 3 (tooling research + decision brief). All three phases are complete and durable; their findings are captured in memory files and in `docs/research/`. **This handoff is for the BUILD step — actually scaffolding the framework's new memory substrate.**

You are not doing more research. You are not re-deliberating the architecture. You are building **Stack A′** with three small design-for-future additions, scoped to **use case #1: the framework's own memory of agent discussions.**

## Who I am

Dan — solo developer, gatekeeper of the AI-native agentic development framework (Diviner-Dojo / agent_framework_template). Python + SQL Server background. **New to graph databases.** ADHD piercing-focus profile — tooling friction at setup disproportionately kills momentum.

## How to engage with me (cadence contract — non-negotiable)

1. **One step at a time.** Don't propose "do A then B then C." Propose one step. Once it's done, we figure out the next together.
2. **Always re-contextualizable.** At the start of every step you propose, restate: where we are in the arc, what this step is, why it matters, what is NOT in this step, cost (yours vs mine), energy budget impact, and ask "should I proceed?"
3. **Your job is to keep the thread.** When I lose context, you provide pickup-from-here.
4. **Save state frequently.** Memory files, BUILD_STATUS.md, durable artifacts. Don't let progress live only in conversation context.

## Required reading (before doing anything else)

Read these in this order. They contain the settled architectural decisions; **do not re-derive them, do not relitigate them, do not propose alternatives:**

1. **Auto-memory index** at `C:\Users\evans\.claude\projects\<project-slug>\memory\MEMORY.md` — index of who-I-am notes, the cadence contract, the architecture framing, project state.
2. **The architecture framing memory entry** at `C:\Users\evans\.claude\projects\<project-slug>\memory\project_memory_architecture_framing.md` — the philosophical commitments, terminology, three open concerns, substrate decision, cross-project sharing model, build order. This is the single most important file.
3. **`docs/research/phase3-tooling-decision-brief.md`** — the Phase 3 decision brief. **Stack A′ is fully specified there with drop-in code.** This is your build template, with three modifications named below.
4. **`BUILD_STATUS.md`** at the project root — current state of the exploration, should reflect the build-handoff stopping point.

If anything you read in those files contradicts something I say in conversation, ASK before acting. The files are authoritative for what's been settled.

## What's already settled (do NOT re-deliberate)

- **Sources are canonical**; everything else is a vehicle for engaging with them.
- **Suchness preservation** is load-bearing. The path back to source must be a first-class user action, not a buried metadata link.
- **Working terminology**: sourced assertion (atomic unit), source binding (link), "the source asserts X" (verb form).
- **Per-project Stack A′** (SQLite + sqlite-vec + sentence-transformers + FastMCP) is the substrate, indefinitely.
- **Cross-project sharing** is solved via a separate shared-knowledge substrate + promotion, NOT federation. This is a FUTURE build (after Howie). Tonight's schema must DESIGN FOR IT.
- **Build order**: framework memory now → apply to Howie next → cross-project shared layer after that.
- **A2A protocols** are out of scope; that's settled.

## What you're building this session

Stack A′ as specified in `docs/research/phase3-tooling-decision-brief.md` (section "Tonight's prototype recipe"), **with three modifications:**

### Modification 1 — `project_id` field on every sourced assertion

Add `project_id TEXT NOT NULL` to the `assertions` table schema. Default to a `current_project` constant resolved at startup (from the framework's project name or `pyproject.toml`). All `assert_fact()` calls write the current `project_id`; all `search_semantic()` calls filter on it by default.

This is the slot for future cross-project queries. Without it, retrofitting is expensive.

### Modification 2 — Portable `source_ref` as a URI

Use the form `project://<project_id>/<relative_path>#L<start>-L<end>` rather than raw local file paths.

The `get_source()` MCP tool parses this URI to locate the file. Today it resolves only to the local project; future cross-project resolution becomes a one-function change. Without this, source refs from project A can't be resurfaced in project B's session.

### Modification 3 — `scope` parameter in MCP tool signatures

Add `scope: str = "local"` to `search_semantic()` (and to any future read tools). Today, only `"local"` is implemented — queries the local substrate. The parameter is in the signature so future expansion to `"shared"` or `["project_a", "project_b"]` doesn't break the tool contract.

## Files to create

Follow the project structure in the Phase 3 brief:

```
data/memory.db                  # NEW — created by substrate.init()
memory/
├── __init__.py                 # NEW — package marker
├── substrate.py                # NEW — SQLite + sqlite-vec wrapper + schema
└── embeddings.py               # NEW — sentence-transformers wrapper
mcp_server/
├── __init__.py                 # NEW
└── server.py                   # NEW — FastMCP server with three tools
.mcp.json                       # NEW or updated — register the server
```

Note: **the existing `memory/` directory in this repo is the framework's Layer 3 curated knowledge directory.** Do not collide with it. If a name conflict surfaces (e.g., the Python package `memory/` would shadow the existing markdown directory), choose a different package name (`framework_memory/` or `assertion_store/`) and update the import paths in the Phase 3 brief code accordingly. Confirm the rename with me before committing.

## Acceptance test for the session

1. **Install** dependencies via `uv` per Phase 3 brief commands.
2. **Drop a real agent-discussion transcript** at `sources/<today>_discussion.md` (or reuse one from `discussions/`).
3. **Use Claude Code to call `assert_fact`** three times against that transcript, recording sourced assertions with byte-range source refs in the portable URI form.
4. **Use `search_semantic`** to retrieve assertions related to a paraphrased version of one of those claims. Verify the semantic match works.
5. **Use `get_source`** to read the original passage. Verify source-resurfacing works end-to-end.

If the round-trip works, the architectural shape is validated. Update `BUILD_STATUS.md` to reflect Phase 4 completion and any defects surfaced.

## Coordination notes (real, check these)

- **ADR-0013 (token-efficiency telemetry) is in flight in a parallel session.** It touches `metrics/evaluation.db` (NOT `data/memory.db`), `scripts/close_discussion.py`, and adds `scripts/ingest_token_usage.py`. Architecturally orthogonal to this session's work. Don't modify those files unless coordinating with the other session.
- **Git status at handoff time** had uncommitted changes from prior framework work (v3.4.0 sync) AND from the ADR-0013 work. Check `git status` and decide whether to start a new branch or work on the existing branch with care. **Do not lose other work.**
- **The framework's own commit protocol applies.** Quality gate before commit. `/review` is required for changes touching code — the new `memory/` (or alternative package name) and `mcp_server/` directories DO count as code changes per the framework's rules.

## What is NOT in scope for this session

- Re-deliberating the substrate choice (SQLite + sqlite-vec is settled)
- Designing the cross-project shared layer (future build, after Howie)
- Building extraction pipelines beyond the three MCP tools (BAML/DSPy/Tier-1 extraction is the NEXT session, not this one)
- Building the code-as-concept graph (Layer 6, future)
- Building authority resolution (Wikidata/GeoNames lookup is future)
- The wiki materialization side (future)
- Touching ADR-0013's work surface

This session is JUST: substrate.py + embeddings.py + mcp_server/server.py + .mcp.json + acceptance test.

## How to engage when reporting back

Same cadence as Phases 1–3:
- Lead with where we are, what step you're on, what you're about to do
- Ask before each step that costs tokens or makes file changes
- Mirror back if I stream thoughts in chunks
- Don't push toward decisions during streaming
- Capture state in BUILD_STATUS.md before pausing for any reason

## When you finish

If the acceptance test passes, the natural next sessions are:
- Apply this substrate to a Howie-shaped use case (the proving ground for use case #4)
- Add Tier-1 extraction (BAML or Instructor) for richer template-driven extraction
- Begin testing reflexive agent use in real workflows

If the acceptance test fails, the next session diagnoses what didn't work end-to-end before adding any layers.

---

*End of handoff. Begin when I say "begin."*
