---
discussion_id: DISC-20260608-053032-phase2-weekly-trends-chart-design-review
started: 2026-06-08T05:30:50.040088+00:00
ended: 2026-06-08T05:34:49.189324+00:00
agents: [architecture-consultant, facilitator, qa-specialist, security-specialist]
total_turns: 5
---

# Discussion: DISC-20260608-053032-phase2-weekly-trends-chart-design-review

## Turn 1 — facilitator (evidence)
*2026-06-08T05:30:50.040088+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Phase 2 weekly trends chart for the Layer B live dashboard daemon (per the rolling supervised-session handoff: developer directive 2026-06-07 pre-authorizes both the polish batch and the weekly-trends chart, then STOP — do NOT start Phase 3). Polish batch shipped session 16 as d157fc9; weekly-trends chart is the last unit before SUPERVISOR_DONE.
- **Files/scope**: NEW src/telemetry/weekly.py (pure aggregator); MODIFIED src/telemetry/dashboard.py (_render_weekly_trends_chart_panel + render_live_fragment optional param); MODIFIED scripts/telemetry/dashboard_server.py (load + aggregate + pass); MODIFIED src/telemetry/static/dashboard-chart.js (parallel init path); MODIFIED tests/test_telemetry.py + tests/test_dashboard_server.py.
- **Developer-stated motivation**: Phase 2 of SPEC-20260607-183136 promises 'weekly trends + prior-window deltas' (R6). It is the second chart consumer, triggering THREE Rule-of-Three pins simultaneously: (1) extract _json_in_script helper; (2) id-string pin extends to weekly canvas/data ids; (3) palette pin extends to weekly chart colors. The directive: ship Phase 2 to closure before reassessment.
- **Explicit constraints**: NO push (NEVER). NO CSP relaxation (option (a) VENDORED-INIT pattern from step 4 — same-origin, script-src 'self'). PARALLEL init paths in JS (least-complex first at N=2 per Principle #8 — do NOT generalize). PRESERVE live.py purity (AC14: no scripts.* import, no transcript IO) — render_live_fragment accepts a pre-rendered weekly panel HTML string, the DB IO stays in dashboard_server.py. ADR-0020 honesty discipline: 'uncosted ≠ $0' — uncosted slice must be MARKED, never collapsed into a USD axis. Stacked bar by tier with TOKEN units (cost in tooltip), uncosted as its own slice.

---

## Turn 2 — architecture-consultant (critique)
*2026-06-08T05:33:46.766788+00:00 | confidence: 0.86*
*tags: design-review, architecture, blocking, rule-of-three, per-poll-db-io*

APPROVE-WITH-CHANGES (confidence 0.86)

## BLOCKING

H1 — Rule-of-Three justification math (Principle #8 / Rule of Three; src/telemetry/dashboard.py:969-975 docstring): The handoff text claims THREE pins simultaneously, but per-turn = consumer #1, weekly = consumer #2. The helper-counting-itself is not Rule-of-Three; it is Rule-of-Two-honoring-a-promised-extraction (the dashboard.py:969-975 docstring explicitly promised: 'when a second consumer of this pattern lands, extract a _json_in_script helper'). Pick (a) extract NOW because the docstring promise is load-bearing. Correct the spec's framing — extracting elsewhere under wrong 3-pin math would trigger premature abstractions.

H2 — Per-poll DB IO coupling/perf-seam (Principle #8 + cross-cutting concerns): The /fragments/live route polls every 3s. This slice introduces the FIRST DB-read on the hot path. 73 rows today is sub-ms; with months of retention this becomes 5,000+. Either (a) add a loader-seam now (15 LOC, app.state-injected with default identity-loader, future-proofs caching), OR (b) accept inline call but add ADR-style comment naming trigger conditions ('revisit if median row count > 1,000 OR median aggregation latency > 10ms'). Don't ship with neither.

## Advisory

L1 — Document panel placement (spec R2 visual hierarchy): per-turn chart docstring at dashboard.py:678-690 explicitly says 'chart appears LAST because it is a derived view'. Weekly trends is ALSO derived, with a broader window. Place AFTER per-turn (broader after broader) and document the same framing in the new panel's docstring. Pins the contract before a 3rd chart arrives.

L2 — JS module-level vars (Q5): parallel pairs (weeklyChartInstance, lastWeeklyCanvas), NOT a map. Map IS the deferred generalization. FALLBACK timer + fallbackDelivered can stay singleton (one-shot recovery copy).

## Q3 — Stacked bar vs paired bars
Confirm stacked-by-tier. Rationale: uncosted slot is natural separate stack segment preserving ADR-0020 honesty; USD already breaks down by tier on cost panel; dual-axis cognitive load is consistent ux friction for manager-gatekeeper persona.

## Strengths
Module placement (sibling of cost.py) shows correct boundary judgment. Backward-compat empty-string default on render_live_fragment kwarg. Server-side delta caption rendering. Reusing _esc/_fmt_*/_absence_tile preserves AC6 single seam.

---

## Turn 3 — security-specialist (critique)
*2026-06-08T05:33:57.641153+00:00 | confidence: 0.91*
*tags: design-review, security, _json_in_script, build-precondition*

APPROVE-WITH-CHANGES (confidence 0.91)

## BLOCKING
None.

## Advisory

M1 — _json_in_script helper extraction is the right seam, make it a build pre-condition (OWASP A03 Injection): consolidates the 4-step escape chain to one auditable location; without extraction a future third consumer is statistically likely to omit one of the steps (most likely <!-- comment-mode escape). Module-level private function in dashboard.py + unit test asserting all four transforms on a payload containing </script>, <!--, -->. The test becomes the spec.

L1 — discussion-ID injection path confirmed non-applicable (informational): payload contains only server-controlled tier names (from config/model_pricing.yaml or literal 'unknown') and ISO date strings. Discussion IDs are aggregation grouping keys, NOT in the JSON output. Add a one-line docstring on the aggregator noting this — if a future iteration adds per-discussion breakdown, the helper still covers escape but the aggregator contract should be explicit.

## Trust Boundaries
- DB → server: ?mode=ro URI gives OS-level write enforcement on C1; no design change.
- Server → fragment: <script type='application/json'> is the SOLE injection surface; 4-step escape chain from REV-20260608-025749 must propagate (handled by extracted helper).
- Fragment → browser: CSP script-src 'self' unchanged. Data block is not executable under HTML5 — no CSP change.
- No new headers, CORS, or middleware required.

## Strengths
Tier names + week dates are server-controlled constants — no user input in serialization path. ?mode=ro flag at SQLite layer (not just app-level convention). Prior-window delta caption uses _esc helper. Parallel JS init at N=2 opens no new trust boundary.

---

## Turn 4 — qa-specialist (critique)
*2026-06-08T05:34:10.794250+00:00 | confidence: 0.87*
*tags: design-review, qa, blocking, delta-caption, composition-count, iso-boundary*

APPROVE-WITH-CHANGES (confidence 0.87)

## BLOCKING

H1 — Zero-denominator delta-caption edge case (missing-edge-case): Q4 covers 'only one week → caption omitted' but NOT the case where prior week priced_cost_usd == 0.0 (e.g., all uncosted tokens, no priced events). Formula (week_n - 0)/0 raises ZeroDivisionError or returns inf. Reachable in normal operation. Spec the behavior (omit caption OR show 'N/A') and pin it with a test.

H2 — Composition count must be DECIDED, not left open (missing-regression): the 4→5 panel bump note says 'data-state=loading bumps 1→2 — need re-evaluation' but this is load-bearing. Decide first-paint state BEFORE writing the test. Test must encode the chosen behavior, not leave it open. @pytest.mark.regression.

## Advisory

M1 — Read-only invariant weak-assertion: 'transport opens with ?mode=ro' is a URL-string check, not a behavioral check. Either assert write attempt against the opened conn raises sqlite3.OperationalError, OR document explicitly that the URL check is the intended scope.

M2 — ISO year-boundary edge case missing (boundary value enumeration): proposal covers Sun 23:59 / Mon 00:00 but not Dec 28 (ISO 2026-W53) / Jan 4 (ISO 2027-W01) — the subtlest ISO calendar case and most likely to produce off-by-one Jan aggregation errors. Add parameterized case @pytest.mark.regression.

L1 — Known-tier-missing-from-pricing case (missing-test): 'unknown tier' branch is covered but not the case where a KNOWN model_id has cost_usd=None because the model is not in pricing.yaml. Should also flow to WeeklyTotal.uncosted_tokens per ADR-0020 'uncosted ≠ $0'. Add parameterized case.

L2 — Missing-created_at policy (design Q3): defensive skip vs hard assertion is unresolved. Pick one in the weekly.py spec comment, then test the chosen behavior (pytest.warns/caplog for skip; pytest.raises for assertion).

## Strengths
_json_in_script extraction creating isolated helper test surface. WCAG coverage at unit level. ISO @pytest.mark.regression classification correct. Reusing palette pin across both charts vs duplicating.

---

## Turn 5 — facilitator (synthesis)
*2026-06-08T05:34:49.189324+00:00 | confidence: 0.88*

## Request Context
- **What was requested**: Phase 2 weekly trends chart for Layer B live dashboard (final unit before SUPERVISOR_DONE per developer directive 2026-06-07).
- **Files/scope**: NEW src/telemetry/weekly.py; MODIFIED src/telemetry/dashboard.py (renderer + _json_in_script helper); MODIFIED scripts/telemetry/dashboard_server.py (load + aggregate + pass); MODIFIED src/telemetry/static/dashboard-chart.js (parallel init); tests in tests/test_telemetry.py + tests/test_dashboard_server.py.
- **Developer-stated motivation**: SPEC-20260607-183136 R6 (weekly trends + prior-window deltas). Pre-authorized.
- **Explicit constraints**: NO push, NO CSP relaxation, parallel JS init at N=2, AC14 purity, ADR-0020 honesty (uncosted MARKED).

## Synthesis

Ensemble: architecture-consultant 0.86 + security-specialist 0.91 + qa-specialist 0.87 → weighted ~0.88. All three APPROVE-WITH-CHANGES, 4 BLOCKING items folded into the build plan + 6 advisories addressed below.

### Design decisions taken (all BLOCKING items resolved)

1. **Rule-of-Three framing (arch H1 RESOLVED)**: This slice is **Rule-of-Two-honoring-the-promised-extraction** from dashboard.py:969-975, NOT 'three pins simultaneously'. Extract _json_in_script(payload) NOW as the docstring promised; correct the spec language in the build. The 'triple pin' wording in the inherited handoff was loose — actually means: extract _json_in_script (Rule of Two honored) + extend id-string pin to weekly ids (existing test grows) + reuse COLOR_* constants (existing palette pin continues to cover both charts). Three pins, but only ONE Rule-of-Three trigger fires (the other two are extension of existing pins).

2. **Per-poll DB IO seam (arch H2 RESOLVED)**: Accept inline call at N=73 rows + add explicit decision comment in the route handler with trigger conditions: 'revisit if median row count > 1,000 OR median aggregation latency > 10ms'. Option (b) per the architecture-consultant; the loader-seam (option a) is the deferred follow-up if either trigger fires. This decision is the door — naming the trigger makes the door visible.

3. **Composition first-paint state (qa H2 RESOLVED)**: Weekly chart uses the SAME tile--loading first-paint pattern as per-turn (mirrors the design contract: chart panels stay loading until JS reveals on first draw). So data-state='loading' count bumps 1→2; data-state='data' stays at 3 (priced) until JS reveals. Composition test will encode this; @pytest.mark.regression.

4. **Delta-caption zero-denominator (qa H1 RESOLVED)**: When week N-1 priced_cost_usd == 0.0 (or only one week of data exists), the caption is OMITTED entirely. Decision: omit (matches honest-absence pattern across the dashboard — never fabricate a delta). Pin with a test.

### Folded advisories (build-time)

- _json_in_script helper (sec M1 + arch H1): module-level private function in dashboard.py with unit test asserting all four transforms on payload containing </script>, <!--, -->. Helper test = spec.
- Aggregator docstring (sec L1): explicit note that discussion_ids are aggregation grouping keys, NOT in JSON output (forward-context for future per-discussion breakdown).
- Panel placement docstring (arch L1): _render_weekly_trends_chart_panel docstring carries the 'appears LAST because broader window' framing, pinning the visual-hierarchy contract.
- JS module-level vars (arch L2): parallel pairs (weeklyChartInstance, lastWeeklyCanvas), NOT a map; FALLBACK timer + fallbackDelivered stay singleton.
- ISO year-boundary test (qa M2): parameterized @pytest.mark.regression case for Dec 28 (ISO 2026-W53) / Jan 4 (ISO 2027-W01).
- Known-tier-missing-from-pricing (qa L1): parameterized case asserting tokens flow to WeeklyTotal.uncosted_tokens.
- Defensive-skip + warning policy (qa L2): aggregator emits a warning via the standard logging module and skips rows whose discussion_id is missing from created_at_lookup. Test via caplog.
- Behavioral read-only assertion (qa M1): integration test asserts write attempt against the transport's opened connection raises sqlite3.OperationalError.

### Build plan (ready for /build_module)

Task 1: Extract _json_in_script(payload) helper in dashboard.py + migrate per-turn chart call site + unit test for all 4 escape steps.
Task 2: New src/telemetry/weekly.py — WeeklyTierBucket, WeeklyTotal, WeeklyTrends dataclasses + aggregate_by_week + unit tests (all 9 cases including ISO year boundary + defensive skip).
Task 3: _render_weekly_trends_chart_panel in dashboard.py — empty/populated paths, panel-placement docstring, prior-window delta caption (omit-on-zero-denom or single-week), reuse _json_in_script.
Task 4: render_live_fragment gains keyword arg weekly_panel_html='' (backward-compat) + composition tests updated to 5 panels (loading 1→2, data 3).
Task 5: dashboard_server.py — load discussion_model_tokens JOIN discussions.created_at on /fragments/live, aggregate via aggregate_by_week, render panel, pass to render_live_fragment. ADR-style comment naming caching-trigger conditions. Behavioral read-only assertion in test.
Task 6: dashboard-chart.js — parallel renderWeeklyChart() + weeklyChartInstance/lastWeeklyCanvas pair + htmx hook calls both + tooltip/legend for stacked bar.
Task 7: SHA-384 re-pin lockstep (README + _DASHBOARD_CHART_JS_SHA384_PIN), id-string pin extension, palette pin sanity (already covers via COLOR_* reuse), regression ledger entry (single primary path in cells[4] per session-16 parser gotcha).

Workflow forward: /build_module → quality gate → /review (4-specialist ensemble) → commit (NO push) → say milestone → UPDATE handoff → SUPERVISOR_DONE.

---
