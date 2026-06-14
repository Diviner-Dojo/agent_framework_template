---
discussion_id: DISC-20260608-053507-phase2-build-weekly-trends-chart
status: closed
sealed_at: 2026-06-08T22:30:00+00:00
risk_level: medium
collaboration_mode: ensemble
linked_review: REV-20260608-053507
---

# Phase 2 weekly trends chart — build close (session 17)

## Outcome

The WIP weekly-trends chart slice was finished in session 17 after being
inherited from an earlier supervised session. The blocking failing test
(`test_server_uses_a_arch1_public_helpers_not_underscored`) was resolved
via **option (b)** per Principle #8 (least-complex): a new public
`load_weekly_trends(db_path, pricing) -> WeeklyTrends` was added to
`scripts/telemetry/dashboard.py` next to `assemble_dashboard_data`, so
`_connect_readonly` stays private and the dead-helper regression guard
(REV-20260607-200447 arch F3) is preserved verbatim. `dashboard_server.py`
imports the public loader; nothing in the transport layer reaches into a
single-underscore private of the read-only-DB module.

## /review verdict

REV-20260608-053507 (4-specialist ensemble): qa-specialist 0.91 +
architecture-consultant 0.86 + security-specialist 0.97 + ux-evaluator
0.87 — weighted ~0.90. **APPROVE-WITH-CHANGES → APPROVE post-fold**, 0
BLOCKING / 6 folded in-session / 6 deferred-as-advisory (all prose-only
or hypothetical-future).

### In-session folds (6)

- **ux F1 HIGH**: shared fallback timer could permanently strand the
  weekly chart in `tile--loading` if the per-turn chart drew first.
  Replaced with per-chart `perTurnFallback` / `weeklyFallback` objects
  carrying their own `timerId` + `delivered` + `canvasId` + `copy`. A
  successful draw on one chart no longer cancels the other.
- **ux F2 HIGH**: fallback copy was per-turn-specific ("Live stream
  panel above") and got stamped onto the weekly tile when fired —
  misdirecting the user. Recovery copy is now per-chart and targeted by
  canvas id, so the weekly fallback points at the retrospective cost
  view.
- **qa F1 HIGH**: 5 direct branch tests added for `load_weekly_trends`
  (DB missing / cost_rows table absent / discussions table absent /
  happy-path JOIN / malformed created_at).
- **arch F1 MED**: `_render_weekly_trends_chart_panel` promoted to
  public `render_weekly_trends_chart_panel`. Cross-module access to a
  single-underscore private was the same shape of erosion the arch F3
  guard exists to catch on the renderer axis.
- **qa F2 MED**: new `test_weekly_tier_color_literals_are_pinned_in_js`
  extends the palette-sync discipline to the JS-side `WEEKLY_TIER_COLORS`
  map (hex literals + tier keys).
- **ux F5 MED**: `borderWidth: 1` with bg color on weekly bar dataset —
  WCAG 1.4.1, gives adjacent stack slices a non-color separation
  channel (blue and purple have similar luminance under deuteranopia).
- **qa F4 LOW**: empty-tuple test added to `_render_weekly_delta_caption`.

### Deferred-as-advisory (6)

All explicitly low-risk prose improvements or hypothetical-future:
security F1 (per-discussion advisory location), security F2 (`base-uri`
CSP hypothetical until `<base>` tag added), arch F2 (map-generalization
trigger naming in JS L2 docstring), arch F3 (no-action), ux F3 (legend
ordering), ux F4 (delta caption prose framing), ux F6 (canvas fallback
wording).

## Quality gate

7/7 PASS. ruff format + check clean; tests pass; coverage 97.45%; 19
ADRs; review present; regression ledger now 41 guards; BUILD_STATUS
fresh.

## Triple Rule-of-Three triggers landed in this cohort

1. `_json_in_script` helper extraction in `src/telemetry/dashboard.py` —
   both chart panels (per-turn + weekly) now route through one auditable
   escape chokepoint.
2. Canvas/data-block id-string pin extended at
   `test_dashboard_chart_init_script_carries_load_bearing_integration_points`
   to cover `weekly-trends-chart` + `weekly-trends-data`.
3. Palette literals — the shared 4 hex literals stay covered by the
   existing cross-Py/JS sync test; the new `WEEKLY_TIER_COLORS` map
   gets its own dedicated pin.

## SHA-384 re-pin

`dashboard-chart.js` bytes 14242 → 23513; digest
`uTPT7PNOVjojQmcUsQt8DvbaK+94T+046qdVX1dIUwTrBXYZgKcTpR5lzDmyZmLH`
written in lockstep to BOTH the README pin table AND
`_DASHBOARD_CHART_JS_SHA384_PIN` in `tests/test_dashboard_server.py`.

## Phase 2 status

**COMPLETE per developer directive (2026-06-07 in-person via the
orchestrator).** Both the weekly-trends chart (A) and the polish batch
(B) are now shipped on `fix/c-gate-log-integrity`. The next supervised
session ends with `SUPERVISOR_DONE`; do not start Phase 3 — the
developer wants to reassess first.
