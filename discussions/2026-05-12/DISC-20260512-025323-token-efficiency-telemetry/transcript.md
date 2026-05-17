---
discussion_id: DISC-20260512-025323-token-efficiency-telemetry
started: 2026-05-12T02:53:42.947541+00:00
ended: 2026-05-12T02:59:06.601526+00:00
agents: [docs-knowledge, facilitator, independent-perspective, performance-analyst, project-analyst]
total_turns: 7
---

# Discussion: DISC-20260512-025323-token-efficiency-telemetry

## Turn 1 — facilitator (evidence)
*2026-05-12T02:53:42.947541+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Evaluate the framework's current telemetry/measurement capability for token usage and efficiency; research what other projects do; dispatch the project-analyst to derive value from those efforts; produce a not-overdesigned recommendation that lets the developer A/B compare framework changes.
- **Files/scope**: Framework-wide measurement infrastructure — Layer 2 SQLite (metrics/evaluation.db), JSONL trend logs (quality_gate_log.jsonl, knowledge_pipeline_log.jsonl, deploy_log.jsonl, emulator_test_log.jsonl), event capture pipeline (scripts/write_event.py, ingest_events.py), agent_effectiveness table, protocol_yield table.
- **Developer-stated motivation**: About to launch into work designed to make the framework operate more efficiently. Concerned current instrumentation is insufficient to measure whether each proposed change actually moves the needle. Wants light on token usage and efficiency before changing approaches blindly.
- **Explicit constraints**: Do NOT overdesign. The goal is enough measurement to compare approaches — not a full observability platform. Research must precede design. Project-analyst must be in the loop to apply external lessons.

---

## Turn 2 — performance-analyst (proposal)
*2026-05-12T02:56:10.381853+00:00 | confidence: 0.82*
*tags: performance, instrumentation, schema, model:opus*

Gap: cost-side is missing; value-side is built. 4 column additions unlock the A/B capability — no new tables, no new scripts.

**Schema additions:**
- turns: tokens_in, tokens_out, model
- discussions: total_tokens_in, total_tokens_out, estimated_cost_usd

**Single instrumentation point:** at Task() call site, extract usage.input_tokens / usage.output_tokens from response, pass as new optional args to write_event.py. close_discussion.py rolls up totals.

**Primary signal:** blocking findings per 1K output tokens, grouped by command_type. Output tokens dominate cost (3-5x input pricing); blocking findings are non-negotiable value; command_type is already structured.

**Secondary:** cost per closed discussion, segmented by risk_level and collaboration_mode → answers 'does Structured Dialogue cost more than Ensemble for low-risk work?'

**Anti-overdesign red flags:** No dashboard. No real-time streaming. No per-finding cost column. No prompt content capture (secret-leakage surface). SQLite query runs in <10ms at framework scale.

**Top 3 A/B hypotheses once instrumented:**
1. Sonnet vs opus for checkpoint reviews — opus may find more blockers per turn but at 3x cost
2. Reflection step on/off — does it produce additional blocking findings or just calibration?
3. Structured Dialogue vs Ensemble at medium-risk — possibly same blocking yield at ~40% fewer tokens

**Open question (confidence-limiting):** whether Task() response object exposes usage in a way the facilitator can intercept — depends on Claude Agent SDK specifics.

---

## Turn 3 — independent-perspective (evidence)
*2026-05-12T02:56:21.512009+00:00 | confidence: 0.78*
*tags: research-scout, external-patterns, rule-of-three, model:opus*

Research Scout: surveyed Claude Code, LangSmith, AG2/AutoGen, CrewAI, AgentOps, Langfuse/Phoenix/Helicone, OpenAI evals.

