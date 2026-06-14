---
discussion_id: DISC-20260610-022610-review-model-cost-donut
started: 2026-06-10T02:26:27.905443+00:00
ended: 2026-06-10T02:37:46.175054+00:00
agents: [architecture-consultant, facilitator, qa-specialist, security-specialist, ux-evaluator]
total_turns: 11
---

# Discussion: DISC-20260610-022610-review-model-cost-donut

## Turn 1 — facilitator (evidence)
*2026-06-10T02:26:27.905443+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Multi-agent review of Phase 4 Unit 4.2 (model-cost donut, SPEC-20260610-015114) before commit, per the per-unit autonomous workflow (developer directive 2026-06-09: run Phases 3-5 to completion; review is never skipped).
- **Files/scope**: src/telemetry/dashboard.py (render_model_cost_donut_panel + LiveFragmentPanels fold), scripts/telemetry/dashboard.py (load_cost_report), scripts/telemetry/dashboard_server.py (route wiring), src/telemetry/static/dashboard-chart.js (CHART_STATES registry + renderModelCostDonut + shared parseJsonArray), src/telemetry/static/README.md (SHA re-pin), tests/test_telemetry_donut.py (new, 18 tests), tests/test_dashboard_server.py (+6 loader/route + id-pins + SHA pin), tests/test_telemetry_weekly.py + tests/test_telemetry_hooks_health.py (signature-fold call sites), memory/bugs/regression-ledger.md (entry 46).
- **Developer-stated motivation**: the Layer B dashboard is the oversight north star; the donut makes per-tier cost visible at a glance.
- **Explicit constraints**: ADR-0020 uncosted never $0; no CSP change; renderer purity; read-only DB; no push; build checkpoints (CP1 arch+qa, CP2 sec+ux) already resolved 2 REVISE rounds in-build.

---

## Turn 2 — qa-specialist (proposal)
*2026-06-10T02:31:29.895834+00:00 | confidence: 0.88*
*tags: review, qa*

