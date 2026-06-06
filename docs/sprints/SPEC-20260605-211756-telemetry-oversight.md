---
spec_id: SPEC-20260605-211756
title: "Telemetry & Oversight: failure/waste lens + visibility surface over the existing capture stack"
type: spec
status: approved
risk_level: medium
reviewed_by: [architecture-consultant, security-specialist, qa-specialist, performance-analyst]
approved_by: developer
approved_at: 2026-06-05
discussion_id: DISC-20260606-041937-telemetry-oversight-spec-review
intake_ids: []
completed_at:
completed_commit:
---

## Goal

Add a **Telemetry & Oversight** component to the framework template (the hub) that
makes the telemetry the framework *already captures* **visible**, and that **catches
where agents fail or waste tokens** — without rebuilding the capture stack and without
becoming a heavyweight observability platform.

Three layers, scoped so the signal layer (A) is fully buildable now and the viewer's
technology (B) is decided once A defines what is worth showing:

- **Layer A — Failure/Waste Analyzer** (the signal): derive operational failure and
  waste signals from data already on disk; compute accurate per-tier dollar cost.
- **Layer B — Unified Viewer** (the surface): one place to see it. Dashboard
  technology is an explicit open decision resolved after Layer A exists.
- **Layer C — Oversight Digest + Loop** (the cheap win): periodic rollup pushed via
  the existing ntfy path, feeding `/meta-review`.

## Context

**The reframe.** The framework is not short on telemetry *capture*. It already has:
per-turn `tokens_in/out` + cache columns and per-discussion rollups
([scripts/ingest_token_usage.py](../../scripts/ingest_token_usage.py), ADR-0013),
[config/model_pricing.yaml](../../config/model_pricing.yaml), the `v_token_efficiency`
and `v_agent_dashboard` views,
[scripts/compute_agent_effectiveness.py](../../scripts/compute_agent_effectiveness.py)
(source of the "ux-evaluator 0% in VerificationPortal" signal),
[scripts/efficiency_report.py](../../scripts/efficiency_report.py),
`metrics/quality_gate_log.jsonl`, and
[scripts/knowledge_dashboard.py](../../scripts/knowledge_dashboard.py). On capture, the
framework is ahead of most comparable tools.

The gaps are three:
1. **No operational failure/waste signal.** Capture is about findings, effectiveness,
   and cost — not *what went wrong during a run* (retry thrashing, orphaned subagents,
   forced-continuation loops, cost-weighted failure ranking).
2. **No visibility surface.** Everything is ASCII tables, JSONL, or raw SQL.
3. **Dollar cost deliberately not computed.** [efficiency_report.py](../../scripts/efficiency_report.py)
   refuses to print dollars because it aggregates across mixed model tiers.

