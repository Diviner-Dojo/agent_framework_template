---
review_id: REV-20260608-025749
discussion_id: DISC-20260608-025749-telemetry-phase2-wire-chart-slice-1-3
pr_id: ""
risk_level: medium
collaboration_mode: structured-dialogue
exploration_intensity: medium
agents_activated: [qa-specialist, security-specialist, ux-evaluator, architecture-consultant]
reviewed_files:
  - src/telemetry/dashboard.py
  - tests/test_telemetry.py
  - tests/test_dashboard_server.py
rounds: 1
consensus_reached: true
verdict: approve-with-changes
confidence: 0.895
review_duration_minutes: 12
---

## Summary

Phase 2 Layer B dashboard "wire-the-chart" slice — steps 1-3 of the supervised
rolling handoff (Chart.js script tag in shell head + per-turn cost chart panel
with canvas + JSON-literal data block + `</` injection guard). Four specialists
converged on a strengthening fold cohort (0 BLOCKING, 1 HIGH, 5 MED, 7 LOW/INFO).
The fold lands as **APPROVE-WITH-CHANGES → APPROVE post-fold** with **1 HIGH +
4 MED + 4 LOW folded in-session, 1 MED deferred-as-advisory**.

## Request Context

- **What was requested**: Implement Phase 2 wire-the-chart slice steps 1-3 from
  the supervised rolling handoff (HANDOFF-supervisor-rolling.md): (1) add the
  vendored Chart.js script tag to the htmx shell head; (2) add a per-turn cost
  chart panel to `render_live_fragment` with a canvas + JSON-literal data block;
  (3) bake chart data via `json.dumps` with a `</script>` injection guard per
  spec R11/AC6.
- **Files/scope**: `src/telemetry/dashboard.py` (new private
  `_render_per_turn_cost_chart_panel` + composition wiring + chart.js script tag
  + `import json` + 2 id constants + a `_ChartPoint` TypedDict added in-fold +
  one CSS rule added in-fold + canvas accessibility attrs added in-fold);
  `tests/test_telemetry.py` (10 new direct unit tests + 2 updated composition
  tests for the panel-count bump from 3 to 4); `tests/test_dashboard_server.py`
  (1 new transport-layer regression test + clarification of existing
  script-block guard).
- **Developer-stated motivation**: Phase 2 NEXT slice in the supervised
  rolling-handoff workflow. The previous slice (session 11) vendored Chart.js
  v4.4.7 + supply-chain hardening (commit 709cd59). This slice wires the chart's
  MARKUP + DATA-BAKING surface; the actual Chart.js init script lands in a
  separate step 4 slice because that's where the genuine CSP design fork sits
  (inline init vs vendored `dashboard-chart.js`).
- **Explicit constraints**: NO push (autonomous-authorization invariant).
  `/review` mandatory before commit. Step 4 (Chart.js init script)
  INTENTIONALLY OUT OF SCOPE for this slice — the CSP fork escalates via the
  rolling handoff to the next session. No CDN usage (R11a).

## Findings by Specialist

### QA Specialist
- **F1 MED**: Missing regression ledger entry for this slice — established
  precedent (session 10i + 11) is one ledger row per session listing
  root-cause + full test-function list. **Fold**: added.
- **F2 LOW**: Stale ledger references in session 10i entry (two test names
  renamed by this slice). **Fold**: updated.
- **F3 LOW**: Non-finite `cost_usd` edge case — `json.dumps` default
  `allow_nan=True` silently emits `NaN`/`Infinity` tokens. **Fold**: added
  `allow_nan=False` (paired with security F1 below — convergent finding).
- Confidence: 0.91

### Security Specialist
- **F1 MED**: `json.dumps` NaN/Inf silent corruption (OWASP A03 — data
  integrity). Same fold as qa F3.
- **F2 LOW**: CSP coverage documentation gap — the shell CSP is the operative
  policy for fragment content; relaxing it for the Step 4 inline init script
  would remove the XSS backstop. **Fold**: shell docstring carries an explicit
  CSP-scope note.
