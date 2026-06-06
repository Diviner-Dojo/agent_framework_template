---
adr_id: ADR-0020
title: "Telemetry & Oversight component (failure/waste lens + visibility) and per-tier cost amendment to ADR-0013"
status: accepted
date: 2026-06-05
decision_makers: [facilitator, architecture-consultant, security-specialist, qa-specialist, performance-analyst, steward]
discussion_id: DISC-20260606-041937-telemetry-oversight-spec-review
spec_id: SPEC-20260605-211756
supersedes: null
amends: ADR-0013
risk_level: medium
scope: framework
confidence: 0.86
tags: [telemetry, oversight, cost, observability, adr-0013-amendment, attribution, compute-dont-store]
---

## Context

The framework captures rich telemetry (per-discussion token rollups via ADR-0013,
agent effectiveness, quality-gate trends, findings/patterns) but it is **not visible**
(ASCII tables, JSONL, raw SQL) and it carries **no operational failure/waste signal**
(retry thrashing, orphaned subagents, forced-continuation loops) and **no dollar cost**
([efficiency_report.py](../../scripts/efficiency_report.py) deliberately refuses dollars
because it aggregates across mixed model tiers).

A session survey of `toolbeltross/rh-telemetry` + `rh-claude-framework` (Ross Beveridge)
and ~10 comparable projects (`disler/...multi-agent-observability`, `phuryn/claude-usage`,
`ColeMurray/claude-code-otel`, `confident-ai/deepeval`, Langfuse, Phoenix, ccusage, …)
found a genuine white space: cost trackers ignore failures, eval frameworks ignore cost,
hook dashboards skip both — and none ship as an *inheritable framework component* feeding
a self-improvement loop.

The component is specified in
[SPEC-20260605-211756-telemetry-oversight.md](../sprints/SPEC-20260605-211756-telemetry-oversight.md),
reviewed by four specialists (all APPROVE-WITH-CHANGES; 8 blocking findings resolved
in-spec), and Steward-gated APPROVE (0.86) with 5 conditions.

## Decision

Adopt a three-layer **Telemetry & Oversight** component, built on the existing capture
stack — not a parallel store and **not an observability platform** (ADR-0013's explicit
scope limit holds).

- **Layer A — failure/waste analyzer + per-tier dollar cost** (this build delivers
  **A1, cost**). A2 (failure signals) is a separate, gated build.
- **Layer B — unified viewer.** Technology deferred (own gate, R-B3); a prior `/status`
  dashboard scored 16/25 → DEFER, so the bar is *lightweight*.
- **Layer C — oversight digest** via the existing ntfy path, feeding `/meta-review` to
  close the self-improvement loop.

### Per-tier cost — amendment to ADR-0013 (the load-bearing decision)

ADR-0013 established **cost is never stored, only computed at analysis time** from
`config/model_pricing.yaml`, and chose a *token-based* primary efficiency signal so model
tier price does not confound approach comparison. Both still hold. ADR-0013 §2, however,
also says cost is *"computed in views and reports"* — it never banned dollars; it only
declined to **store** them. [efficiency_report.py](../../scripts/efficiency_report.py)'s
refusal to *print* dollars was a narrower honesty guard against applying one rate to a
**mixed-tier aggregate**.

This ADR **amends** ADR-0013 to add accurate dollar cost by computing it **per model
before aggregating**: a new `discussion_model_tokens` table persists the per-discussion,
per-model token breakdown (the cost **input** — never a dollar figure), and dollars are
computed at read time from `model_pricing.yaml`. This dissolves the mixed-tier objection
without violating compute-don't-store. The token-based efficiency signal is **retained**;
the dollar view answers a *different* question (where money goes) and coexists.

**Coverage honesty:** every dollar aggregate carries a **coverage %** on a *token*
denominator; a model id that resolves to no known tier is marked `unknown` and is **never
zero-rated** — it counts toward the denominator but not the cost total. (The live
first-run measured 100% coverage, $655.83 over 264.9M tokens across 36 discussions.)

### ADR-0013 status