Verdict: APPROVE-WITH-CHANGES (0.88). 0 BLOCKING. F1 MED missing-test: AC13 claims donut colors pinned by the existing color-literal test, but that test covers only the weekly path — no assertion that renderModelCostDonut calls tierColor( rather than a future divergent DONUT_TIER_COLORS map; one-line addition to the integration-points test closes it. F2 LOW: caption _fmt_int large-token variant (1,500,000) cheap guard. F3 LOW: negative cost_usd from a malformed pricing config would sort into the priced group; advisory — upstream pricing validation makes it unreachable; docstring note at most. Strengths: _payload() round-trips json.loads; six-position chain via sorted-indices; determinism+semantic-order combined test; exact-dict pins on the 0.0-vs-None ADR-0020 boundary; ledger entry format-correct; existing tests surgically migrated, none weakened.

---

## Turn 3 — architecture-consultant (proposal)
*2026-06-10T02:31:30.019065+00:00 | confidence: 0.86*
*tags: review, arch*

Verdict: APPROVE-WITH-CHANGES (0.86). 0 BLOCKING. Both recorded Rule-of-Three folds discharged faithfully: LiveFragmentPanels (frozen, additive-only pin, caller contract relocated, no compat shim, all call sites migrated — grep-verified) and CHART_STATES registry (matches the REV-20260608-053032 arch L2 promise; per-chart fallback isolation + destroy/lastCanvas lockstep preserved; helper trio right-sized). M1 MED advisory: parseJsonArray comment mis-frames the Rule-of-Three trigger as the pre-existing duplication rather than the third caller landing — tighten phrasing. L1 LOW: render_live_fragment docstring coherent, keeps the watchpoint live for a fourth chart. Boundaries clean (pure renderer <- transport <- route; no upward imports). load_cost_report tuple rationale + bidirectional lockstep pins present per spec arch F1/F2. R15 satisfied (public helper, callable without a server).

---

## Turn 4 — security-specialist (proposal)
*2026-06-10T02:31:30.153491+00:00 | confidence: 0.93*
*tags: review, security*

Verdict: APPROVE-WITH-CHANGES (0.93). 0 BLOCKING. F1 MED advisory (A03): nothing-priced listing interpolates raw tier strings into body then escapes at emission (_esc(body)) — correct TODAY but a deferred-escape pattern; a natural refactor hoisting the f-string out of _esc silently opens reflected XSS. Recommend per-tier _esc at the interpolation site (the caption path's discipline) and drop the outer _esc. F2 INFO: LiveFragmentPanels caller contract is convention-level — acceptable for an internal type; watch item. SHA-384 triple-lock VERIFIED by independent recompute (MJgwAUxP... matches README + test constant). Trust-boundary table: payload via _json_in_script (allow_nan=False + script-close escapes), caption via _esc, aria-label static, JS parallel arrays + hasOwnProperty, CHART_STATES keys first-party constants, mode=ro + parameterized queries, generic error wrapper intact.

---

## Turn 5 — ux-evaluator (proposal)
*2026-06-10T02:31:30.269012+00:00 | confidence: 0.87*
*tags: review, ux*

Verdict: APPROVE-WITH-CHANGES (0.87). 0 BLOCKING. F1 MED accessibility (WCAG 1.1.1/2.1.1): dollar figures are hover-tooltip-only — keyboard/screen-reader users get the static aria-label but no per-tier numbers; remediate with a server-rendered always-visible per-tier cost breakdown line alongside the canvas (no JS change). F2 LOW: true-zero tile copy is passive + 'populate' jargon — breaks the active-voice register CP2 established on the sibling tiles; revise to match. F3 note: donut tile lacks tile--wide (per-turn + weekly have it) — likely intentional for a compact square chart; verify visually. Strengths: sibling-enumeration pass clean otherwise; absence + nothing-priced copy hit the gatekeeper register; per-chart differentiated fallback copy prevents the REV-20260608-053507 misdirected-recovery bug semantically; canvas fallback text honest; 'Model cost split' title legible to a non-engineer.

---

## Turn 6 — facilitator (critique)
*2026-06-10T02:36:52.163629+00:00 | confidence: 0.8*
*tags: finding-verification*

Finding verification: 5 verified (qa F1 AC13 gap, arch M1 comment framing, sec F1 deferred-escape at dashboard.py nothing-priced branch, ux F1 hover-only dollars, ux F2 true-zero copy — all confirmed against source), 4 inconclusive/general (qa F2/F3 edge inventory, sec F2 convention-contract, ux F3 tile-wide visual), 0 discarded.

---

## Turn 7 — facilitator (synthesis)
*2026-06-10T02:36:52.240598+00:00 | confidence: 0.89*
*tags: blocking:0, advisory:9, speculative:0, model-tiers:default-x4*

## Request Context
- **What was requested**: Review of Phase 4 Unit 4.2 (model-cost donut) before commit, per the 2026-06-09 autonomous Phases-3-5 directive.
- **Files/scope**: 10 files (renderer + loader + route + JS + README pin + 4 test files + ledger).
- **Developer-stated motivation**: dashboard oversight north star.
- **Explicit constraints**: ADR-0020 uncosted never $0; no CSP change; renderer purity; read-only DB; no push.

## Synthesis
4-specialist ensemble unanimous APPROVE-WITH-CHANGES -> APPROVE post-fold; weighted confidence ~0.885; 0 BLOCKING. 5 advisories FOLDED in-session: (qa F1 MED) donut-scoped tierColor pin added to the integration-points test (AC13 was only weekly-pinned); (arch M1 MED) parseJsonArray Rule-of-Three comment re-framed to the third-caller trigger; (sec F1 MED) nothing-priced listing switched from deferred-escape to per-site _esc with a refactor-trap rationale comment; (ux F1 MED) new _render_donut_cost_breakdown always-visible per-tier dollar line closes the hover-only WCAG 1.1.1/2.1.1 gap server-side; (ux F2 LOW) true-zero tile copy moved to the active-voice register. SHA-384 re-pinned post-fold (28329 bytes) and the gate re-ran 7/7. 4 deferred-as-advisory: qa F2 large-token caption test, qa F3 negative-cost note, sec F2 LiveFragmentPanels structural-contract watch item, ux F3 tile-wide visual check. Verification: 5 verified / 4 inconclusive / 0 discarded. 0 speculative, 0 unscored. Model tiers: qa-specialist:default, architecture-consultant:default, security-specialist:default, ux-evaluator:default (no --cost flag). Report: docs/reviews/REV-20260610-022610.md.

---

## Turn 8 — qa-specialist (reflection)
*2026-06-10T02:37:45.928086+00:00 | confidence: 0.8*
*tags: reflection*

Missed: should have probed end-to-end color-mapping coverage before folding the AC13 gap, and whether a spec boundary existed for the large-token case. Rule: when a visual-consistency gap is flagged, require >=1 integration-level render-path test before downgrading from blocking to advisory. Calibration: Original 0.88, Revised 0.82, Delta -0.06.

---

## Turn 9 — architecture-consultant (reflection)
*2026-06-10T02:37:46.006630+00:00 | confidence: 0.8*
*tags: reflection*

Missed: did not trace whether the mis-framed comment string reaches any rendered surface before classifying as style-level. Rule: for comment/label strings in dashboard code, verify whether the string reaches a rendered surface before severity-classifying — rendered comments are defects, not style. Calibration: Original 0.86, Revised 0.82, Delta -0.04.

---

## Turn 10 — security-specialist (reflection)
*2026-06-10T02:37:46.084680+00:00 | confidence: 0.8*
*tags: reflection*

Missed: did not verify the consolidated _esc helper's override surface (importable/monkey-patchable from derived projects) or document the assumed rendering target so a transport shift triggers re-review. Rule: for any escape/sanitize consolidation, confirm non-overridability and pin the rendering-target assumption explicitly. Calibration: Original 0.93, Revised 0.87, Delta -0.06.

---

## Turn 11 — ux-evaluator (reflection)
*2026-06-10T02:37:46.175054+00:00 | confidence: 0.8*
*tags: reflection*

Missed: adjacent-segment palette contrast (3:1) not audited; keyboard-focus tooltip trigger is a separate gap from the screen-reader text line. Rule: for color-primary data viz, run a fixed three-point checklist — adjacent-segment contrast, keyboard tooltip trigger, non-color fallback label. Calibration: Original 0.87, Revised 0.80, Delta -0.07.

---