- **F3 INFO**: `</` → `<\/` escape coverage analysis confirms implementation
  matches HTML5 §12.2.6.1 — `</SCRIPT>` / `</sCrIpT>` / etc all caught; the
  `< /script>` (space-separated) form is not a closing tag per HTML5. No action.
- Confidence: 0.93

### UX Evaluator
- **F1 HIGH**: Empty-canvas interim state reads as broken — until the Phase 2
  init script lands, the data-present path renders a visible-but-blank
  `<canvas>` inside a `tile--data` panel. Reads to a gatekeeper as "the chart
  broke." **Fold**: data-present path now renders `tile--loading` with the
  canvas + data block in an HTML5-`hidden` wrapper (`chart-rendering-target`
  class). The Phase 2 init script removes `hidden` + flips `data-state="data"`
  on first draw. Loading copy explicitly says "Chart visualization layer
  initializing — turn data is also listed in the Live stream panel above."
- **F2 MED**: Canvas missing `aria-label` / `role="img"` (WCAG SC 1.1.1/4.1.2).
  **Fold**: added `role="img"` + descriptive `aria-label` + fallback `<p>`
  inside `<canvas>` for legacy clients.
- **F3 MED**: Legend uses internal vocabulary ("nuance") + cross-panel
  reference. Violates teach-don't-dump pattern. **Fold**: legend rewritten —
  uncosted defined inline ("Turns from model tiers without a known price
  appear at `0.0000` — uncosted, excluded from totals, not zero-rated"); no
  cross-panel reference.
- **F4 LOW**: Heading "Per-turn cost" omits time dimension. **Fold**: renamed
  to "Per-turn cost over time" (one-word change).
- **F5 LOW**: Canvas fixed pixel dimensions break responsive layout (overflow
  on <800px viewports). **Fold**: added `canvas{max-width:100%;height:auto;}`
  to `_LIVE_CSS`.
- Confidence: 0.88

### Architecture Consultant
- **F1 MED**: `cost: 0.0` collapses priced-$0 with uncosted in chart payload —
  C4 honesty-discipline regression. `LiveCostEvent` carries no `uncosted` flag
  (tracked at `LiveState.uncosted_turns` aggregate). **DEFERRED-AS-ADVISORY**:
  this fold touches the fold model (live.py — adding `uncosted: bool` per-event
  + updating `_bump_totals` to propagate it), which is beyond this slice's
  scope. Documented in the `_ChartPoint` TypedDict docstring as a known
  limitation; the next slice (chart init + visual rendering) should land the
  fold-model change in the same cohort alongside the visual distinction
  (dashed line for uncosted turns).
- **F2 MED**: Chart-data contract is implicit; no `TypedDict`. The data shape
  is the API between this slice (renderer) and the next slice (Chart.js init).
  **Fold**: added `_ChartPoint(TypedDict)` with field-by-field docstring
  documenting the contract + the arch F1 known limitation + the schema
  evolution rule (additive non-breaking, removal/rename is breaking).
- **F3 INFO**: `_json_in_script` helper extraction NOT yet warranted (Rule of
  Three — one consumer today). **Fold**: docstring pins the deferred extraction
  trigger so a future reviewer doesn't second-guess.
- **F4 LOW**: O(2N) walks of `recent_events` confirmed not a concern (N ≤ 100,
  3s poll, immutable tuple snapshot). No action.
- **F5 LOW**: First panel with JS-runtime value-delivery dependency confirmed
  bounded by R11a (vendored, SHA384-pinned, same-origin CSP). The live-stream
  panel above has the same per-event cost data — chart is a derived view, so
  Chart.js failure is not a data-loss event. Confirms developer's reframe (d)
  reasoning. No action.
- Confidence: 0.86

## Verification Pass

- 4 verifiable findings checked against source (qa F3 / security F1 NaN —
  verified via `json.dumps({"cost": float("nan")})` repro; arch F1 uncosted
  collision — verified via `live.py:314-316` + `_price_message` evidence;
  security F3 HTML5 closing-tag coverage — verified against HTML5 §12.2.6.1
  spec; arch F4 O(2N) — verified `RECENT_EVENTS_CAP = 100`).
- 0 findings discarded as `verified: false`.
- 9 findings inconclusive (judgment-dependent — UX visual-hierarchy, copy
  quality, contract-completeness — retained per conservative posture).

## Convergence Note

Two pairs of orthogonal specialists landed on the same load-bearing finding,
strongly signaling the right cohort to fold:

1. **qa F3 + security F1 (NaN/Inf)** — qa hit it from data-integrity (test
   coverage gap), security hit it from injection-surface (bare `NaN` token in
   parser-data context). Same `allow_nan=False` fix.
2. **ux F3 + arch F1 (uncosted/$0 collision)** — ux hit it from copy quality
   (cross-panel reference using internal vocab), arch hit it from honesty
   discipline (C4 regression). ux F3 folded (legend rewritten);
   arch F1 deferred-as-advisory (fold-model change beyond slice scope).

The four folded MED/HIGH findings cohere as one strengthening pass on the new
chart panel + its tests: NaN guard at the data boundary + accessibility
attributes at the visual boundary + interim loading-state at the UX boundary +
TypedDict at the contract boundary. The four folded LOW findings are
mechanical: ledger entries (qa F1 + F2) + heading rename (ux F4) + canvas CSS
(ux F5) + CSP-scope note (security F2) + Rule-of-Three pin (arch F3).

## Required Changes Before Merge

All HIGH and MED findings either folded in-session or deferred-as-advisory
(arch F1 only — documented in TypedDict). No remaining required changes.

## Recommended Improvements (Non-Blocking)

All actionable findings folded in-session.

## Speculative Findings — Lower Confidence

None. All specialists reported confidence ≥ 0.86.

## Deferred-as-Advisory (1)

- **arch F1 MED — uncosted/$0 collision in chart payload**. Documented in the
  `_ChartPoint` TypedDict docstring as a known limitation. The next slice
  (Phase 2 step 4 — Chart.js init + visual rendering) should land the
  fold-model change (propagate `uncosted: bool` per-event onto `LiveCostEvent`,
  thread through `_bump_totals` and `_apply_message` in `src/telemetry/live.py`)
  alongside the visual distinction (dashed line / different marker / "(N
  uncosted excluded)" caption — the architecture consultant's Option A or B).
  Re-evaluate at the start of the next slice; if step 4's CSP fork prevents
  the bundled change, file a separate ADR explaining why the discipline
  divergence is acceptable for the interim window.

## Education Gate

- **Required**: no — incremental Phase 2 slice within an established surface
  area (the live dashboard renderers). The fold cohort uses patterns the
  gatekeeper has already learned in sessions 10c-10i (absence vs loading
  vocabulary, JSON-in-script escape seam, TypedDict contract pinning).
- **Bloom's levels**: N/A
- **Mastery tier**: N/A

## Synthesis

The slice ships the chart's markup + data-baking surface with a substantially
stronger contract than originally proposed. The interim `tile--loading` state
(ux F1 fold) eliminates the blank-canvas defect that would have shipped between
this slice and step 4. The `_ChartPoint` TypedDict (arch F2 fold) gives the
next slice's init script a typed API to consume rather than a dict-literal to
re-derive. The `allow_nan=False` guard (qa F3 + security F1 convergent fold)
closes a silent-corruption surface that fold-path constraints today but a
future direct-construction call could trip. The accessibility attributes (ux
F2 fold) close a WCAG AA defect at the visual boundary.

The single deferred-as-advisory finding (arch F1 uncosted/$0 collision) is
honestly out of scope for this slice — it requires a fold-model change in
`live.py` and is naturally folded alongside the visual distinction the next
slice owns. The deferral is documented in code (TypedDict docstring) and in
the handoff for the next session.

Verdict: **APPROVE post-fold**. Ready to commit.
