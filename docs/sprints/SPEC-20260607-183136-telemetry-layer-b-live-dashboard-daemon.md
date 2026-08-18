---
spec_id: SPEC-20260607-183136
title: "Layer B Telemetry Dashboard — live localhost-only daemon (redesign)"
type: spec
status: complete
risk_level: high
reviewed_by: [security-specialist, architecture-consultant, qa-specialist]
discussion_id: DISC-20260607-183247-telemetry-layer-b-live-dashboard-daemon-spec-review
intake_ids: []
completed_at: 2026-06-10
completed_commit: c5a9cf2
status_note: "stamped complete post-hoc 2026-07-16 during the wave-2 spec-budget check (shipping evidence: git log; part of triage #11 bookkeeping debt)"
---

## Goal
Replace the shipped **static HTML** Layer B dashboard with a **live, localhost-only,
user-launched persistent daemon** that renders the framework's telemetry (A1 cost / A2
failure signals / A3 value) in real time during a session, and the durable retrospective
views from history when no session is live. Reach functional parity with Ross Barbieri's
reference live dashboard (live agent lanes, context-runway gauge, per-turn cost, failure
intelligence, trends) **without** adopting its auto-inject-into-prompts mechanism or its
Node/npm toolchain.

## Context
The static dashboard (ADR-0020 Layer B note, lines 195–241; gate DISC-20260607-063709,
APPROVE 0.88) is a one-shot read-time artifact. The capability-gap analysis
(`docs/reviews/ANALYSIS-20260607-rh-oversight-deepdive.md`, §3) shows a **structural** gap:
a static snapshot categorically cannot show live agent lanes, context runway, per-turn
cost, or in-flight orphan detection. No amount of static-artifact polish closes a gap that
is intrinsic to the form factor.

**This redesign is the LOCKED north star** (`project_telemetry_dashboard_northstar`): the
whole point of the Telemetry & Oversight component is a powerful dashboard for understanding
AI use; A1/A2/A3 are its data foundation.

**Steward form-factor gate cleared this session: APPROVE 0.86** (overturns the
"no-standing-process" constraint of DISC-20260607-063709). The Steward attached 9 binding
conditions (folded into Constraints + Acceptance Criteria below) and confirmed no
Prime-Objective / extraction clause is violated: the daemon runs on the developer's own
machine, serves only them, persists no dollar figures, and emits nothing outbound.

**Prior art / reuse (do not rebuild):**
- A1/A2/A3 pipeline read-side functions: `build_cost_report` (cost), `rank_failures`
  (failures), `analyze_value` returned objects (value). **NEVER** call `analyze_cost()`,
  `analyze_failures()`, or `init_db()` from the dashboard — they MUTATE the DB.
- The replaced static renderer `src/telemetry/dashboard.py` (pure render + `html.escape`
  helpers, ASCII console summary) — its escaping helpers and `DashboardData` assembly seam
  are reusable for the `--render-static` export mode and server-side rendering.
- `reference_subagent_transcript_layout` memory: dispatch tool is `Agent` (not `Task`);
  subagent transcripts live in `<sessionId>/subagents/agent-<agentId>.jsonl`. Load-bearing
  for any live transcript parsing (agent-lanes, per-turn cost).

**Known-broken approaches to avoid (regression ledger + analysis §5):**
- Reading Anthropic's `~/.claude.json` / `stats-cache.json` for cost — reads ≈$0 on a
  subscription (`project_billing_topology`) and `stats-cache.json` is documented-broken
  since Claude Code v2.1.118. We compute cost from token-counts × pricing instead.
