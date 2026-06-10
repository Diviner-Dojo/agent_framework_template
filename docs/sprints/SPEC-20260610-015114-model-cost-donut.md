---
spec_id: SPEC-20260610-015114
title: "Model-cost donut — corpus cost split by model tier (Phase 4 Unit 4.2)"
type: spec
status: complete
risk_level: medium
reviewed_by: [architecture-consultant, qa-specialist, security-specialist]
discussion_id: DISC-20260610-015227-model-cost-donut-spec-review
intake_ids: []
completed_at: 2026-06-10
completed_commit: 8538ac7
---

## Goal

Add a Chart.js doughnut panel to the live dashboard showing the stored corpus's
API-equivalent cost split by model tier (Opus / Sonnet / Haiku / any other
priced tier), so the manager-gatekeeper can see at a glance *where the money
goes* across models — the per-tier table in the retrospective cost panel made
visual. Third chart consumer; the unit also discharges the recorded
Rule-of-Three fold on `render_live_fragment`'s pre-rendered-HTML parameters.

## Context

- SPEC-20260607-183136 §Internal Phasing, Phase 4: "model-cost donut" (one
  bullet; concrete semantics defined here).
- Data source: `CostReport.by_tier` (`src/telemetry/cost.py`) —
  `TierCost.cost_usd` is `None` for an unpriced/unknown tier; callers must
  render that as *uncosted*, never `$0` (module contract + ADR-0020).
- Established chart pattern (per-turn chart `e70cfd3`, weekly chart
  `c559816`): pure renderer in `src/telemetry/dashboard.py` emitting
  `tile--loading` + `hidden` wrapper + canvas + `_json_in_script` JSON data
  block; init path in `src/telemetry/static/dashboard-chart.js` keyed on
  element ids, with a per-chart fallback-timer object and `revealChart()`
  on first draw; SHA-384 re-pin in lockstep across
  `src/telemetry/static/README.md` and `_DASHBOARD_CHART_JS_SHA384_PIN` in
  `tests/test_dashboard_server.py`.
- **Prior-art honesty precedent**: the weekly chart chose *tokens* as its
  visual unit precisely because an uncosted slice has no USD figure to plot.
  The donut's headline IS dollars, so the inverse resolution applies: the
  doughnut plots **priced tiers only, in USD**; uncosted tiers are surfaced
  by an explicit caption (tier name + token count) and carried in the JSON
  payload — marked, never folded into a $0 slice. The developer directive
  for this unit pre-authorized "an 'uncosted' slice or caption"; caption is
  the only honest option when slice units are USD (mixing a token-sized
  slice into a USD donut fabricates proportion).
- **Rule-of-Three fold (recorded in SPEC-20260610-005602)**: the donut panel
  would be the THIRD additive pre-rendered-HTML param on
  `render_live_fragment(state, weekly_panel_html, hook_health_chip_html)`.
  The recorded watchpoint fires: fold the pre-rendered extras into one
  structured container this unit.

## Requirements