As part of this work, **ADR-0013 is ratified `proposed` → `accepted`** (Steward
condition #4, developer-approved). Amending a never-accepted ADR was poor provenance; the
ratification + this amendment give a clean record that propagates to derived projects.

### Attribution (Prime Objective / ADR-0015)

Patterns are **rebuilt in Python**, not lifted (Ross's repos are Node/JS). `rh-telemetry`
is MIT — **credit Ross Beveridge**. `Arize-ai/phoenix` is **excluded** (Elastic License
2.0, redistribution-restricted; this template is inherited by derived projects).

## Alternatives Considered

### Alternative 1: Per-turn model attribution (`turns.model_id`)
The spec's first framing. **Rejected** because Claude Code transcript messages do not map
1:1 onto framework `turns` rows (turns are framework dialogue events; messages are runtime
API calls attributed by timestamp window). A per-discussion, per-model breakdown is the
accurate, queryable cost substrate; per-turn attribution would have invented a linkage
that does not exist.

### Alternative 2: Store dollar cost in the database
**Rejected** — violates ADR-0013 compute-don't-store. Pricing churns (a YAML edit must not
be a schema migration), and a stored dollar figure would silently rot when rates change.
We store the token breakdown (the stable input) and compute dollars at read time.

### Alternative 3: Full observability platform (OTel + Grafana/Prometheus, or Langfuse/Phoenix)
**Rejected** — ADR-0013's explicit scope limit ("measure efficiency, do not build an
observability platform"). ClickHouse/Prometheus/Grafana is two orders of magnitude too
heavy for an in-tree, SQLite-backed template; Phoenix is additionally ELv2 (redistribution-
restricted) and cannot be bundled into a template derived projects inherit. These remain
optional *graduation* backends a derived project may adopt, not the embedded default.

### Alternative 4: Recompute cost from transcripts on every read (no breakdown table)
**Rejected** on performance grounds (performance-analyst BLOCKING finding): a full
transcript re-scan is O(corpus) — 430 MB / 1429 files today, growing unboundedly.
Persisting the per-model breakdown + a watermark makes reads cheap and runs incremental.

### Alternative 5: A separate `telemetry.db`
**Rejected** — reuse `evaluation.db` (the reuse-don't-duplicate constraint). A parallel
store would fork the schema, the migration path, and the backup story for no benefit.

## Consequences

### Positive
- Per-tier dollar cost is now computable and honest (coverage-gated), filling the gap
  `efficiency_report.py` left open; the "token rollup skipped / no per-tier cost" state is
  resolved.
- Built additively on `evaluation.db`, `ingest_token_usage.py`, `model_pricing.yaml`,
  `init_db.py`, `notify.py` — no parallel store, no new runtime deps (A1 is stdlib + yaml).
- Pure logic in `src/telemetry/` (coverage-measured); transport in `scripts/telemetry/`
  behind a declared transport-fidelity boundary.

### Negative / risks (mitigated)
- Per-turn tier data does not exist (transcript `message.model` was parsed-then-discarded);
  resolved by a **per-discussion-per-model** breakdown rather than per-turn attribution
  (transcript messages do not map 1:1 to framework turns).
- Dependence on the undocumented `~/.claude/projects/` path — isolated by **reusing**
  `ingest_token_usage`'s parser + `_is_inside_projects_root` guard (one-file-patch).
- **KNOWN-BROKEN guard:** telemetry must never enter a live agent prompt (KV-cache
  invalidation — `memory/projects/self-improving-coding-agent.md`). Layer C/`/meta-review`
  hand-off is constrained to schema-bound aggregates (enforced in A2/C builds).

### Neutral
- Carried advisories (to /review): promote reused `ingest_token_usage` helpers to public;
  add an allowlist/pragma to the pre-existing `init_db` f-string DDL.

## Linked Discussions
- Spec review: discussions/2026-06-06/DISC-20260606-041937-telemetry-oversight-spec-review/
- Steward gate: (framework-evolution review, APPROVE 0.86, 5 conditions)
- Build (A1): discussions/2026-06-06/DISC-20260606-063822-build-telemetry-cost-a1/
