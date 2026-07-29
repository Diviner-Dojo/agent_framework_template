---
adr_id: ADR-0013
title: "Token-efficiency telemetry via post-hoc JSONL ingest"
status: superseded
superseded_by: ADR-0029
amended_by: ADR-0020
date: 2026-05-12
accepted_date: 2026-06-05
decision_makers: [facilitator, architecture-consultant, performance-analyst, docs-knowledge, project-analyst, independent-perspective]
discussion_id: DISC-20260512-025323-token-efficiency-telemetry
supersedes: null
risk_level: medium
scope: framework
confidence: 0.78
tags: [telemetry, efficiency, instrumentation, capture-pipeline]
---

> **Superseded by ADR-0029 (2026-07-28).** token-efficiency telemetry ingestion was removed; nothing writes the token tables. The decision and its
> reasoning are preserved here; only its status changed.


> **Ratified `proposed` → `accepted` on 2026-06-05** alongside ADR-0020, which
> **amends** §2 ("Cost computation"): accurate per-tier dollar cost is now computed by
> pricing each model *before* aggregating (via the `discussion_model_tokens` breakdown),
> dissolving the mixed-tier objection while preserving compute-don't-store. The
> token-based primary signal here is retained. See ADR-0020.

## Context

The framework captures the **value-side** of agent work — findings, confidence, calibration, protocol yield — but does not capture the **cost-side**. The `turns` and `discussions` tables hold no token counts, no model identity as a first-class field, and no cost. Without the denominator, no efficiency ratio is computable.

The developer is about to begin framework efficiency work (e.g., comparing sonnet vs opus checkpoints, reflection step on/off, Structured Dialogue vs Ensemble at medium-risk) and cannot answer "did this change make us more efficient?" with current instrumentation.

A deliberation surveyed external practice (Claude Code transcript JSONL, LangSmith, AG2, LangChain, AgentOps, Langfuse, Phoenix, OTel, OpenAI evals) and three internal specialists. The constraint is explicit: do not overdesign — measure efficiency, do not build an observability platform.

Three architectural seams emerged with non-trivial disagreement:
1. **Capture path**: live instrumentation at the `Task()` call site vs post-hoc ingest of Claude Code's transcript JSONL at `~/.claude/projects/`.
2. **Model granularity**: tier alias (`opus`/`sonnet`) vs full model ID (`claude-opus-4-7`).
3. **Scope**: instrument only the Task() boundary, or also self-report facilitator overhead.

## Decision

Adopt **post-hoc JSONL ingest as the system of record** for token telemetry, with a minimal schema extension on existing tables.

### 1. Capture path

- **Primary**: a new `scripts/ingest_token_usage.py` scans `~/.claude/projects/{project}/{sessionId}/` (main session) and `subagents/agent-{agentId}.jsonl` (subagent dispatches), dedupes by `message.id`, and writes token data to the `turns` table, attributing turns to discussions by timestamp.
- **Secondary (opportunistic)**: a thin wrapper around `Task()` may parse the trailing `<usage>` block in the response string and attach `usage_partial` tags. This is best-effort; the JSONL ingest is authoritative.
- **Not adopted**: live in-workflow instrumentation that depends on the `<usage>` suffix as a primary source. The suffix is a presentation artifact, exposes only 3 of the 6 needed fields, and creates a load-bearing dependency on an undocumented output format.

### 2. Model granularity

- **Primary**: keep tier alias (`model:opus`) in `turns.tags`. Tier is the stable analytical dimension over years; model IDs churn quarterly.
- **Secondary**: capture full model ID as `model_id:<id>` tag when cheaply available.
- **Cost computation**: at analysis time via a `config/model_pricing.yaml` lookup keyed by full ID, with tier-average fallback. Cost is **never stored**, only computed in views and reports.

### 3. Scope

- Instrument the **Task() boundary** (the architectural seam between facilitator and specialist) opportunistically; let JSONL ingest cover the rest, including facilitator overhead.
- **Not adopted**: facilitator self-reporting of its own token use. The facilitator cannot directly observe its tokens; self-reporting would be fabricated telemetry.

### 4. Schema extensions

Additive only via the existing `_migrations` pattern in `scripts/init_db.py:250` (idempotent, NULL-safe):

- `turns.tokens_in INTEGER`
- `turns.tokens_out INTEGER`
- `turns.cache_read_tokens INTEGER`
- `turns.cache_create_tokens INTEGER`
- `discussions.total_tokens_in INTEGER`
- `discussions.total_tokens_out INTEGER`
- `discussions.total_cache_tokens INTEGER`