- **R1 — pure renderer**: `render_model_cost_donut_panel(report: CostReport,
  has_run: bool) -> str` in `src/telemetry/dashboard.py` (public, mirroring
  `render_weekly_trends_chart_panel`). Emits the established chart-tile
  shape: `tile--loading` + legend `<p>` + loading-copy + `hidden` wrapper +
  `<canvas id="model-cost-donut-chart">` (accessible `role="img"` +
  `aria-label` + fallback `<p>`) + `<script id="model-cost-donut-data"
  type="application/json">` routed through `_json_in_script`. Ids as module
  constants per the existing id-pin convention. The canvas `aria-label` is
  **fully static copy** (it describes the chart's shape + uncosted handling;
  it interpolates NO tier names) — if a future revision interpolates dynamic
  data into it, that value MUST route through `_esc` like the existing
  renderers (sec F1, this spec's review).
- **R2 — payload shape**: a `_DonutSlice` TypedDict — `tier: str`,
  `cost_usd: float | None`, `tokens: int`, `uncosted: bool`. ALL tiers
  appear in the payload (priced and uncosted); the JS draws slices only for
  `uncosted: false` entries and uses the uncosted entries for the
  caption/tooltip context. Schema-evolution rule mirrors `_ChartPoint`.
- **R3 — honesty (ADR-0020)**:
  - Uncosted tiers NEVER become a $0 slice. They appear in a rendered
    caption ("N tokens across tier(s) X have no list price and are not in
    the donut — uncosted, not free") and in the payload flagged
    `uncosted: true`.
  - Empty corpus / analyzer never run (`has_run is False`) → honest absence
    tile pointing at the capture/analyze pipeline (match the weekly tile's
    vocabulary).
  - `has_run is True` but NO priced tier (all uncosted or zero rows) →
    honest "nothing priced to chart" data-state tile that names the
    uncosted tiers + token counts; never an empty donut with fabricated
    axes/slices.
  - Priced tiers whose summed cost is $0.00 (genuinely zero-priced rows)
    are kept as real slices — Chart.js renders zero-size slices honestly;
    legend still names them.
  - An uncosted tier with zero accumulated tokens (if reachable from
    `build_cost_report`) is still emitted in the payload with `tokens: 0`
    and named in the caption — never silently dropped. If the build
    inspection proves `build_cost_report` cannot emit a zero-token tier,
    document that as unreachable instead of testing it (qa F5).
- **R4 — composition + Rule-of-Three fold**: introduce a frozen dataclass
  `LiveFragmentPanels` (in `src/telemetry/dashboard.py`) with fields
  `hook_health_chip_html: str = ""`, `weekly_panel_html: str = ""`,
  `model_cost_donut_html: str = ""`. Change `render_live_fragment(state,
  panels: LiveFragmentPanels | None = None)`; existing two keyword params
  are REMOVED (no compat shim — update the server + all test call sites in
  the same commit). Composition order: chip first; donut LAST (after the
  weekly chart) per the pinned broader-after-narrower hierarchy — the donut
  is the broadest view (whole stored corpus, no time axis). The caller
  contract (only `src.telemetry.dashboard` helper output may be passed)
  moves onto the dataclass docstring. The dataclass docstring also pins the
  **additive-only evolution rule** (arch F3): a future fourth panel adds a
  field with an empty-string default; never a new positional/keyword param
  on `render_live_fragment` itself.
- **R5 — transport loader**: public `load_cost_report(db_path: Path,
  pricing: PricingTable) -> tuple[CostReport, bool]` in
  `scripts/telemetry/dashboard.py` next to `load_weekly_trends` (read-only
  `?mode=ro` open; missing table → empty report + `has_run=False`;
  `has_run` = rows present OR cost watermark present, the same logic
  `assemble_dashboard_data` uses; a DB file absent entirely — `?mode=ro`
  raises `sqlite3.OperationalError` at connect — maps to
  `(empty report, False)` like `load_weekly_trends`'s outer except, qa F1).
  `dashboard_server.py`'s `/fragments/live`
  route builds the donut panel via the loader + renderer and passes it in
  `LiveFragmentPanels` — no new routes, no reach into `_connect_readonly`.
  Docstring pins (arch F1 + F2): WHY the return is `tuple[CostReport, bool]`
  while `load_weekly_trends` returns a bare `WeeklyTrends` (the cost case
  needs the watermark bit to distinguish ran-with-zero-rows from never-ran;
  the weekly case self-signals via emptiness), and a keep-in-lockstep
  cross-ref between this loader's `has_run` logic and
  `assemble_dashboard_data`'s cost-state computation (both directions; do
  NOT extract a shared helper at N=2).
- **R6 — JS init path**: `renderModelCostDonut()` in
  `src/telemetry/static/dashboard-chart.js`, registered in the existing
  `htmx:afterSwap` dispatch: parse the data block, build a `type: "doughnut"`
  chart over priced slices, colors via the existing tier-color lookup
  (`WEEKLY_TIER_COLORS` + fallback fn — single palette source in JS),
  `borderWidth: 1` (WCAG 1.4.1 adjacent-slice contrast, weekly precedent),
  tooltip shows `$X.XXXX` per slice; per-chart fallback object (mirror
  `weeklyFallback`) so a failed draw shows recovery copy instead of a
  stranded `tile--loading`; `revealChart()` flips tile state on first draw;
  chart instance destroyed before recreate on each swap (established
  lifecycle pattern). Any per-tier accumulator object keyed by
  payload-origin tier strings uses the `hasOwnProperty` guard (mirror
  `buildWeeklyDatasets`) or a null-prototype/`Map` structure so a tier
  named `__proto__`/`constructor` cannot write the prototype chain (sec F2).
- **R7 — SHA-384 lockstep**: re-pin `dashboard-chart.js` digest in BOTH
  `src/telemetry/static/README.md` and `_DASHBOARD_CHART_JS_SHA384_PIN`
  (same commit).
- **R8 — id pins**: extend the existing integration-points regression test
  so `model-cost-donut-chart` / `model-cost-donut-data` literals are
  asserted present in the JS file (same pattern as the weekly ids).

## Constraints

- Read-side only: no DB writes, no new analyzer work, no schema change
  (ADR-0013 compute-don't-store).
- No CSP change: vendored first-party JS under existing `script-src 'self'`;
  NO inline `<script>` beyond the `type="application/json"` data block.
- All dynamic strings through `_esc`; the JSON payload through
  `_json_in_script` (single chokepoint — never re-inline the escape chain).
- `src/telemetry/dashboard.py` stays render-pure (no IO); DB IO only in the
  transport loader.
- Known-broken approaches: none found in the regression ledger for
  donut/chart work; the ledger's chart-adjacent guards (NaN/Inf rejection,
  script-close injection, tile-reveal lifecycle) are inherited via the
  shared helpers and must be exercised for the new panel too.

## Acceptance Criteria

- [ ] AC1: `render_model_cost_donut_panel` with a priced multi-tier report
  emits canvas + data block; payload parses as JSON and carries one entry
  per tier with `tier/cost_usd/tokens/uncosted` fields. Payload tier order
  is deterministic: rendering the same `CostReport` twice yields identical
  JSON arrays (list equality, not set equality — qa F4).
- [ ] AC1b: a single priced tier (one-slice donut) produces a payload with
  exactly one entry (`uncosted: false`) and NO uncosted caption in the
  rendered HTML (qa F3).
- [ ] AC2: an unpriced tier appears in the payload with `uncosted: true` and
  `cost_usd: null`, AND the rendered caption names it with its token count;
  no `$0` or `0.00` is rendered for it anywhere in the panel.
- [ ] AC3: `has_run=False` renders the absence tile (no canvas, no `[]`
  JSON scaffolding in the output).
- [ ] AC4: `has_run=True` with zero priced tiers renders the "nothing priced
  to chart" tile naming uncosted tiers; no canvas/donut emitted.
- [ ] AC5: non-finite `cost_usd` raises `ValueError`
  (`allow_nan=False` inherited via `_json_in_script`).
- [ ] AC6: a tier name carrying `</script><script>` round-trips safely
  (escaped in JSON payload; `_esc`'d in the caption).
- [ ] AC7: canvas has `role="img"`, a non-empty `aria-label` describing the
  chart honestly (mentions uncosted handling), and a fallback `<p>`.
- [ ] AC8: `render_live_fragment(state)` (no panels arg) renders WITHOUT the
  donut/weekly/chip — backward-shape preserved via the dataclass default;
  passing `LiveFragmentPanels(model_cost_donut_html=...)` composes the donut
  LAST inside `#live-section`.
- [ ] AC9: the old `weekly_panel_html=` / `hook_health_chip_html=` keyword
  params are gone (no occurrence of either kwarg anywhere in src/, scripts/,
  or tests/ after the fold — grep-audit; the gate's full pytest run is the
  enforcement backstop, qa F6); the server route passes `LiveFragmentPanels`;
  the composition test pins the FULL six-position index chain (qa F2
  BLOCKING fold): chip < runway < per-turn chart < weekly panel < donut <
  `</section>` via the `html.index()` pattern from the existing weekly
  composition test.
- [ ] AC10: `load_cost_report` — missing table → `(empty report, False)`;
  rows present → `(populated report, True)`; watermark-only (analyzer ran,
  zero rows) → `(empty report, True)`; DB file absent entirely (`?mode=ro`
  connect raises `sqlite3.OperationalError`) → `(empty report, False)`,
  tested with a non-existent `Path` (qa F1 BLOCKING fold). Direct unit
  tests for all four.
- [ ] AC11: `/fragments/live` end-to-end (TestClient) contains the donut
  panel when the DB has cost rows (non-vacuous: a seeded row produces a
  payload entry).
- [ ] AC12: `model-cost-donut-chart` + `model-cost-donut-data` literals are
  asserted present in `dashboard-chart.js`; SHA-384 pin test passes against
  the re-pinned digest (README + test constant identical).
- [ ] AC13: donut slice colors in JS come from the existing tier-color
  lookup (no second palette map); pinned by the existing color-literal test
  pattern.
- [ ] AC14: quality gate 7/7; regression-ledger entry for the new
  surface (single primary test file in the Test File cell; no literal pipe
  characters in prose).

## Risk Assessment

- **Injection surface (medium)**: new JSON-in-script + caption interpolation.
  Mitigated: single `_json_in_script` chokepoint + `_esc` + AC6 round-trip
  test; security-specialist on the review panel (static-asset change).
- **Signature refactor blast radius (medium)**: `render_live_fragment` call
  sites in server + many tests. Mitigated: dataclass default keeps the
  bare `render_live_fragment(state)` form working; grep-audit of all call
  sites in-build; AC8/AC9 pin the new shape.
- **Misleading proportions (low)**: donut with one dominant tier reads fine;
  the dishonest case (uncosted-as-$0) is excluded by R3 design.
- **Per-poll DB IO (low)**: one more bounded read per 3s poll, same scale as
  `load_weekly_trends` (~tens of rows); the recorded caching triggers in
  `load_weekly_trends`'s docstring apply to this loader too (cross-ref it).

## Affected Components

- `src/telemetry/dashboard.py` — new renderer + `LiveFragmentPanels` +
  `render_live_fragment` signature fold + id constants.
- `scripts/telemetry/dashboard.py` — new `load_cost_report` loader.
- `scripts/telemetry/dashboard_server.py` — `/fragments/live` route wiring.
- `src/telemetry/static/dashboard-chart.js` — `renderModelCostDonut` init
  path (+ size/digest change).
- `src/telemetry/static/README.md` — SHA-384 re-pin row.
- `tests/test_telemetry_donut.py` (NEW — separate-file precedent like
  `test_telemetry_weekly.py`) + `tests/test_dashboard_server.py` (loader,
  route, id-pin, SHA pin) + touched composition tests in
  `tests/test_telemetry.py` / `tests/test_telemetry_hooks_health.py` /
  `tests/test_telemetry_weekly.py` for the signature fold.
- `memory/bugs/regression-ledger.md` — new entry.

## Dependencies

- Depends on: vendored Chart.js v4.4.7 (`709cd59`), `_json_in_script`
  helper (`c559816`), `CostReport`/`build_cost_report` (Phase A1),
  watermark helpers in `scripts/telemetry/dashboard.py`.
- Depended on by: Phase 5 `--render-static` (Unit 5.1) reuses the same
  panel helpers (R15 single render path) — the donut renderer must stay
  callable without a server.
