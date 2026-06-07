---
spec_id: SPEC-20260607-064958
title: "Telemetry Layer B — local static HTML dashboard (render the honest Layer-A outputs)"
type: spec
status: approved
risk_level: medium
reviewed_by: [architecture-consultant, security-specialist, qa-specialist, ux-evaluator]
discussion_id: DISC-20260607-065118-telemetry-layer-b-dashboard-spec-review
intake_ids: []
completed_at:
completed_commit:
---

## Goal

Deliver the **north-star Layer B dashboard**: a single, self-contained HTML infographic,
generated locally at read-time from `metrics/evaluation.db` + config, that makes the
already-captured A1/A2/A3 telemetry **visible** so the developer can understand their AI
use at a glance. The dashboard **renders the existing honest Layer-A outputs** — it
performs no new measurement, forks no computation, and persists nothing.

Form factor is already **Steward-APPROVED** (DISC-20260607-063709, 0.88): static HTML
generated locally, mirroring the accepted `/status` precedent (`scripts/git_visualize.py`).
This spec is the form-factor-respecting `/plan` for that decision — it must not re-open the
server-vs-script question, and must demonstrate each of the 5 binding honesty conditions.

## Context

- **Why now**: A1 (per-tier cost + coverage), A2 (failure/waste signals), and A3
  (value-vs-subscription + estimate cross-check) are the data foundation and are **COMPLETE
  + committed** (`ed93448`, `e01e196`, `be79efa`, `a639903`). The whole point of the
  Telemetry & Oversight component is this dashboard (see `project_telemetry_dashboard_northstar`);
  the data was always in service of the visual surface.
- **Developer setup**: Claude Code subscription + individual account → local-only data, no
  billing API. Every figure derives from local transcripts + `evaluation.db` + local config.
- **Steward gate (DISC-20260607-063709)**: APPROVE 0.88. The 16/25-DEFER weight bar attached
  to the heavier FastAPI/web-app **server** option; a read-time render script with no server
  is categorically lighter on every axis (Principle #8). The disciplines (read-only, typed
  honest-absence) are already implemented in Layer A → correct build = "render the existing
  honest outputs."

### Prior art (informs this spec)
- **`/status` precedent** — `scripts/git_visualize.py` gathers state into dataclasses, builds
  one `<!DOCTYPE html>` string, writes it to `Path(tempfile.gettempdir()) / "git_repo_map.html"`,
  and `webbrowser.open()`s it (`--no-open` to suppress). **Reuse this exact shape.** The
  temp-dir write is also the privacy mechanism — the artifact never enters the repo tree.
- **Layer-A assembly functions to reuse (do NOT recompute):**
  - A1 cost: `scripts.telemetry.analyze_cost.load_cost_rows(conn)` → `src.telemetry.cost.build_cost_report(rows, pricing)` → `CostReport` (per-tier tokens, `cost_usd`, `coverage_pct`, `is_fully_covered`).
  - A2 failures: `scripts.telemetry.analyze_failures.load_failure_signals(conn)` → `src.telemetry.failures.rank_failures(...)` → ranked `FailureSignal`s (type, signature, occurrence, tier, wasted tokens, detail).
  - A3 value: `scripts.telemetry.analyze_value.analyze_value(...)` returns `LeverageResult` + two `DivergenceResult`s (attribution coverage + OTel pricing) — already carry typed honest-absence (`configured`, `available`, `reason`, `source_label`, `flaw_class`).
- **Known-broken to avoid (regression-ledger):** display/print strings emitted to the
  Windows terminal must be **ASCII-only** — a non-ASCII char (em-dash etc.) raises
  `UnicodeEncodeError` under cp1252 (3rd occurrence of this class: statusLine, ntfy title,
  quality_gate summary). The HTML file is UTF-8 with a declared `<meta charset>`; the
  **console summary** the generator prints must be pure ASCII.
- **Compute-don't-store lineage (ADR-0013 / ADR-0020):** the DB stores cost *inputs* (token
  breakdowns), never dollar figures; dollars are derived at read. The dashboard continues
  this — it reads the same stored inputs and derives at render.

## Requirements

### Functional
- **R1 — One self-contained artifact.** Produce a single HTML file (inline CSS, no external
  network assets, no CDN) so it renders offline and leaks nothing on open.