New view `v_token_efficiency` joining `discussions` and `protocol_yield` grouped by `command_type`, producing the primary efficiency signal: **blocking findings per 1K output tokens by command_type**.

### 5. Rollup

`scripts/close_discussion.py` aggregates `turns.tokens_*` into `discussions.total_*` after the existing `duration_minutes` computation. Mirrors the LangSmith rollup-at-close pattern.

### 6. Backfill

**No backfill** of historical turns from `content_excerpt`. The excerpt is truncated; estimates would contaminate the baseline. `NULL` in new columns honestly represents "we did not measure this." JSONL ingest may opportunistically populate historical discussions whose JSONL is still on disk, but no synthesis from excerpts.

## Alternatives Considered

### Alternative 1: Live instrumentation by parsing `<usage>` suffix in Task() returns

- **Pros**: in-workflow, no dependency on `~/.claude/projects/` filesystem path; data captured at the moment of the dispatch.
- **Cons**: the suffix is a presentation artifact, not a stable interface. Exposes only `total_tokens`, `tool_uses`, `duration_ms` — no input/output split, no cache breakdown. Wrapping every Task() in a parser puts a load-bearing dependency on output formatting we don't control.
- **Reason rejected**: violates the dependency-direction principle (depend on stable structured data, not presentation). The architecture-consultant's call: "we're choosing the less-fragile of two fragile paths — JSONL has field names, the suffix does not."

### Alternative 2: First-class `model` column on `turns` + token columns

- **Pros**: enables direct `GROUP BY model` queries without parsing tags; structured data.
- **Cons**: duplicates information already in `turns.tags` as `model:<tier>`; creates drift risk between column and tag. Full model ID would churn quarterly.
- **Reason rejected**: tier alias in tags is the stable analytical dimension. Promote to column only when structured queries demonstrably need it.

### Alternative 3: Separate `agent_token_usage` child table

- **Pros**: cleaner separation; turns table is already wide; lets us query token usage without scanning content_excerpt.
- **Cons**: requires joins for most efficiency queries; another table to keep in sync with turns.
- **Reason rejected**: NULL-safe columns on `turns` are simpler and the existing `_migrations` pattern handles them cleanly. The child-table argument may revisit if cache field complexity grows.

### Alternative 4: Facilitator self-reporting of its own token use

- **Pros**: complete picture without depending on external JSONL.
- **Cons**: facilitator cannot directly observe its own tokens; self-reporting is fabricated telemetry. Violates Principle #4 (the generator should not be the sole evaluator) applied at a measurement layer.
- **Reason rejected**: JSONL ingest captures facilitator overhead naturally without fabrication.

### Alternative 5: Full observability platform (OTel + Phoenix/Langfuse + ClickHouse)

- **Pros**: industry-standard span model; rich visualization.
- **Cons**: ClickHouse + Docker + dashboards is two orders of magnitude too heavy for "compare approaches." Wrong scale for a discussion-centric Python CLI framework.
- **Reason rejected**: explicit developer constraint — measure efficiency, do not build an observability platform.

## Consequences

### Positive

- Enables the primary efficiency signal: **blocking findings per 1K output tokens by command_type**.
- Enables three concrete A/B hypotheses immediately upon ingest: sonnet vs opus checkpoints, reflection step on/off, Structured Dialogue vs Ensemble at medium-risk.
- Additive-only schema change — historical data remains valid, `NULL` honestly represents un-instrumented.
- No new pipeline, no new dependencies, no dashboard. Existing `_migrations` and JSONL trend log patterns are reused.
- Cost stays out of stored data — pricing updates are a one-line edit to `model_pricing.yaml`, not a schema migration.

### Negative

- Dependency on `~/.claude/projects/` JSONL path, which is undocumented by Anthropic. If they restructure or rename it, the ingester needs a patch. Mitigation: isolate the parser behind one interface so the impact is one-file (per `.claude/rules/review_gates.md` rule on external API integration).
- No live token visibility during a workflow run — only after JSONL ingest. The `<usage>` suffix gives partial live data but is not authoritative.
- Cache fields (read/create) are new concepts to surface in queries and views; learning curve for the developer.

### Neutral

- Adoption log will record the AG2 schema and LangSmith rollup-at-close patterns; defers the Claude Code JSONL parser as a pattern (17/25) but credits its 4-field schema choice.
- The deliberation surfaced two non-fatal defects in `scripts/close_discussion.py` (broken kwarg in `surface_candidates`, missing `compute_effectiveness` import) — unrelated to this ADR but worth a follow-up.

## Linked Discussion

See: discussions/2026-05-12/DISC-20260512-025323-token-efficiency-telemetry/
