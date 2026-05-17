# Handoff Prompt — Phase 4 Canonical Acceptance Test

> Paste this into a fresh Claude Code session in this repo. The previous session built the substrate and smoke-tested it; your job is the canonical 5-step acceptance test using the `agent-memory` MCP tools that should now be loaded into your session.

---

## What this is

The previous Claude Code session built the Phase 4 sourced-assertion memory substrate (Stack A′ from `docs/research/phase3-tooling-decision-brief.md`, with three design-for-future modifications) and smoke-tested it by calling the underlying Python functions directly. **That validated the architecture but bypassed the MCP transport layer.** Your job is to do the canonical test: invoke the three tools through MCP, the way real agent use will.

## Verify the MCP server is loaded

Before anything else, confirm Claude Code discovered and loaded the `agent-memory` server. Three tools should be available to you:

- `assert_fact(subject, predicate, object, source_ref, framing="asserts")`
- `search_semantic(query, k=5, scope="local")`
- `get_source(source_ref)`

If they aren't listed, check `.mcp.json` at the project root — it should have an `agent-memory` server registered with `command: "python"` and `args: ["-m", "mcp_server.server"]`. If the server is registered but tools aren't visible, capture the error and stop.

## The 5-step test

**Source file**: `sources/2026-05-12_discussion.md` (a real agent-team deliberation about token-efficiency telemetry, copied from `discussions/2026-05-12/DISC-20260512-025323-token-efficiency-telemetry/transcript.md`).

### Step 1 — Read the source
Read `sources/2026-05-12_discussion.md`. Identify three substantive claims you could record as sourced assertions, each with a specific line range that contains the claim.

### Step 2 — `assert_fact` × 3
For each claim, call `assert_fact` with:
- `subject`, `predicate`, `object` — the structured claim
- `source_ref` — the bare path-with-fragment form: `sources/2026-05-12_discussion.md#L<start>-L<end>`. The server will canonicalise it to `project://agentic-framework-template/sources/2026-05-12_discussion.md#L<start>-L<end>`.
- `framing` — usually `"asserts"`; use `"questions"` or `"considers"` if the source is hedging.

Verify each call returns `{fact_id, source_ref, project_id}`. Note the URI form actually stored.

### Step 3 — `search_semantic` (paraphrase)
Pick one of the three claims you recorded. Compose a query that paraphrases it (different words, same meaning). Call `search_semantic(query="...", k=3)`. The matching assertion should appear at the top of the results with the lowest distance.

Sanity check: distances less than ~1.0 indicate strong semantic match; 1.0–1.4 is moderate; >1.4 is weak.

### Step 4 — `get_source` on the top hit
Take the top hit's `source_ref` URI from step 3 and pass it to `get_source(source_ref="...")`. Verify the returned `passage` text matches the actual content at the line range in `sources/2026-05-12_discussion.md`.

### Step 5 — Suchness check
Compare the symbolic form of the assertion (subject+predicate+object) to the original passage. Note any nuance, framing, or context the symbolic form lost. This is the suchness-preservation moment — the architectural commitment is that this comparison is always available, not that the symbolic form perfectly captures the source.

## Reporting back

Update `BUILD_STATUS.md`:
- Move Phase 4 from "session active" to "round-trip validated" (or document defects)
- Note the three claims recorded, the top semantic match's distance, and any suchness observations
- Surface any defects (URI parsing edge cases, MCP transport quirks, schema gaps) under Open Advisories

If the round-trip works, the architecture is fully validated and we move to the framework's commit protocol: `python scripts/quality_gate.py` → `/review` → address blocking findings → commit.

## What's already settled (do NOT re-derive)

- `assertion_store/` is the chosen Python package name (avoids collision with the markdown `memory/` directory)
- Stack A′ is settled; no substrate alternatives are on the table
- Three Phase 4 modifications are baked in: `project_id` field on every assertion, portable `source_ref` URI, `scope` parameter in MCP signatures
- The canonical project_id is `agentic-framework-template` (resolved from `pyproject.toml`)

## What is NOT in this session

- No new code (substrate is built; you're testing it)
- No /review yet (canonical test first, then we commit)
- No extraction pipeline (BAML/DSPy is the next session)
- No `scope="shared"` — `local` is the only implemented scope

## Cadence contract

- One step at a time. Re-contextualize at the start of each step. Save state in BUILD_STATUS.md before pausing.
- The 5 steps above can each be a single tool call + a brief observation. Don't bundle them.
- The previous session's auto-memory entries (`project_memory_architecture_framing.md`, `feedback_adhd_cadence_contract.md`, `feedback_incremental_thinking.md`) carry forward — read them if you need to re-anchor.

---

*End of handoff.*