- **R2 — Render all three Layer-A panels (developer-approved scope = Full A1+A2+A3, static):**
  - **Cost & Coverage (A1):** per-tier token totals + USD, total known cost, coverage % of
    billable tokens, and an explicit treatment of the unknown-tier remainder (never zero-rated).
  - **Failure & Waste (A2):** ranked failure signals (orphaned subagents, retry loops) with
    type, occurrence, tier, wasted tokens, and short detail; a true "no failures detected"
    state distinct from "analyzer not yet run."
  - **Value vs Subscription (A3):** list-price-equivalent multiple (lead with the per-month
    figure), plus the two cross-checks (attribution coverage; OTel pricing) with their honest
    states preserved.
- **R2a — Plain-language framing for the manager-gatekeeper (ux BLOCKING).** Decontextualised
  dollar/multiple figures mislead a non-expert reader. Required, not left to the build:
  - The A1 panel carries a one-line legend (verbatim or equivalent): *"These figures show what
    the same tokens would cost at API pay-per-use prices — not what you paid on your
    subscription."*
  - The A3 multiple's **primary label is "List-price-equivalent multiple"** (NOT "leverage" or
    "value"), matching the A3 CLI (`_print_leverage`), with a one-line legend explaining what the
    multiple compares.
  - Every panel is understandable by a reader who does not know "coverage %" or "list-price-
    equivalent" — jargon terms carry an inline plain-language gloss.
- **R3 — Honest-absence as first-class visual states.** `n/a` / `not configured` /
  `not yet active` / `unavailable` must each render as a **visually distinct** tile/state —
  never a fabricated `0` bar, never an empty-but-authoritative chart. Carry the existing typed
  signals (`LeverageResult.configured`, `DivergenceResult.available`/`reason`/`source_label`,
  `CostReport.is_fully_covered`) directly to the UI. The OTel cross-check renders as an
  **"enable OTel" affordance**, not a dead "unavailable" row (matches the A3 console behavior).