- Auto-injecting telemetry into agent prompts (Ross's pattern) — violates the binding
  "no telemetry into any live agent prompt" Steward condition (KV-cache safety).
- Copying Node/JS verbatim or reusing Ross's test fixtures (contamination guard, §5).

## Requirements

### Functional
- **R1 — Daemon:** a FastAPI app launched explicitly by the developer (e.g.
  `python scripts/telemetry/dashboard_server.py` or a `/dashboard` action). Serves an
  htmx + vanilla-JS UI. Persistent until the developer stops it.
- **R2 — Live view (session active):** agent lanes (active/completed/orphaned, model, cost,
  context %, tool count, failure count), a live cost/failure stream, and a context-window
  runway gauge (fill %, amber/red thresholds, est. turns remaining). Updates without a full
  page reload via **htmx polling** (NOT SSE) against `127.0.0.1` in Phase 1 — keeps the
  test surface synchronous/`TestClient`-compatible (qa F5). SSE deferred to a later phase;
  if adopted it must cap concurrent connections (default 5 → HTTP 503) with
  server-specified intervals, not client query-param overridable (security F5).
- **R3 — Retrospective view (no session active):** the four R-B2 minimum views rendered
  from `evaluation.db` history — (a) per-model/agent cost + coverage %; (b) cost-weighted
  failure list; (c) per-command efficiency; (d) recurring-failure trend. The static
  dashboard's *value* survives the form-factor change.
- **R4 — `--render-static` export mode (Fork B):** a thin one-shot CLI mode on the same
  read-side functions that writes a static HTML artifact (today's behavior) for
  headless/derived instances with no standing-process option. No server required.
- **R5 — Data source:** A1/A2/A3 pipeline only. Cost = token-counts × pricing computed at
  render time. Live data parsed from session/subagent transcripts (read-only).
- **R6 — Later-phase surfaces (parity backlog):** per-turn cost chart, weekly trends +
  prior-window deltas, config-drift visibility, hook-health self-monitoring, model-cost
  donut, CLI inline summary, Picture-in-Picture. Each is its own internal phase.

### Non-functional / security (Steward conditions)
- **R7 — Explicit launch only:** NOT wired to SessionStart, any hook, `/distribute`, or the
  ADR-0018 auto-launch path.
- **R8 — Hard localhost bind:** binds `127.0.0.1` as a hardcoded literal; never `0.0.0.0`,
  never host-configurable. **NO `--host`/`-H` CLI flag and no `HOST` env read** (uvicorn
  honors both — a flag would let a derived project bind `0.0.0.0` with no auth) (security F1).
  A **runtime guard** asserts `host == "127.0.0.1"` and fails fast BEFORE `uvicorn.run()`,
  not only in a test.
- **R8a — Loopback request-origin guard:** configure `CORSMiddleware` same-origin only (no
  wildcard); validate the `Host` header equals `127.0.0.1:<port>` (else HTTP 400) to blunt
  DNS-rebinding / localhost-CSRF from a malicious page the developer visits (security F4).
- **R9 — Display-parity only:** reads + renders only. No write to / post to / inject into
  any agent prompt, hook payload, or `settings.json`. No enforcement subsystem.
- **R10 — Read-only DB + compute-don't-store:** `evaluation.db` opened `file:...?mode=ro`;
  in-memory live layer persists nothing on teardown; no dollar/ratio column ever created.
- **R11 — Output safety:** `html.escape` every dynamic field in HTML attribute/text
  contexts server-side. **For data baked as a JSON literal inside `<script>` blocks,
  `html.escape` is WRONG** — serialize with `json.dumps()` and apply a `</script>`
  injection guard (replace `</` with `<\/`, or `<`); a transcript value like
  `</script><script>…` must not be able to close the block (security F2). Generic errors
  only — raw DB/internal exceptions never reach the browser.
- **R11a — Vendor frontend assets:** vendor Chart.js + htmx (pinned exact versions) into
  `src/telemetry/static/` and serve them from the FastAPI static mount, rather than a CDN
  fetch — eliminates the only outbound load-time dependency (strengthens R13) and removes
  the SRI/CDN-compromise surface (security F3). (If CDN is ever used instead, `integrity=`
  SRI hashes are mandatory.)
- **R12 — Zero idle overhead + clean teardown:** when not launched, zero processes / watchers
  / CPU. A documented stop path (Ctrl-C / kill) releases the port and frees memory. Startup
  banner states the bind address + stop instruction.
- **R13 — No outbound surface:** no remote POST, no outbound HTTP client in the server.
- **R14 — `live.py` purity seam (arch F1):** `src/telemetry/live.py` is a pure
  `events → LiveState` fold. It consumes an **already-parsed** `LiveEvent` sequence produced
  by the transport layer; it imports NO transcript-IO and NO `scripts.*` module (the live
  analogue of the static `DashboardData` seam — keeps statefulness in the transport process
  only, keeps the model unit-testable, and makes R10's "persists nothing" enforceable).
- **R15 — Single render path (arch F2):** the htmx live fragments AND the `--render-static`
  document compose from the SAME `src/telemetry/dashboard.py` panel/section render helpers,
  differing only in shell (full doc vs fragment + polling wrapper). No second renderer.
- **R16 — Fold A-ARCH1 (arch F3, Phase 1 prerequisite):** promote the cross-module-consumed
  transcript helpers (`_collect_messages`, `discover_session_dirs`, `_parse_since`,
  `_is_inside_projects_root`) in `scripts/ingest_token_usage.py` to public names in ONE
  change (the daemon is the 4th consumer — Rule of Three crossed), updating the 3 existing
  call sites. Flat public-function promotion only — NOT a new module/class. **Verify at
  build** that the daemon reuses this parsing (vs a distinct live-tail); skip the promotion
  only if it genuinely needs different parsing.

## Constraints
- Stack: Python 3.11+, FastAPI (already a dep), pytest, ruff; coverage ≥80%.
- Frontend: htmx + vanilla JS + Chart.js, **vendored (pinned exact versions) into
  `src/telemetry/static/` and served locally** (per R11a) — **NO Node/npm/build step**.
- Pure/transport split preserved (per existing telemetry modules): pure render/assembly in
  `src/telemetry/`, I/O + server wiring in `scripts/telemetry/`.
- Contamination guard (analysis §5): original Python only; no verbatim JS from Ross's repo;
  no reuse of Ross's fixture JSON/JSONL. Error-class *vocabulary* (not_found, permission,
  orphan, config, validation, timeout, network) may be reused as domain terms.
- ADRs never deleted (Principle #5): amend ADR-0020 Layer B note; cite DISC-20260607-063709
  as superseded form factor; re-affirm Ross (MIT) attribution.

## Acceptance Criteria

### Steward conditions (BLOCKING — all must hold)
- [ ] **AC1** No SessionStart/hook/auto-launch/`/distribute` reference starts the server
      (grep/test asserts; condition 1/R7).
- [ ] **AC2** Server binds `127.0.0.1` from a hardcoded literal; no `--host`/`-H` flag, no
      `HOST` env read; a runtime guard fails fast before `uvicorn.run()` on any non-loopback
      host. **Tested via `uvicorn.Config` inspection** (`config.host == "127.0.0.1"`) + a
      source-grep test that `"0.0.0.0"` is absent + a `TestClient` positive path — **NOT a
      live non-loopback bind** (OS-dependent/flaky; qa F1). Plus a `Host: evil.example.com`
      request returns 400 (R8a). **BLOCKING security invariant** (condition 2/R8).
- [ ] **AC3** Two-layer `@pytest.mark.regression` no-inject guard (condition 3/R9; qa F2):
      **(a) static** — importing the server module does not pull `hooks`/`settings`/any
      prompt-assembly module into `sys.modules` (module-name allowlist); **(b) behavioral** —
      every endpoint called via `TestClient` against a `tmp_path` copy of `.claude/hooks/` +
      `settings.json` leaves them byte-unchanged (diff before/after). Layer (b) is what bites
      new vectors.
- [ ] **AC4** With no live session, the daemon renders all four R-B2 retrospective views
      from `evaluation.db` (condition 4/R3).
- [ ] **AC5** `evaluation.db` opened read-only (`mode=ro`); a `_schema_snapshot` +
      `_table_row_counts` test (reusing existing helpers) asserts the DB is byte-unchanged
      and no dollar/ratio column added; a teardown test exercises the FastAPI `lifespan`
      exit and asserts no new files in `tmp_path` + the live state is reset/empty
      (condition 5/R10; qa F6).
- [ ] **AC6** Every dynamic/transcript-shaped field `html.escape`d server-side in HTML
      contexts (tests on failure signature/detail/tier, divergence reason, labels); **data
      in `<script>` blocks serialized via `json.dumps()` with a `</script>` guard — a test
      injects `</script><script>` into chart data and asserts no literal `</script>` in
      output** (security F2); frontend assets vendored + pinned (R11a); and a test patches
      `assemble_dashboard_data` to raise `sqlite3.OperationalError` and asserts HTTP 500 with
      a body that contains neither the DB path nor `"OperationalError"` (qa F7)
      (condition 6/R11).
- [ ] **AC7** Documented teardown frees the port + memory; startup banner prints bind
      address + stop instruction; zero processes when not launched (condition 7/R12).
- [ ] **AC8** No outbound HTTP client in the server; review check confirms no remote POST
      (condition 8/R13).
- [ ] **AC9** ADR-0020 Layer B amendment committed recording the reversal + Ross attribution
      (condition 9).

### Functional
- [ ] **AC10** Daemon launches via explicit command, serves the htmx UI on `127.0.0.1:<port>`.
- [ ] **AC11** Live view shows agent lanes + cost/failure stream + context-runway gauge,
      verified against an **authored** fixture-transcript inventory (qa F3; extend the A2
      `_assistant_line`/`_subagent_line` factory — do NOT reuse Ross fixtures): minimum
      (a) active session with an orphaned subagent; (b) context at ~75% (amber); (c) context
      at ~91% (red); (d) a truncated/partial last JSONL line skipped gracefully (qa F9).
- [ ] **AC12** `--render-static` and the live retrospective view compose from the SAME
      `src/telemetry/dashboard.py` panel helpers (R15): a test asserts both paths produce
      **byte-identical panel bodies** for the same `DashboardData`, and that both derive
      from a **field-for-field-equal `DashboardData`** on the same fixture DB (arch F2 +
      qa F8 reconciled — same panel helpers ⇒ identical bodies; only the doc shell differs).
- [ ] **AC13** Cost is computed from token-counts × pricing (never read from `~/.claude.json`).
- [ ] **AC14** `src/telemetry/live.py` imports no `scripts.*` module and no transcript-IO; a
      test asserts the absence (R14 purity seam, arch F1).
- [ ] **AC15** A-ARCH1 promotion landed: the four transcript helpers are public in
      `scripts/ingest_token_usage.py`, the 3 existing call sites updated, a contract test
      locks the public surface (R16, arch F3) — unless build confirms the daemon needs
      distinct parsing (then log the skip).
- [ ] **AC16** Port-in-use yields a clear human-readable message (not a raw `[Errno 98]`
      trace) and does not hang; `@pytest.mark.regression` (qa F4).
- [ ] **AC17** Quality gate 7/7: ruff format + lint clean, pytest green, coverage ≥80%, ADR
      completeness, review existence, regression ledger, BUILD_STATUS freshness.

## Risk Assessment
- **Network exposure (HIGH→mitigated):** a standing HTTP server is a new attack surface.
  Mitigation: hardcoded `127.0.0.1` literal (AC2), no auth needed for loopback-only, no
  outbound client (AC8), generic errors (AC6). Treated as BLOCKING in review.
- **Injection via transcript-shaped data (MED→mitigated):** transcripts are
  generative/uncontrolled. Mitigation: `html.escape` at every field (AC6), data baked as a
  JSON literal in `<script>` blocks for charts (not interpolated into HTML attributes).
- **DB mutation (MED→mitigated):** accidental call to a mutating analyzer. Mitigation:
  read-only connection (AC5) + read-side-functions-only constraint + schema test.
- **No-inject regression (HIGH→mitigated):** future code accidentally feeding a metric into a
  prompt. Mitigation: standing `@regression` guard (AC3) — the single most load-bearing line.
- **Scope creep across phases (MED):** parity backlog (R6) is large. Mitigation: internal
  phasing with commit + review per phase; Phase 1 is independently shippable.

## Internal Phasing (one spec, phased build, commit + review per phase)
- **Phase 1 — Live core (independently shippable):** daemon skeleton + `127.0.0.1` bind +
  htmx shell; agent-lanes; live cost/failure stream; context-runway gauge; retrospective
  history views from DB (R3); the no-inject + bind + read-only invariants (AC1–AC10).
- **Phase 2 — Time series:** per-turn cost chart; weekly trends + prior-window deltas
  (Chart.js, data baked as JSON literal).
- **Phase 3 — Failure intelligence:** error-class grouping + remediation hints; config-drift
  rows; retry-chain nesting.
- **Phase 4 — Self-monitoring + extras:** hook-health chip; model-cost donut; CLI inline
  summary; Picture-in-Picture.
- **Phase 5 — `--render-static` export mode (R4/AC12)** for headless/derived instances.

(Phasing is refinable during `/build_module`; Phase 1 carries all 9 Steward conditions.)

## Affected Components
- NEW `scripts/telemetry/dashboard_server.py` — FastAPI app, `127.0.0.1` bind, routes, htmx
  endpoints, transport (transcript parsing, read-only DB access). Launch entry point.
- `src/telemetry/dashboard.py` (existing pure renderer) — extend with server-side render
  helpers + live-state assembly; reuse `html.escape` helpers; feeds `--render-static`.
- NEW `src/telemetry/live.py` (pure) — in-memory live-state model (agent lanes, runway,
  per-turn cost) folded from a pre-parsed `LiveEvent` sequence; imports no `scripts.*`,
  persists nothing (R14).
- NEW `src/telemetry/static/` — vendored, pinned Chart.js + htmx served from the FastAPI
  static mount (R11a).
- Disposition (arch F5): the existing one-shot `scripts/telemetry/dashboard.py` is retired
  INTO the new server's `--render-static` mode (not kept as a 2nd static entry point).
- `tests/test_telemetry.py` (+ possibly NEW `tests/test_dashboard_server.py`) — bind test,
  no-inject regression guard, escaping tests, read-only/schema tests, render-static parity.
- `docs/adr/ADR-0020-telemetry-oversight-component.md` — Layer B form-factor amendment.
- `requirements.txt` / `pyproject.toml` — confirm FastAPI + an ASGI server (uvicorn) pinned.

## Dependencies
- Depends on: A1/A2/A3 pipeline (DONE); `evaluation.db` schema (DONE); FastAPI + uvicorn.
- Depended on by: Layer C ntfy oversight digest (separate, aggregates-only); future
  enforcement subsystem (deferred — display-parity only here).