**Game-changing finding:** Claude Code already writes per-message usage data to ~/.claude/projects/{project}/{sessionId}/ JSONL (main) and subagents/agent-{agentId}.jsonl. Schema per message: message.id (dedupe), usage.input_tokens, usage.output_tokens, usage.cache_creation_input_tokens, usage.cache_read_input_tokens. Compaction events tagged. Three independent community tools (ccusage, token-dashboard, Claudetop) use the same approach: scan JSONL, dedupe by message.id, sum the four usage fields. **Rule of Three met.** Per-subagent token tracking is explicitly Not Planned in Claude Code (#22625) — but the raw data is on disk.

**This resolves performance-analyst's open question:** we do NOT need to intercept Task() responses. The data exists post-hoc. Parser is ~80 lines, zero new dependencies.

**Adoptable shortlist:**
1. Parse Claude Code transcript JSONL (highest leverage — data already exists)
2. AG2 usage-summary schema: {agent: {model: {input, output, cache_read, cache_write, est_cost}}} — maps to 5 columns on turns
3. LangSmith parent-child rollup at close time (consistent with how duration_minutes already works)
4. OpenAI evals 'tokens-per-outcome' pattern — bind token count to graded outcome; join with existing agent_effectiveness to get tokens-per-blocking-finding (the actual efficiency measure)
5. metrics/token_usage.jsonl — mirrors the existing JSONL-per-domain pattern

**Do NOT adopt:** full OTel/OpenInference (wrong scale), Langfuse/Phoenix/Arize self-hosted (ClickHouse + Docker), Helicone proxy (would sit in front of Claude Code itself — breaks the loop), AgentOps SDK (for frameworks lacking telemetry — we have data already), per-token cost as primary metric (pricing changes; store raw counts, compute cost in views).

**Hidden assumption flagged:** ~/.claude/projects/ path is undocumented and informal. Three tools depend on it; Anthropic has not committed to stability. If we build on this, isolate the parser behind an interface per review_gates.md.

**Cross-domain insight:** the 'tokens-per-correct-answer' framing maps cleanly onto existing findings + agent_effectiveness infrastructure. Most observability tools measure spend; few measure efficiency. Our discussion-centric model is well-positioned to compute this ratio — already have outcomes, only lack denominator.

dispatch_request: project-analyst to deep-dive ccusage, token-dashboard, AG2 — Rule of Three met, urgency: enhancing.

---

## Turn 4 — docs-knowledge (proposal)
*2026-05-12T02:56:30.647264+00:00 | confidence: 0.8*
*tags: documentation, schema, migration, model:sonnet*

Integration cost: 4 _migrations entries, 1 view, optional JSONL field, 2 CLAUDE.md sentences. No ADR needed (instrumentation addition, not architectural decision). No .claude/rules/ changes needed.

**Placement recommendations:**
- Token counts per turn → turns.tokens_in, turns.tokens_out (first-class columns; tags TEXT is not aggregatable)
- Model used per turn → KEEP in turns.tags as existing model:<tier> convention. Do NOT add turns.model column. Adding column would duplicate data and create drift risk between column and tag. Promote to column only when structured queries demand it.
- Total tokens per discussion → discussions.tokens_total, discussions.cost_usd (consistent with how duration_minutes is rolled up at close)
- Per-command-run rollup → add tokens_total + cost_usd fields to existing JSONL trend logs (knowledge_pipeline_log.jsonl, quality_gate_log.jsonl) — additive, no migration

**View:** v_token_efficiency joining discussions + protocol_yield, grouped by command_type. Follows v_agent_dashboard pattern.

**Migration path:** 4 entries in _migrations list at scripts/init_db.py:250. Existing try/except OperationalError pattern is idempotent and NULL-safe.

**Backfill stance: do NOT backfill.** content_excerpt is truncated → estimates would be unreliable. Historical turns predate instrumentation; NULL is the honest representation. Efficiency work starts from a clean baseline on first instrumented run.

**Drift risk identified:** write_event.py must keep new args optional with None defaults so commands not yet updated still work. Hardcoded price table in close_discussion.py would drift — recommend storing raw counts only, computing cost in views.

**Disagreement with performance-analyst:** they proposed turns.model TEXT column; I argue keep model in tags. The tier-level granularity in tags (opus, sonnet) is already what we capture. Model-ID-level granularity (claude-opus-4 vs claude-opus-4-5) is a future decision, not a blocker for current efficiency work.

**Documentation surface area:** two CLAUDE.md edits only — Capture Pipeline section bullet for write_event.py, SQLite tables list adds the new columns and v_token_efficiency. That's the entire doc footprint.

---

## Turn 5 — facilitator (decision)
*2026-05-12T02:56:37.561820+00:00 | confidence: 0.8*
*tags: dispatch-decision, requested:project-analyst, outcome:approved*

Dispatch approved: project-analyst for deep-dive on ccusage, token-dashboard, and AG2 usage tracking. Rationale: Research Scout met Rule of Three on a single pattern (3 independent community tools converging on the same Claude Code JSONL parser approach). This is exactly the discovery pipeline the framework is designed for. Also aligns with developer's explicit instruction: 'dispatch the project analyst to derive value from those efforts.'

---

## Turn 6 — project-analyst (proposal)
*2026-05-12T02:58:29.956719+00:00 | confidence: 0.82*
*tags: adoption-scoring, rule-of-three, model:sonnet*

Scored 3 patterns on 5-dim rubric, applied Rule of Three threshold (>=20/25).

**Pattern 1: Parse Claude Code transcript JSONL — 17/25 → ADAPT (NOT ADOPT)**
P:5 E:4 Ev:3 F:3 M:2. Undocumented path = unsuitable for always-on infrastructure. But the **4-field dedup schema** (input/output/cache_creation/cache_read by message.id) IS the right canonical token record shape. Adopt schema, not the filesystem reader. Belongs as opt-in diagnostic script, not core pipeline.

**Pattern 2: AG2 dict-of-agents — 22/25 → ADOPT**
P:4 E:5 Ev:4 F:4 M:5. Adopt the {agent → model → tokens} nesting structure. Translate into a separate child table: agent_token_usage(discussion_id, agent, model, input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens, recorded_at). DO NOT adopt gather_usage_summary() or total_cost field (pricing drifts; store raw counts).

**Pattern 3: LangSmith rollup-at-close — 22/25 → ADOPT**
P:3 E:5 Ev:4 F:5 M:5. Aggregate at close, not at write. Slots into close_discussion.py with a single UPDATE statement. Adopt only the trigger point — not LangSmith's run-hierarchy model or SDK primitives.

**Disagreement with performance-analyst and docs-knowledge:** they proposed token columns ON turns table. I recommend separate agent_token_usage child table. Rationale: turns is already wide; token data is additive and optional; separation lets us query token usage without scanning content_excerpt. Also: separate table cleanly handles cache fields, which they both omitted.

**Recommended adoption path (priority order):**
1. Schema: new agent_token_usage table + 3 token rollup columns on discussions
2. Write path: extend write_event.py with optional --token-data JSON arg
3. Rollup: append UPDATE statement to close_discussion.py after duration_minutes step

**Open questions for developer:**
1. Are token counts available to the facilitator at write_event.py call time? If not, where in the workflow?
2. Should model column store actual model ID (claude-sonnet-4-6) or tier alias (sonnet)? Former enables precise cost; latter is more stable.
3. Scope: only structured /review and /build_module dispatches, or also informal facilitator responses?

**Adoption log:** record Pattern 2 and Pattern 3 in memory/lessons/adoption-log.md (>=20/25). Pattern 1 logged as DEFERRED with schema-field attribution credit.

---

## Turn 7 — facilitator (synthesis)
*2026-05-12T02:59:06.601526+00:00 | confidence: 0.78*
*tags: synthesis, facilitator, model:opus*

## Request Context
- **What was requested**: Evaluate current telemetry capability for token efficiency, research what other projects do, dispatch project-analyst to derive value, produce a not-overdesigned recommendation.
- **Files/scope**: metrics/evaluation.db schema, scripts/write_event.py, scripts/close_discussion.py, JSONL trend logs.
- **Developer-stated motivation**: About to start framework efficiency work; current instrumentation cannot answer 'did this change make us more efficient?'
- **Explicit constraints**: Do NOT overdesign. Compare approaches, not build an observability platform.

## Convergence (all three specialists agree)

1. **The framework has value-side telemetry but no cost-side.** turns and discussions tables capture findings, confidence, calibration — but no tokens, no model, no cost. Without the denominator, no ratio.
2. **No new pipeline. No new layer.** Extend existing schema and existing close-time rollup. Anti-overdesign red flags shared: no dashboard, no real-time streaming, no per-finding cost column, no prompt content capture.
3. **Primary efficiency signal: blocking findings per 1K output tokens, grouped by command_type.** All three converge on this ratio. Secondary: cost per closed discussion segmented by risk_level + collaboration_mode.
4. **Do NOT backfill historical turns.** content_excerpt is truncated; estimates would contaminate the baseline. NULL is the honest representation. Start clean.
5. **Top 3 A/B hypotheses worth testing once instrumented:** (a) sonnet vs opus for checkpoint reviews, (b) reflection step on/off, (c) Structured Dialogue vs Ensemble at medium-risk.

## Disagreements — Developer Decision Points

### Disagreement 1: Schema shape — columns on turns vs separate child table
- **performance-analyst + docs-knowledge:** Add tokens_in / tokens_out as columns on the turns table. NULL-safe via existing _migrations pattern. Minimal change. Both cite the existing 'confidence' column as the precedent.
- **project-analyst:** Separate child table agent_token_usage(discussion_id, agent, model, input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens, recorded_at). Cleaner separation; cleanly handles cache fields (which the others omitted); turns is already wide.
- **What's actually at stake:** Cache field handling. Cache reads cost ~10% of normal input tokens; cache creation costs ~125%. Collapsing them into tokens_in is wrong-economics. The child table is the safer schema. Columns on turns is the smaller change.

### Disagreement 2: Model field — column vs tag
- **performance-analyst + project-analyst:** First-class model column. Needed to GROUP BY model for cost-per-model rollups.
- **docs-knowledge:** Keep model:<tier> in turns.tags as already established convention. Duplicating it to a column creates drift risk between tag and column. Promote to column only when structured queries demand it.
- **What's actually at stake:** Whether your efficiency questions need to filter or only describe. If you just want 'what did this discussion cost', tag is fine. If you want 'how do sonnet checkpoints compare to opus', a column is needed.

### Disagreement 3: Claude Code transcript JSONL parser — infrastructure or forensic tool
- **independent-perspective (Research Scout):** Game-changing because data already exists at ~/.claude/projects/{project}/{sessionId}/subagents/. Removes need to instrument Task() call site. Three independent tools (ccusage, token-dashboard, Claudetop) use this approach → Rule of Three met.
- **project-analyst:** 17/25 score → ADAPT, not ADOPT. Path is undocumented; Anthropic can break it any release. Should be opt-in diagnostic script, not core pipeline. Adopt the 4-field dedup schema, not the filesystem reader.
- **What's actually at stake:** Whether to depend on an undocumented external path or build live instrumentation. The fork in the road: bet on Anthropic stability (cheap, fragile) OR build durable but require facilitator workflow to capture usage objects (more work, robust).

## Recommended Path (Facilitator Synthesis)

The path that maximizes signal per unit of build effort while preserving optionality:

**Step 1 — Schema (smallest reversible move):**
- Add 4 NULL-safe columns via _migrations:
  - turns.tokens_in INTEGER
  - turns.tokens_out INTEGER
  - turns.cache_read_tokens INTEGER  (resolves cache-field gap project-analyst flagged)
  - turns.cache_create_tokens INTEGER
- Add 3 NULL-safe columns to discussions: total_tokens_in, total_tokens_out, total_cache_tokens
- Add view v_token_efficiency joining discussions + protocol_yield by command_type
- Keep model in tags for now (docs-knowledge view); revisit only if Disagreement 2 becomes a blocker

This is the **columns-on-turns + cache-aware** synthesis. It splits the disagreement: take the smaller schema change (columns) and take the broader field set (cache fields).

**Step 2 — Write path (instrumentation):**
- Extend write_event.py with optional --tokens-in / --tokens-out / --cache-read / --cache-create args, all defaulting to None
- Update facilitator workflow / Task() result handling to extract usage from response and pass through
- Open question for developer: is usage exposed in the Task() result object? Research Scout flagged this as the gating uncertainty

**Step 3 — Rollup at close:**
- In close_discussion.py, after duration_minutes step, append a SUM over turns and write to discussions
- Mirrors the LangSmith rollup-at-close pattern (Pattern 3, 22/25)

**Step 4 — Bootstrap with JSONL transcript script (opt-in, not infrastructure):**
- Build a one-shot scripts/import_token_data.py that reads ~/.claude/projects/ and backfills the new columns for closed discussions
- Use it once to establish a baseline before your efficiency work begins
- Do NOT depend on it for live capture; it's a forensic tool

**Step 5 — Adoption log:**
- Record AG2 schema (Pattern 2, 22/25) and LangSmith rollup-at-close (Pattern 3, 22/25) in memory/lessons/adoption-log.md
- Record Claude Code JSONL pattern as DEFERRED (17/25) with schema-field attribution

## Open Questions That Block Step 2

1. Is Task() usage available to the facilitator? (Research Scout's gating uncertainty; performance-analyst's confidence-limiter)
2. Model granularity: tier alias (opus/sonnet) or model ID (claude-opus-4-7)?
3. Scope: only structured agent dispatches, or also informal facilitator responses?

## What This Synthesis Refuses to Build

- A dashboard. SQLite queries answer the comparison in <10ms.
- Real-time streaming, OTel spans, ClickHouse, proxy architectures.
- A pricing table inside close_discussion.py. Store raw token counts; compute cost in views where the formula is easy to update.
- Backfill of historical data from content_excerpt.

## Caveat Stack

- Confidence: 0.78. The primary unknown is whether the facilitator-as-orchestrator pattern exposes Task() usage data inline. If it does not, Step 2 needs a different implementation (likely the opt-in JSONL parser as the only viable path).
- The synthesis took a deliberate position on the schema disagreement (columns on turns + cache fields). If you prefer the cleaner separation, swap in a child table at Step 1; downstream steps are identical.

---
