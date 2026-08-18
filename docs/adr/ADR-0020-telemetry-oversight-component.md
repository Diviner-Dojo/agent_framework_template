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

A session survey of `toolbeltross/rh-telemetry` + `rh-claude-framework` (Ross Barbieri)
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
is MIT — **credit Ross Barbieri**. `Arize-ai/phoenix` is **excluded** (Elastic License
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

## Implementation note — Layer A2 (failure signals), 2026-06-06

A2 detects token-waste failures over the same transcript corpus, persisted to a
new `telemetry_failures` table (wasted tokens + tier as the cost INPUT; dollar
weight derived at read — same compute-don't-store rule as A1). Two decisions made
during the build, grounded on real transcripts (NOT the spec's assumptions):

- **The subagent dispatch tool is named `Agent`, not `Task`.** CLAUDE.md still
  documents `Task(subagent_type=...)`; that name returns zero matches across the
  whole transcript corpus. A2 keys on `Agent`. Subagent transcripts live in
  `<sessionId>/subagents/agent-<id>.jsonl` and carry no back-link to their
  dispatch id — so a no-result orphan is detected parent-side (tokens left
  honestly uncosted) and a hung subagent is detected from its own transcript's
  non-clean terminal. (See the `reference_subagent_transcript_layout` memory.)
- **The third failure class (stop-loop / forced-continuation) is deferred to
  A2.1.** No reliable transcript signal was found — only a rare `stop_hook_summary`
  record and ambiguous `"continue."` user messages (indistinguishable from a human
  typing it). Shipping a guessed detector would violate the smoke-test-fidelity
  lesson; the two grounded classes (`retry_loop`, `orphaned_subagent`) ship now.
- **The A1 watermark perf advisory is folded in** for the failures path via an
  mtime watermark (`failures_last_analyzed_mtime`) using a `>=` boundary to avoid
  the same-timestamp silent-skip the A1 review caught. The cost path
  (`ingest_token_usage`) retrofit remains a carried advisory.

## Implementation note — Layer A3 (value-vs-subscription + estimate cross-check), 2026-06-06

A3 turns A1's bottom-up dollar cost into two **local, credential-free** honesty
metrics that feed the north-star Layer B dashboard. Four decisions:

- **The programmatic Cost API is superseded as a data source.** The developer
  runs on a flat Claude Code **subscription** under an **individual account**, so
  the Cost/Usage/Claude-Code-Analytics APIs are all unavailable (each needs an
  Admin key + a real multi-member org) and would read ≈$0 against these tokens
  anyway. A3's source is therefore local: A1's stored cost, an un-windowed
  attribution baseline, the OpenTelemetry export, and the subscription fee as a
  config input. (Recorded as a known-broken approach in `memory/projects/_self.md`,
  not the regression ledger — the ledger parser treats every pipe row as a
  fixed-bug entry.)
- **Compute-don't-store is reaffirmed and A3 adds no table.** Leverage is a pure
  read over a `CostReport` parameter + the fee; the cross-check is pure divergence
  logic. Nothing dollar- or ratio-shaped is persisted (a `@pytest.mark.regression`
  guard asserts no new A3 table and no stored dollar/ratio).
- **Two pinned independent sources, no registry** (`IndependentEstimate` dataclass):
  an always-available **attribution baseline** (un-windowed per-model aggregation,
  same `PricingTable` — divergence measures the un-attributed share of total spend,
  `flaw_class="attribution"`) and the **OTel export** (`claude_code.cost.usage`,
  independent pricing, `flaw_class="pricing"`) which reports honest absence when
  the export file is missing — the common case. Live A3 on real data: A1 $666.26
  / 100% coverage; attribution baseline $2,244.53 ⇒ framework discussions account
  for ~30% of total project AI spend; OTel cross-check honestly unavailable.
- **A3 is a third consumer of the `ingest_token_usage._` private helpers**
  (`_collect_messages`, `discover_session_dirs`, `_parse_since`, `_is_inside_projects_root`),
  reused — not promoted (that is the deferred A-ARCH1 public-surface decision). A3's
  own new exports in `src/telemetry/__init__.py` are public-clean.

## Implementation note — Layer B (the north-star dashboard), 2026-06-07

Layer B is the **render-only** surface the data foundation was always in service
of: a single self-contained static HTML infographic, generated locally at
read-time, that makes the A1/A2/A3 outputs **visible**. Steward-approved form
factor (DISC-20260607-063709, 0.88): static HTML mirroring the `/status`
precedent — categorically lighter than the deferred FastAPI/web-app server
(Principle #8). Build = **render, not new measurement.** Key decisions:

- **Read-side functions only, no forked computation (spec R7/C1).** The dashboard
  reads the stored Layer-A outputs through the read-side path — `load_cost_rows` →
  `build_cost_report` (A1), `load_failure_signals` → `rank_failures` (A2, the full
  stored corpus), and a new **shared read-only A3 assembler** `assemble_value_inputs`
  that both the A3 CLI (`analyze_value`) and the dashboard call. It **never** calls
  `analyze_cost()` / `analyze_failures()` / `init_db()` (they mutate the DB); the DB
  is opened `file:...?mode=ro` and a missing telemetry table is caught and mapped to
  the analyzer-not-yet-run absence state. The A3 extract-method resolves rather than
  worsens the deferred A-ARCH1 private-cross-module smell (one read-only path).
- **Layering (corrects the spec's component note).** The coverage-counted pure
  layer `src/telemetry/dashboard.py` holds `DashboardData`, the `html.escape`
  helpers, the inline HTML template, `render_dashboard_html`, and the ASCII
  `render_console_summary`. The read-side loader library
  `scripts/telemetry/dashboard.py` holds `assemble_dashboard_data` and the
  public loaders (DB/transcript IO); the CLI (`main`, `--render-static`,
  `--summary`) lives on the transport `scripts/telemetry/dashboard_server.py`
  (the loader module's one-shot `main` was retired into `--render-static` by
  SPEC-20260610-035920 — in-place factual update, decision unchanged). `src/`
  does not import `scripts/` (the package `__init__` declares I/O
  orchestration lives in `scripts/telemetry/`).
- **Escaping is a deliberate divergence from `/status` (spec C6).** `git_visualize.py`
  interpolates raw git-plumbing output into `innerHTML` (safe — controlled); the
  dashboard renders **server-side** with `html.escape()` in Python on every dynamic
  string (failure signature/detail/tier, divergence reason/source_label, fee labels)
  because Layer-A strings are transcript-shaped. The injection guard targets the
  transcript tool-name feeding `FailureSignal.signature`.
- **Honest absence is a first-class visual state (spec R3a / Steward C4).** Not-yet-
  run / not-configured / unavailable render in a **distinct dashed-border + icon**
  container (distinction by shape/icon, not color alone — WCAG 1.4.1) with a plain-
  language `[what]. [why]. [action]` sentence; a **true zero** (analyzer ran, found
  nothing) uses the normal **data** tile ("No failure signals detected"); OTel
  absence renders a live "enable OTel" `<a>` link. The build attaches per-state
  screenshots so `/review` can probe this axis visually.
- **Plain-language for the manager-gatekeeper (spec R2a).** The A1 panel carries the
  pay-per-use legend ("what the same tokens would cost at API pay-per-use — not what
  you paid"); the A3 multiple is labelled **"List-price-equivalent multiple"** with
  a legend. The console summary is ASCII-only (cp1252 — the 4th guard of that class).
- **Privacy / no standing process (spec R6/C9).** One-shot generate → write to the OS
  temp dir (never the repo tree) → open browser → ASCII summary. No daemon, no
  refresh. A defensive `.gitignore` entry covers the conventional filename. Live on
  real data: A1 $666.26 / 100%, 1 failure signal, fee-not-configured + OTel-not-yet-
  active honest-absence states.

## Implementation note — Layer B form-factor amendment (Phase 1 live daemon), 2026-06-07

The shipped static HTML Layer B (commit `f1bc2a5`) categorically cannot show
live agent lanes, context runway, per-turn cost, or in-flight orphan detection
— that is a *form-factor* gap, not a polish gap (see
`docs/reviews/ANALYSIS-20260607-rh-oversight-deepdive.md`). The Steward
*form-factor* gate (separate from the original 5 build conditions) ran on
2026-06-07 and reached **APPROVE 0.86**, overturning the no-standing-process
constraint of DISC-20260607-063709 with 9 binding conditions. The user-launched
localhost-only daemon is the new Layer B shape; the prior static dashboard is
not deleted but folds into the same code path as a future `--render-static`
export mode (spec R4 / R15).

**Phase 1 (live core) — landed in this commit:**

* NEW `scripts/telemetry/dashboard_server.py` — FastAPI app, hardcoded
  ``127.0.0.1`` bind, no ``--host`` flag, no ``HOST`` env read, runtime guard
  before ``uvicorn.run()``, ``HostHeaderGuard`` + same-origin CORS (R8a),
  htmx-polled live fragment + retrospective fragment that reuses the existing
  ``assemble_dashboard_data`` + ``render_dashboard_html`` path (R15 single
  render path), vendored static mount, read-only DB (``mode=ro``), generic
  error bodies (no DB path / no exception class), lifespan-reset live state.
* NEW `src/telemetry/live.py` — pure events→LiveState fold (R14/AC14): no
  ``scripts.*`` imports, no transcript IO, frozen dataclasses, per-request
  idempotent fold. Live cost mirrors the A1 read-side via
  ``PricingTable.cost_usd`` so live and stored figures cannot diverge.
* Extended `src/telemetry/dashboard.py` with live-panel render helpers
  (agent lanes, runway gauge with amber/red, live cost/failure stream) — same
  ``_esc`` / ``_fmt_*`` / ``_absence_tile`` helpers as the static doc; honest
  absence preserved (cold-start runway shows "not enough data yet", never a
  fabricated ``0`` estimate).
* NEW `src/telemetry/static/` — vendored htmx 1.9.12 (SHA384 recorded in the
  README) served from the FastAPI static mount; eliminates the only outbound
  load-time dependency (R11a / AC6). Chart.js will be vendored when Phase 2
  first uses it.
* **A-ARCH1 promotion landed** (R16/AC15, Phase 1 prerequisite): the four
  cross-module-consumed transcript helpers
  (``collect_messages``, ``discover_session_dirs``, ``parse_since``,
  ``is_inside_projects_root``) are public on
  ``scripts.ingest_token_usage``; the dashboard daemon is the 4th consumer.
  The three prior call sites (``analyze_cost``, ``analyze_failures``,
  ``analyze_value``) + two test files are updated. A contract test in
  ``tests/test_dashboard_server.py`` locks the public surface.

**Re-affirmation (Ross Barbieri, MIT):** the rh-claude-framework reference
that inspired the form-factor decision is attributed in
``docs/reviews/ANALYSIS-20260607-rh-oversight-deepdive.md``; no JS or fixture
JSON from that repo is lifted (analysis §5 contamination guard). Error-class
vocabulary may be reused as domain terms.

**Phase 1 acceptance carried:** AC1-AC10 (all 9 Steward conditions), AC14
(live.py purity seam), AC15 (A-ARCH1 promotion), AC16 (port-in-use clear
message), AC17 (quality gate). Deferred to later phases: AC11 (authored
fixture-transcript inventory — lands with Phase 2 once a background watcher
replaces lazy-per-request folding), AC12 (``--render-static`` parity — Phase 5),
AC13 (cost from tokens × pricing — already enforced structurally by reusing
the A1 read side; no separate test added).

**Two checkpoints fired during the build, both APPROVE on Round 1 / 2:**
architecture-consultant + qa-specialist on ``live.py`` (architecture 0.88
APPROVE; qa 0.92 REVISE → 0.90 APPROVE Round 2 — 28 unit tests written + 1
arch-F1 fix (uncosted-turns accounting separated from priced-cost total) +
1 arch-F2 fix (runway rolling avg scoped to main-lane-only so a Haiku
subagent cannot skew the main-Opus estimate)); security-specialist +
architecture-consultant on ``dashboard_server.py`` (security 0.91 APPROVE
— two-layer bind guard + Host-header middleware + read-only URI + generic
errors; architecture 0.86 APPROVE — pure/transport boundary held, R15 single
render path verified, A-ARCH1 helpers consumed; one Low arch finding folded
in-checkpoint: removed an inverted ``mark_orphans`` call from the lazy
per-request fold — orphan transition needs a session-end signal that lazy
folding does not have).

## Implementation note — per-call cost/cache instrument (SPEC-20260716-093231), 2026-07-16

The 2026-07-14 performance review found all cost telemetry NULL on the heaviest
workloads — the A1 writers existed but nothing ever invoked them, and no cache
health signal existed at all. The wave-1 instrument adds:

* **`scripts/telemetry/call_log.py`** — one JSONL line per model call
  (`input_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`,
  `output_tokens`, `cache_read_ratio`, `message_id`, `source_kind`) appended to
  **`metrics/model_call_log.jsonl`** (gitignored). Incremental via a
  `{watermark_ts, boundary ids}` blob in `telemetry_run_state`
  (`call_log_watermark`), with a `FLUSH_LAG_SECONDS` trailing window for
  late-flushed transcript lines.
* **Cache-read ratio** — `src/telemetry/cost.py` `compute_cache_read_ratio`
  plus per-tier (`TierCost`) and overall (`CostReport`) properties. Pure
  read-time computation; honest-`None` on zero denominator or unknown
  components.
* **Auto-run seam** — `scripts/stop_hook.py` `_run_telemetry_kick`: throttled
  (10 min floor, eager atomic stamp), timeout-bounded subprocess with captured
  output (the hook's stdout stays reserved for its single JSON decision
  object), `STOP_HOOK_TELEMETRY_DISABLE=1` kill-switch under the existing
  `STOP_HOOK_DISABLE=1` master switch.

**Why a JSONL, not a table** (divergence from this ADR's "new granularity =
new table" precedent, recorded per the 2026-07-16 spec-review arch finding):
(a) no DDL means no exposure of the `_migrations` allowlist surface
(regression ledger 2026-06-05/06); (b) the per-call corpus (~265M tokens
historically) would bloat both `evaluation.db` and the repo if committed —
the JSONL is gitignored, append-only, greppable; (c) its purpose is
durability past `~/.claude` transcript pruning, not relational queries — the
committed Layer-2 artifacts remain the DB aggregates. Compute-don't-store is
preserved: the logged ratio is a recomputable token-count derivation; dollars
are never logged.

**Activation (developer-applied manual edit — protected file, ADR-0018
precedent):** add to `.claude/settings.json` `"hooks"`:

```json
"Stop": [
  {
    "hooks": [
      {
        "type": "command",
        "command": "python scripts/stop_hook.py",
        "timeout": 680
      }
    ]
  }
]
```

(680 = the parked ntfy-wait draft's 660 + the 15 s telemetry budget + slack.)
Until wired, `python scripts/telemetry/call_log.py` runs the same pass
manually.

## Linked Discussions
- Spec review: discussions/2026-06-06/DISC-20260606-041937-telemetry-oversight-spec-review/
- Steward gate: (framework-evolution review, APPROVE 0.86, 5 conditions)
- Build (A1): discussions/2026-06-06/DISC-20260606-063822-build-telemetry-cost-a1/
- Review (A2): discussions/2026-06-06/DISC-20260606-085949-review-telemetry-failures-a2/ (REV-20260606-085949, approve-with-changes, 2 blocking fixed)
- Spec review (A3): discussions/2026-06-06/DISC-20260606-211551-telemetry-value-crosscheck-a3-spec-review/ (arch/security/qa, approve-with-changes, 0 blocking)
- Steward gate (A3): discussions/2026-06-06/DISC-20260606-220705-telemetry-a3-steward-gate/ (APPROVE 0.88)
- Build (A3): discussions/2026-06-06/DISC-20260606-221119-build-telemetry-value-crosscheck-a3/
- Spec (Layer B): docs/sprints/SPEC-20260607-064958-telemetry-layer-b-dashboard.md (approve, 5 blocking findings folded)
- Steward form-factor gate (Layer B): DISC-20260607-063709 (APPROVE 0.88, static HTML)
- Spec review (Layer B): DISC-20260607-065118 (arch/security/qa/ux, all approve-with-changes, 5 blocking folded)
- Build (Layer B static): discussions/2026-06-07/DISC-20260607-072951-build-telemetry-layer-b-dashboard/
- Spec (Layer B live daemon): docs/sprints/SPEC-20260607-183136-telemetry-layer-b-live-dashboard-daemon.md (reviewed + approved)
- Steward form-factor gate (Layer B live): discussions/2026-06-07/DISC-20260607-163709-telemetry-layer-b-form-factor-gate/ (APPROVE 0.86, 9 conditions = AC1-AC9)
- Spec review (Layer B live): discussions/2026-06-07/DISC-20260607-183247-telemetry-layer-b-live-dashboard-daemon-spec-review/ (security/arch/qa, 7 blocking folded into spec AC1-AC9)
- Build Phase 1 (Layer B live core): discussions/2026-06-07/DISC-20260607-193135-build-telemetry-layer-b-dashboard-server-phase1/