**External survey (this session).** Scouted `toolbeltross/rh-telemetry` +
`rh-claude-framework` (Ross Beveridge's, the dashboard inspiration) and ~10 comparable
projects. Findings that shape this spec:
- The high-value, portable pieces of rh-telemetry are three *derived* failure signals
  (retry-loop via tool+input hash; orphaned subagents; stop-hook forced-continuation
  loops) and cost-weighted failure ranking. ~200 lines of pure event-pattern logic.
- `phuryn/claude-usage` (Python + SQLite + single-page Chart.js, no build step) is the
  closest stack-match for a lightweight viewer; `disler/...multi-agent-observability`
  is the reference hook→SQLite→live-dashboard pattern; `ColeMurray/claude-code-otel`
  (MIT) is the cost/error metric-taxonomy reference; `confident-ai/deepeval`
  (Apache-2.0, pure-Python, pytest-native) is the agent-failure/waste eval that could
  fit the quality gate.
- The genuine **white space**: cost trackers ignore failures, eval frameworks ignore
  cost, hook dashboards skip both — and none ship as an *inheritable framework
  component* that feeds a self-improvement loop. Combining all three in one
  template-inherited component is the differentiator.

**Prior art / precedent.**
- **ADR-0013** (token-efficiency-telemetry, status `proposed`): cost is **never stored**,
  only computed at analysis time from `model_pricing.yaml`; the primary signal is
  token-based ("blocking findings per 1K output tokens") *by design* so tier price
  doesn't confound approach comparison; explicitly rejected "build an observability
  platform" as out of scale. This spec **refines, not reverses** ADR-0013.
- **memory/projects/self-improving-coding-agent.md**: direct precedent (FastAPI +
  WebSocket live callgraph visualization, async LLM oversight). Carries the
  Known-Broken Approach below.
- **memory/projects/claude-agentic-framework.md**: `infra/token-audit` solution path —
  measure per-turn waste (Token Budget Optimization, 22/25 ADOPT).
- **memory/projects/agentic-journal.md**: a `/status Dashboard` pattern was previously
  scored **16/25 → DEFER**. Dashboards have been weighed and deferred before for not
  being worth the weight — *lightweight* is the bar this must clear.

## Requirements

### Layer A — Failure/Waste Analyzer (Phase 1, fully specified)

- **R-A1: Operational failure signal extraction.** A new analyzer derives failure
  signals from data already on disk. **Source ordering (arch finding): the failure
  signals R-A1.1–1.3 live primarily in the Claude Code transcript JSONL under
  `~/.claude/projects/` (tool invocations, subagent lifecycle, stop events) — NOT in
  `discussions/**/events.jsonl` or the `turns` table, which lack tool/subagent detail.**
  The analyzer leads with transcript JSONL for failures and reserves `events.jsonl`/
  `turns` for cost. Where transcript JSONL is absent (common on a fresh derived
  project), R-A1.1–1.3 **degrade to a no-op with a coverage note** rather than erroring.
  - **R-A1.1 Retry-loop detection** — a stable hash of (tool name + normalized input);
    repeated identical invocations within a bounded, **injectable** window flagged as
    thrashing. The **normalization contract is defined** (R-A5).
  - **R-A1.2 Orphaned-subagent detection** — a dispatched subagent with no
    corresponding completion event within the sealed discussion (or no activity beyond
    an **injectable** threshold).
  - **R-A1.3 Forced-continuation / stop-loop detection** — agent continuation with no
    intervening human turn, counted as a budget-drain signal.
  - **R-A1.4 Cost-weighted failure ranking** — rank failures by estimated wasted spend,
    not just count. **Tier-unknown failures appear in the ranking with a clearly marked
    unknown/estimated cost — never silently dropped** (qa finding).
- **R-A2: Accurate per-tier dollar cost.** Compute cost **per turn** (where the model
  tier is known) using `config/model_pricing.yaml`, then aggregate. This resolves the
  mixed-tier aggregation objection in
  [efficiency_report.py](../../scripts/efficiency_report.py) without storing cost
  (ADR-0013 honored). The analyzer reads cost inputs by **joining the existing `turns`
  table** (already-attributed token columns), not by re-parsing raw transcript JSONL.
  - **R-A2.0 Data-reality prerequisite (resolves arch BLOCKING).** Per-turn tier data
    does **not exist in the pipeline today**: `ingest_token_usage.py` parses the JSONL
    `message.model` field but **discards it**, writing only discussion-level
    `total_tokens_*`; `_update_tagged_turns` is a dormant hook returning 0. R-A2 must
    not assume per-turn tier tags are populated. Resolution = **option (ii), the real
    fix**: extend `ingest_token_usage.py` to **persist the already-parsed `message.model`
    per turn** (a `turns.model_id` value or `model_id:<id>` tag), resolved to a tier via
    `model_pricing.yaml`. This is a **separate, explicit acceptance criterion** and a
    capture-pipeline change (additive, NULL-safe). **Fallback** where per-turn model is
    still absent (historical turns): infer tier from the `agent`→tier mapping in the
    roster for single-tier discussions; mark genuinely mixed/unknown turns `unknown`.
    Coverage starts low on historical data and rises as new turns are captured — this is
    honest and acceptable; R-A4's "day-one value" is carried by the failure signals
    (R-A1), not by dollar coverage.
  - **R-A2.1 Coverage honesty.** Turns lacking a resolvable tier are marked
    `unknown`/`estimated`, never silently rated (never zero-rated). Every dollar
    aggregate is accompanied by a **coverage %** computed on a **token denominator**
    (`known-tier tokens / total tokens`), not a turn-count denominator. Coverage % is
    produced in the **same single-pass SQL aggregation** as cost (conditional `COUNT`/
    `SUM`), not a second pass. Mirrors the "log skipped runs honestly" ethic and
    ADR-0013's "NULL = we did not measure this."
- **R-A3: Persistence via the existing pattern.** New signals land in
  `metrics/evaluation.db` via the additive, NULL-safe `_migrations` pattern (e.g. a
  `telemetry_failures` table; cost stays derived, not stored). The analyzer **calls the
  shared `init_db()` for its schema** rather than carrying its own ALTER list (avoids a
  3rd copy of the migration list — arch finding). Table/column names are **hardcoded
  literals, never derived from config or runtime input** (DDL-injection guard — security
  finding). No parallel database, no new JSONL store unless a view-layer reason emerges.
- **R-A4: Retroactive operation + watermark (resolves perf BLOCKING).** The analyzer
  runs over **existing** sealed discussions/transcripts. To avoid re-reading the whole
  corpus every run (430 MB / 1429 files today, growing), it maintains a **high-water-
  mark** and processes only discussions sealed since the last run
  (`WHERE status='closed' AND closed_at > watermark`), persisted in a small
  `telemetry_run_state` row (or a `telemetry_analyzed_at` column on `discussions`). A
  `--full-rescan` flag forces the one-time retroactive pass (mirrors the existing
  `--since` flag). **Idempotent**: dedupe by a defined content hash with
  `INSERT OR IGNORE`; row count is stable across two identical runs (asserted by test).
- **R-A5: Determinism & testability contracts (resolves qa BLOCKING).**
  - **Injectable transcript seam.** The `~/.claude/projects/` path is an injectable
    module constant / parameter (equivalent to `CLAUDE_PROJECTS_ROOT` in
    `ingest_token_usage.py`); **no test reads the developer's live `~/.claude`**. The
    analyzer **reuses `discover_session_dirs`/`parse_session_dir`** and does not re-walk
    the path itself; it also reuses the `_is_inside_projects_root` traversal guard.
  - **Injectable time thresholds.** Retry/orphan/stop-loop windows are injectable params
    with defaults; tests use synthetic timestamps — **no `time.sleep`, no global
    `datetime.now()` mock**.
  - **Retry-hash normalization contract.** Defined and tested: trailing whitespace,
    JSON key ordering, and tool-version suffixes are treated as equivalent (or
    explicitly distinct — the choice is stated).
  - **Transport-fidelity boundary, declared.** Unit tests cover parsing/signal logic
    against `tmp_path` fixtures; live path discovery is exercised only by an out-of-band
    smoke check, not pytest. Stated explicitly so passing tests are not mistaken for
    end-to-end transport coverage.
  - **Streaming parse.** Transcript JSONL is read line-by-line (follow
    `parse_session_dir`), never loaded whole into memory.

### Layer B — Unified Viewer (Phase 2, technology = OPEN DECISION)

- **R-B1: One surface.** Read `metrics/evaluation.db` — existing views
  (`v_agent_dashboard`, `v_token_efficiency`) **plus** the Layer-A tables — and present
  them together. Replaces scattered ASCII/JSONL/raw-SQL access.
- **R-B2: Minimum views (technology-agnostic).** Whatever the stack: (a) per-model /
  per-agent cost breakdown with coverage %; (b) cost-weighted failure list with
  error-class grouping; (c) per-command-type token-efficiency (existing signal,
  surfaced); (d) recurring-failure trend.
- **R-B3: Technology decision deferred.** Resolved after Layer A exists. Candidates,
  least-complex-first (Principle #8): **(i)** static HTML/markdown render on a schedule
  (no server); **(ii)** FastAPI + SQLite + single-page Chart.js, no build step
  (phuryn/claude-usage shape) — *current front-runner*; **(iii)** live React/WebSocket
  SPA (rh-telemetry shape) — richest, heaviest, a JS build pipeline inside a Python
  template. The viewer must not regress the "16/25 DEFER" weight verdict — if the only
  justifiable option is heavy, prefer (i)/(ii) and log the tradeoff.
  - **R-B3.1 Viewer security controls (carry into the R-B3 ADR).** If a server (FastAPI)
    is chosen: bind to **`127.0.0.1` only** (never `0.0.0.0`); **no wildcard CORS**
    (serve JS same-origin so CORS is unneeded); return **generic errors** only (never
    raw DB/internal exceptions); auth required for any non-read-only endpoint. Any
    front-end dependency (e.g. Chart.js) is **pinned to an exact version or vendored**
    locally — no `/latest` CDN float. `redact_secrets.py` runs before any content is
    rendered.

### Layer C — Oversight Digest + Loop (Phase 3, cheap win)

- **R-C1: Periodic digest.** A rollup of recurring failure classes and cost spikes
  (24h/7d windows), emitted via the existing [scripts/notify.py](../../scripts/notify.py)
  ntfy path (`notifying-the-developer` skill). No new UI required for value.
  - **R-C1.1 Aggregates-only content (resolves security BLOCKING).** The digest body is
    assembled **exclusively from DB-level aggregates** — failure-class enum, occurrence
    counts, estimated wasted spend, coverage %. It **MUST NOT** include any string
    sourced from transcript/event content (no "representative excerpt"). This is a
    *structural* constraint, distinct from and additional to `redact_secrets.py`. Topic
    slug is never printed, even on error paths (always-on invariant).
- **R-C2: Feed the self-improvement loop.** The digest is consumable by `/meta-review`
  (the quarterly macro loop) so telemetry informs framework evolution — the
  differentiator no comparable project ships.
  - **R-C2.1 Schema-constrained hand-off (resolves security BLOCKING).** Content passed
    to `/meta-review` is limited to the same schema-constrained aggregate fields — never
    free-text transcript excerpts. This is a **separate control** from the KV-cache rule
    (R below): KV-cache protects the *live agent prompt*; this protects the *meta-review
    consumption path* from stored-content prompt injection (A03).

## Constraints

- **KNOWN-BROKEN — never inject changing metrics into agent context.** From
  `memory/projects/self-improving-coding-agent.md` (`llm/cache-stability`): putting
  cost/budget/telemetry into agent prefill invalidates the KV cache (observed 25% cost
  *increase* vs 90% decrease). Layer C and any "feedback loop" must surface telemetry to
  **humans / out-of-band channels only** — never into live agent prompts.
- **Refine, don't reverse ADR-0013.** Cost stays **derived at analysis time, never
  stored**. The token-based efficiency signal is retained for approach comparison; the
  new dollar view answers a *different* question (where money goes) and coexists. Fold
  the dollar-cost refinement into this component's ADR as an **ADR-0013 amendment**.
- **No observability platform.** ADR-0013's explicit scope limit holds: no ClickHouse /
  Prometheus / Grafana / OTel-collector stack embedded in the template. Stay in-tree,
  SQLite-backed, dependency-light.
- **Reuse, don't duplicate.** Build on `evaluation.db`, `model_pricing.yaml`,
  `ingest_token_usage.py`, `notify.py`, `init_db.py` migrations, existing views. No
  parallel store, no parallel cost table.
- **Attribution (Prime Objective / refuse-extraction, ADR-0015).** Patterns are
  *rebuilt in Python*, not lifted (Ross's repos are Node/JS). rh-telemetry is MIT —
  credit Ross Beveridge in the ADR/source. **Do NOT bundle `Arize-ai/phoenix`** — it is
  Elastic License 2.0 (redistribution-restricted) and this template is inherited by
  derived projects.
- **Progressive disclosure (ADR-0016).** Do not bloat CLAUDE.md; component detail lives
  in a path-scoped doc/skill + a docs pointer.
- **Template-is-the-hub.** Success is measured by derived-project usefulness, not
  template-local activity. The component must degrade gracefully where data is sparse
  (a fresh derived project with few discussions).
- **Stdlib + existing deps only for Layer A** (Python 3.11+, sqlite3, yaml). Any viewer
  dependency (e.g. FastAPI is already a stack dep; Chart.js via CDN) is decided in R-B3.
- **Security baseline.** Transcript/event content is untrusted input: parse defensively,
  parameterized SQL only, `redact_secrets.py` before any content is surfaced in a digest
  or viewer, and never expose raw DB/internal errors.

## Acceptance Criteria

### Layer A (Phase 1 — required for this spec to be "complete")
- [ ] Analyzer detects retry-loops, orphaned subagents, and forced-continuation loops,
      reading failure signals from transcript JSONL; degrades to a no-op with a coverage
      note when transcript JSONL is absent.
- [ ] Failures are ranked by cost-weighted wasted spend; **tier-unknown failures appear
      in the ranking marked unknown/estimated, not dropped** (fixture: 2 known + 1
      unknown tier asserts the unknown one is present).
- [ ] `ingest_token_usage.py` is extended to **persist per-turn `model`/tier** from the
      already-parsed `message.model`; per-turn cost is computed from the `turns` table
      then aggregated; **cost is not stored** (verified by schema inspection).
- [ ] Every dollar figure reports a **coverage % on a token denominator**, computed in a
      single-pass aggregation; tier-unknown turns are marked `unknown` (never zero-rated);
      test asserts `coverage_pct < 100` and cost based only on known turns.
- [ ] New schema lands via the shared `init_db()`; migration test covers fresh DB,
      existing-without-table, existing-with-table, **and existing-with-table-missing-a-
      column**, asserting columns exist via `PRAGMA table_info` after each.
- [ ] Idempotent: `INSERT OR IGNORE` with a defined content-hash key; **row count stable
      across two identical runs** (asserted).
- [ ] **Watermark**: a second run with no new sealed discussions does no re-processing;
      `--full-rescan` forces a full pass (both asserted).
- [ ] **Injectable seams**: transcript path and time thresholds are injectable; no test
      reads live `~/.claude` or real `discussions/`; no `time.sleep`/global datetime mock.
- [ ] Retry-hash normalization contract tested (whitespace / JSON key order / version
      suffix treated per the stated choice).
- [ ] Edge-case fixtures: corrupt/truncated JSONL line skipped; empty `events.jsonl`;
      dispatch-without-completion; fresh empty DB; sparse 1-discussion DB.
- [ ] All analyzer SQL is parameterized; a test asserts SQL-injection-shaped tool
      names/inputs do not corrupt the DB.
- [ ] Graceful no-op with an informative message when `evaluation.db` is absent/empty.
- [ ] `redact_secrets.py` test covers short tokens and `NTFY_TOPIC`-shaped strings.
- [ ] A `memory/bugs/regression-ledger.md` entry is added for the `init_db.py` migration
      before commit.
- [ ] ruff format + ruff check clean; pytest passes; coverage ≥ 80% (transport-fidelity
      boundary declared for the live-path code).

### Layer B (Phase 2 — gated on the R-B3 technology decision)
- [ ] Technology decision recorded (in the ADR) with rationale vs the "16/25 DEFER"
      weight bar.
- [ ] The four minimum views (R-B2) render from `evaluation.db`.
- [ ] Viewer degrades gracefully on sparse/empty data.

### Layer C (Phase 3)
- [ ] Digest emits recurring-failure + cost-spike summary via `notify.py`; secrets
      redacted; topic slug never printed (per always-on invariant).
- [ ] **Digest body contains only schema-constrained aggregate fields** (enum, counts,
      estimated spend, coverage %); **no raw transcript text / tool output / free-text
      excerpts** (verified by review + a content-assembly test).
- [ ] Content handed to `/meta-review` is limited to the same aggregate fields — no
      free-text transcript content (stored-content prompt-injection guard).
- [ ] No telemetry is injected into any agent prompt (KV-cache constraint verified by
      review) — *distinct* from the meta-review hand-off control above.
- [ ] `/meta-review` can consume the digest output.

### Cross-cutting
- [ ] ADR written for the component **including the ADR-0013 dollar-cost amendment** and
      Ross/rh-telemetry attribution.
- [ ] Docs pointer added; CLAUDE.md not bloated (progressive disclosure).
- [ ] Framework doc sync per `syncing-framework-docs` skill.

## Risk Assessment

- **Medium — schema/pipeline change.** New table + analyzer touch the capture stack.
  Mitigation: additive `_migrations` guard (proven pattern), idempotent re-runs,
  migration tests.
- **Medium — philosophy refinement (dollar cost).** Reverses an
  [efficiency_report.py](../../scripts/efficiency_report.py) stance. Mitigation: it is a
  *refinement* consistent with ADR-0013 (compute-don't-store), documented in an ADR
  amendment; coverage-% honesty prevents fabricated precision.
- **Medium — scope creep into an observability platform.** The 16/25-DEFER history and
  ADR-0013's explicit scope limit are the guardrails; Layer B technology is chosen
  least-complex-first.
- **Low — transcript JSONL path dependency** (`~/.claude/projects/`, undocumented).
  Mitigation: isolate parsing behind one interface (per ADR-0013's existing mitigation),
  degrade gracefully when absent.
- **Low (but high-impact if ignored) — KV-cache regression** from injecting metrics into
  prompts. Mitigation: hard constraint above + review check.

## Affected Components

### New
- `scripts/` analyzer module(s) for Layer A (e.g. `scripts/telemetry/analyze.py` or a
  cohesive module set; final layout decided in `/build_module`).
- New `evaluation.db` table(s) (e.g. `telemetry_failures`) via `init_db.py` migrations.
- Tests: analyzer signals, per-tier cost + coverage, migration, idempotency.
- ADR: component decision + ADR-0013 dollar-cost amendment + attribution.
- Layer B viewer artifact(s) — type per R-B3 decision.
- Layer C digest hook/script (extends `notify.py` usage).
- A path-scoped doc or skill describing the component (progressive disclosure).

### Modified
- `scripts/init_db.py` (additive migration).
- Possibly `scripts/close_discussion.py` (optional: trigger analyzer at seal time —
  evaluate in build; retroactive batch is the baseline).
- `/meta-review` command (consume digest) — Phase 3.
- `CLAUDE.md` (minimal pointer only), `docs/FRAMEWORK_SPECIFICATION.md` + presentations
  (doc sync).

### Explicitly unchanged
- Existing cost/token capture (`ingest_token_usage.py`, `model_pricing.yaml`,
  `v_token_efficiency`) — built upon, not modified.
- The token-based efficiency signal — retained.

## Dependencies

- **Depends on**: `metrics/evaluation.db` (`turns` token columns, `discussions`
  rollups), `config/model_pricing.yaml`, `init_db.py` `_migrations` pattern,
  `scripts/notify.py`, `scripts/redact_secrets.py`, sealed `discussions/`.
- **Depends on this**: `/meta-review` self-improvement loop (Layer C); derived projects
  inherit the component.

## Open Decisions (resolve before/within build)

1. **R-B3 — viewer technology** (static render vs FastAPI+Chart.js vs React/WebSocket).
   Developer deferred; resolve after Layer A defines the data. Front-runner:
   FastAPI + SQLite + Chart.js (least-complex that still satisfies "visible").
2. **Analyzer trigger** — **RESOLVED (spec review): batch + watermark; seal-time
   trigger in `close_discussion.py` DECLINED.** Rationale: `close_discussion.py` is a
   7-step synchronous hot path; the watermark (R-A4) makes the next batch run pick up a
   newly-sealed discussion cheaply, so the seal-time trigger adds latency for no gain.
3. **deepeval adoption** — whether to wire `confident-ai/deepeval` (Apache-2.0,
   pytest-native) agent-failure metrics into the quality gate, or keep Layer A
   self-contained first. Lean: self-contained first, deepeval as a later adopt.

## Phasing

Phase 1 (Layer A) is independently valuable and shippable. Phase 2 (Layer B) gated on
the R-B3 decision. Phase 3 (Layer C) is small and can follow either. This spec is
approvable for **building Layer A now** while the viewer technology is decided.

## Spec Review Summary

Reviewed by architecture-consultant (0.84), security-specialist (0.87), qa-specialist
(0.87), performance-analyst (0.88) — all **APPROVE-WITH-CHANGES**. Discussion:
`DISC-20260606-041937-telemetry-oversight-spec-review`.

**8 BLOCKING findings — all addressed in this revision:**
1. *(arch)* Per-turn tier data doesn't exist today (`message.model` parsed-then-
   discarded) → R-A2.0: extend `ingest_token_usage.py` to persist per-turn model; honest
   low-and-rising coverage; day-one value carried by R-A1 failure signals, not dollars.
2. *(sec)* `/meta-review` prompt-injection via stored content → R-C2.1: schema-
   constrained aggregates only.
3. *(sec)* ntfy digest could exfiltrate transcript text → R-C1.1: structural
   aggregates-only constraint, distinct from redaction.
4. *(qa)* Injectable transcript seam → R-A5: injectable path, reuse
   `discover_session_dirs`/`parse_session_dir`, no live `~/.claude` in tests.
5. *(qa)* Migration test must assert columns exist + partial-migration scenario →
   acceptance criteria updated (PRAGMA + 4th scenario).
6. *(qa)* Undefined contracts (retry-hash normalization, dedupe key, unknown-tier
   ranking) → R-A1.1/R-A1.4/R-A4/R-A5 define them.
7. *(qa)* Non-deterministic thresholds → R-A5: injectable, no sleep/global-mock.
8. *(perf)* O(corpus) full re-scan → R-A4: watermark + `--full-rescan`; Open Decision 2
   resolved (seal-time trigger declined).

**Advisories carried into `/build_module`:** lead failure-signal sources with transcript
JSONL; consume `turns` table for cost (avoid N+1); streaming parse; single-pass coverage
%; hardcoded DDL names + traversal guard reuse; FastAPI localhost/CORS/generic-errors +
Chart.js pinning (R-B3.1, gated on the viewer decision); `redact_secrets` short-token
test; window-boundary tests; init_db regression-ledger entry at commit.

**Open decisions remaining:** R-B3 viewer technology (deferred by developer); whether to
wire `deepeval` later (lean: Layer A self-contained first).

**Note:** ADR-0013 is still `status: proposed`; the build ADR should ratify it or cleanly
reference it when recording the dollar-cost amendment + rh-telemetry attribution.