- **R3a — Absence-state visual + copy spec (ux BLOCKING; the highest-risk axis).** "Visually
  distinct" is made concrete so the build cannot satisfy the letter with a grey `n/a` box:
  - Absence tiles use a **distinct container treatment** (e.g. dashed border / muted background)
    NOT used by any data-bearing tile. The distinction is conveyed by **shape/border/icon, not
    color alone** (WCAG 1.4.1).
  - Each absence tile carries a **plain-language sentence**: "[What is absent]. [Why]. [Action
    if any]." (mirror the A3 CLI wording already in `_print_divergence`).
  - **True-zero** (analyzer ran and found nothing) uses the **normal data-bearing tile** with
    explicit copy (e.g. "No failure signals detected"), **not** the absence style.
  - **Analyzer-not-yet-run** is a **distinct absence tile** (e.g. "No data yet. Run
    `scripts/telemetry/analyze_failures.py` to populate this panel.").
  - The OTel affordance renders the docs URL as a **live `<a>` hyperlink** (new tab), not plain
    text (ux ADVISORY 1).
  - **Reviewability gate:** because "unmistakable on sight" is not auto-testable, the build close
    attaches a **screenshot showing each absence state** from a fixture run, so `/review` can
    probe condition #4 visually.
- **R4 — Mirror `/status` UX.** Generate + open in the browser, then print a **5-6 line ASCII
  text summary** to the console; let the visual carry the detail. `--no-open` suppresses the
  browser open (for CI / headless / tests). The summary lines are: (1) output file path; (2)
  total known cost + coverage %; (3) failure-signal count or "no failures"; (4) list-price-
  equivalent multiple or "subscription not configured"; (5) OTel cross-check status in one
  phrase; (6) optional honest-absence advisory. No raw internal field names; no figure that
  needs explanation to read (ux ADVISORY 3). The A2 panel itself leads with a one-line status
  ("N signals detected" / "No failure signals detected") before its detail table (ux ADVISORY 2).
- **R5 — Transport-fidelity assertion.** The rendered figures must equal the Layer-A outputs for
  the same DB/config — no drift between the page and the CLIs.
- **R5a — Testable assembly seam (qa BLOCKING).** The dashboard exposes a **pure**
  `assemble_dashboard_data(db_path, *, pricing, subscription_path, otel_path) -> DashboardData`
  that returns the assembled Layer-A dataclasses with **no HTML and no DB writes**. The render
  layer formats `DashboardData` into HTML; the fidelity test compares `assemble_dashboard_data`
  field-by-field against `build_cost_report` / `rank_failures` / `analyze_value` on the same
  fixture (loaded with an identical `load_pricing()` table). Named fields that must match:
  `CostReport.total_cost_usd`, `.coverage_pct`, `.is_fully_covered`, every `by_tier`
  `TierCost.cost_usd`; `LeverageResult.configured`, `.leverage_cumulative`, `.leverage_per_month`;
  both `DivergenceResult.available`, `.divergence_pct`, `.direction`. The seam also gives the
  escaping / ASCII / absence-state tests a clean input without brittle HTML parsing.
- **R6 — Output to the OS temp dir (developer decision #6 = temp like `/status`).** Write to
  `Path(tempfile.gettempdir()) / "telemetry_dashboard.html"`. The artifact never enters the
  repo tree, so personal cost/fee figures cannot reach a remote. (Belt-and-suspenders: add a
  defensive `.gitignore` entry for the conventional filename in case a future flag redirects
  it into the tree.)

### Non-functional / architecture
- **R7 — Thin render layer over READ-SIDE functions only (arch BLOCKING).** `dashboard.py` is
  transport/presentation only and consumes the **read-side** assembly functions exclusively:
  `load_cost_rows` → `build_cost_report` (A1); `load_failure_signals` → `rank_failures` (A2);
  `analyze_value(...)`'s returned objects (A3). It must **never** call `analyze_cost()` or
  `analyze_failures()` — those CLI orchestrators **mutate the DB**, print, and return only an
  int summary (calling them would violate R8/C1 and fork a second computation path). The A2
  panel mirrors the CLI's post-run report = the **full stored corpus** via `load_failure_signals`
  (not only freshly-detected signals). **No math moves into the script** — all aggregation stays
  in `src/telemetry/`; any pure formatting/escaping helper goes in a `src/telemetry/` module.
- **R8 — Read-only DB access, tolerant of an unpopulated DB (arch ADVISORY).** Open
  `evaluation.db` read-only (`file:...?mode=ro` URI); the dashboard never writes, migrates, or
  creates tables/columns/caches/sidecars, and **does not call `init_db()`** (it writes). If a
  telemetry table is absent (fresh clone / analyzers never run), the read is caught
  (`try/except sqlite3.OperationalError`) and mapped to the **analyzer-not-yet-run** honest-
  absence state — never a crash, never a fabricated zero.

## Constraints

- **C1 (Steward BLOCKING #1 — compute-don't-store, inviolable).** Derive every dollar / ratio
  / coverage figure at render from `evaluation.db` + config. Persist **nothing** new — no
  cache, table, column, or sidecar file; reuse `analyze_cost` / `analyze_value` /
  `analyze_failures` assembly paths with **no parallel computation**. Any persistence-for-speed
  returns to the Steward gate.
- **C2 (Steward BLOCKING #2 — aggregates-only + no slug).** Render only aggregates already in
  the Layer-A outputs. **No transcript free-text or prompt bodies.** The **ntfy topic slug is
  NEVER printed** — not in the HTML, not in any console line, **not in any error/diagnostic
  path** of the generator.
- **C3 (Steward BLOCKING #3 — no telemetry into any agent prompt).** The dashboard is
  render-only; its output is never passed as a `Task()`/`Agent()` input, never prefills a KV
  cache, never feeds a live agent prompt.
- **C4 (Steward BLOCKING #4 — honest-absence is first-class; highest-risk axis).** See R3 + R3a
  (concrete visual/copy spec). The `/review` MUST specifically probe this: a visual surface can
  make a fabricated `0` look authoritative. Absence states must be unmistakable from a true zero;
  the build attaches a per-state screenshot so the probe is possible.
- **C5 (Steward BLOCKING #5 — no secrets in the artifact).** No keys/credentials/topic/env-
  leaking paths baked into the HTML. Cost + fee figures may render (they are the developer's
  own data) but nothing that is a secret.
- **C6 — HTML-injection / escaping safety (security BLOCKING).** Render dynamic values
  **server-side** and `html.escape()` them in **Python** before interpolation; render in the JS
  layer (if any) as `textContent`, **never `innerHTML`**. This is a deliberate **divergence from
  the `/status` precedent** (`git_visualize.py` interpolates raw into `innerHTML` — safe there
  because git plumbing output is controlled; unsafe here because Layer-A strings are transcript-
  shaped). Escape **every** string field: `FailureSignal.signature` / `.detail` / `.failure_type`
  / `.tier`, `DivergenceResult.reason` / `.source_label`, `IndependentEstimate.source_label`,
  `LeverageResult.reason` / `.note`, the `subscription.yaml` `plan_label` / `effective_date`, and
  tier-name keys. Numeric values need no escaping. The injection test must target the transcript
  field feeding `FailureSignal.signature` (the tool-name component), not only `.detail`.
- **C7 — ASCII-only console output.** Every string the generator `print()`s is ASCII (Windows
  cp1252). The HTML file is UTF-8 with `<meta charset="utf-8">`.
- **C8 — Hardened file reads.** Any template/file read follows the `_otel_estimate` discipline
  (fixed path, resolves within-root, size-capped). v1 inlines CSS/markup in Python (no external
  template file) to keep this surface minimal; if a template file is introduced it must be
  fixed-path + within-root + size-capped.
- **C9 — No standing process (developer decision #7 / Steward #7).** No live-refresh, no
  auto-open-on-schedule, no daemon, no watch. One-shot generate + open. Re-introducing any
  standing process re-opens server-vs-script and returns to the gate.

## Acceptance Criteria

- [ ] `python scripts/telemetry/dashboard.py` generates one self-contained HTML file in the OS
      temp dir and opens it; `--no-open` generates without opening. (R1, R4, R6)
- [ ] The HTML renders three panels — Cost & Coverage (A1), Failure & Waste (A2), Value vs
      Subscription (A3) — populated from the live `evaluation.db`. (R2)
- [ ] **Assembly seam:** a pure `assemble_dashboard_data(...) -> DashboardData` returns the
      Layer-A dataclasses with no HTML and no DB writes; the render layer consumes only its
      output. (R5a, R7)
- [ ] **Transport-fidelity (field-level):** a test asserts `assemble_dashboard_data` equals
      `build_cost_report` / `rank_failures` / `analyze_value` on the same fixture (identical
      `load_pricing()`), checking `CostReport.total_cost_usd`/`.coverage_pct`/`.is_fully_covered`
      + each `by_tier` `cost_usd`; `LeverageResult.configured`/`.leverage_cumulative`/
      `.leverage_per_month`; both `DivergenceResult.available`/`.divergence_pct`/`.direction`. (R5, R5a)
- [ ] **Read-side-only:** a test asserts the dashboard path never invokes `analyze_cost()` /
      `analyze_failures()` / `init_db()` (no DB mutation). (R7, R8, C1)
- [ ] **Honest-absence — one test per state**, each asserting a distinct non-numeric marker
      (named CSS class / data-attribute / literal copy token), never a `0` bar: (a) subscription
      fee not configured; (b) OTel not-yet-active → an "enable OTel" **live `<a>` link**; (c)
      attribution cross-check skipped under `--since`; (d) analyzer-not-yet-run (distinct from
      true-zero); (e) unknown-tier remainder rendered "uncosted", not `$0`. (R3, R3a, C4)
- [ ] **True-zero vs not-yet-run:** a test with an empty `telemetry_failures` table + watermark
      present renders "No failure signals detected" (data tile); empty table + no watermark
      renders the analyzer-not-yet-run absence tile. (R3a, qa ADVISORY 7)
- [ ] **First-run / empty DB:** a run against an empty DB renders every panel in its absence
      state, not a blank page or a crash. (R8, ux flow)
- [ ] **HTML-escaping (parametrized over all string fields):** injecting `<script>…</script>`
      into a fixture's `FailureSignal.signature` (via the transcript tool-name), `.detail`,
      `DivergenceResult.reason`, and `.source_label` yields escaped output, never live markup;
      values render via `textContent`/escaped Python, never raw `innerHTML`. (C6)
- [ ] **No-slug (behavioral):** inject a known fake `NTFY_TOPIC`, force an error path
      (unreadable `db_path`), capture stdout+stderr, assert the fake slug value is absent; the
      generator imports/calls no `notify.py`. (C2)
- [ ] **ASCII console summary (parametrized):** the summary round-trips through cp1252 + ascii
      across states (all-present / fee-not-configured / no-failures). (C7)
- [ ] **No persistence (strong):** the DB is opened `file:...?mode=ro`; a test asserts both
      schema (`sqlite_master`) and row counts are unchanged before/after a dashboard run. (C1, R8)
- [ ] **Plain-language framing:** the A1 panel carries the pay-per-use legend; the A3 multiple is
      labelled "List-price-equivalent multiple" with an explanatory legend. (R2a, ux BLOCKING 2)
- [ ] **Reviewability artifact:** the build attaches a screenshot of each honest-absence state
      from a fixture run for the `/review` to probe condition #4. (R3a, C4)
- [ ] Quality gate 7/7 (ruff, lint, pytest, coverage ≥80%, ADR completeness, review existence,
      regression ledger). ADR-0020 carries a Layer B implementation note.

## Risk Assessment

- **Highest risk — fabricated-zero (C4).** A chart makes a fake `0` authoritative. *Mitigation:*
  carry the existing typed absence signals straight to distinct UI states; dedicated tests +
  the `/review` probes this axis specifically.
- **HTML injection (C6).** Failure signatures/detail are transcript-shaped. *Mitigation:*
  `html.escape` at every interpolation; injection test.
- **Slug / secret leak (C2, C5).** A diagnostic/error path could print the slug or a secret.
  *Mitigation:* the generator reads only aggregate Layer-A outputs (which never contain the
  slug); explicit no-slug test incl. an error path; no env/credential interpolation.
- **Scope creep into a standing process (C9).** *Mitigation:* one-shot only; any refresh/daemon
  returns to the Steward gate.
- **Figure drift between page and CLI (R5).** *Mitigation:* transport-fidelity assertion test.
- **Privacy of the artifact (R6).** *Mitigation:* temp-dir output, never in the repo tree;
  defensive `.gitignore` for the conventional filename.

## Affected Components

- **NEW** `scripts/telemetry/dashboard.py` — thin render/transport layer: open the DB read-only,
  assemble via the **read-side** Layer-A functions, format `DashboardData` into one HTML string,
  write to temp, open browser, print the ASCII summary. No math, no DB writes.
- **NEW (pure)** `src/telemetry/dashboard.py` (or a `dashboard_data` module) — the
  `DashboardData` dataclass + the pure `assemble_dashboard_data(...)` seam + any HTML-escaping /
  formatting helpers (keeps math/format out of the script and inside the coverage-counted pure
  layer). The HTML template/markup may be a module-level string constant here.
- **EDIT** `tests/test_telemetry.py` — dashboard tests: assembly-seam fidelity (field-level),
  read-side-only/no-init_db, one-per honest-absence state, true-zero-vs-not-run, empty-DB
  first-run, parametrized escaping, behavioral no-slug, parametrized ASCII summary, strong
  no-persistence (schema + row counts, `?mode=ro`).
- **EDIT** `.gitignore` — defensive entry for the conventional dashboard filename.
- **EDIT** `docs/adr/ADR-0020-telemetry-oversight-component.md` — Layer B implementation note.
- **EDIT** `memory/bugs/regression-ledger.md` — entries for any guard added (escaping / no-slug /
  ASCII summary / read-side-only) as warranted by `/review`.
- **ARTIFACT (build close)** a screenshot set of the honest-absence states from a fixture run,
  for the `/review` condition-#4 probe (R3a reviewability gate).

## Dependencies

- **Depends on:** A1/A2/A3 (COMPLETE) — `src/telemetry/{cost,failures,value,pricing}.py`,
  `scripts/telemetry/{analyze_cost,analyze_failures,analyze_value}.py`, `metrics/evaluation.db`,
  `config/{model_pricing.yaml,subscription.yaml}`. The `/status` pattern in
  `scripts/git_visualize.py`. ADR-0013 (accepted), ADR-0020.
- **Depended on by:** Layer C (ntfy oversight digest → /meta-review) may later reuse the same
  aggregate assembly; the dashboard does not block it. No downstream code depends on this yet.
- **Out of scope (explicit):** any new measurement/analyzer; A2.1 stop-loop; the A1.1
  session-keyed watermark; deferred A-PERF2/A-ARCH1 refactors; live-refresh/server/daemon;
  Layer C itself.
