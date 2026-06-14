---
discussion_id: DISC-20260608-045732-phase2-polish-batch-7-advisories
started: 2026-06-08T04:58:00.847176+00:00
ended: 2026-06-08T05:05:01.883450+00:00
agents: [architecture-consultant, facilitator, qa-specialist, security-specialist]
total_turns: 6
---

# Discussion: DISC-20260608-045732-phase2-polish-batch-7-advisories

## Turn 1 — facilitator (evidence)
*2026-06-08T04:58:00.847176+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Drain the 7 deferred-as-advisory items from REV-20260608-044128 — the polish batch identified as option (B) the default in the supervisor handoff after step 4 (e70cfd3) shipped. Items: qa F3 (test belt-and-suspenders assertion), qa F5 (banner-check comment clarification), qa F6 (formatTimeLabel guard doc), security F3 (README SRI clarification), ux F3 (autoSkip density doc), arch F3 (three-sources-of-truth rephrasing), arch F4 (README pin table Trust model column).
- **Files/scope**: src/telemetry/static/dashboard-chart.js (3 comment-only edits: arch F3 + qa F6 + ux F3), src/telemetry/static/README.md (arch F4 add Trust model column + security F3 SRI note + SHA-384 re-pin), tests/test_telemetry.py (qa F3 add assert), tests/test_dashboard_server.py (qa F5 banner-check clarification + _DASHBOARD_CHART_JS_SHA384_PIN re-pin).
- **Developer-stated motivation**: Default per handoff after no allow-list reply to session-start ASK (3 options: POLISH-BATCH / WEEKLY-CHART / PHASE-3-START). Burns down 7 tracked advisories in a single small cohort commit; well-bounded; safe; closes outstanding items before tackling the new-front weekly-chart slice.
- **Explicit constraints**: NO push (per autonomous_workflow); /review required before commit (touches src/); preserve all prior load-bearing guards (SHA-384 pin discipline, palette pin, JSON-in-script escape chain, CSP same-origin); SHA-384 must be re-pinned in lockstep across README + test constant; no behavior change in dashboard-chart.js (all edits are inside comment blocks).

---

## Turn 2 — qa-specialist (proposal)
*2026-06-08T05:01:24.571006+00:00 | confidence: 0.94*
*tags: verdict:approve-with-changes, blocking:0, advisory:2, info:1*

**Verdict**: APPROVE-WITH-CHANGES (2 LOW + 1 Info; both LOW are easy in-session folds)

**F1 LOW (weak-assertion / comment-accuracy)**: tests/test_telemetry.py:3809-3814 — qa F3 comment overstates precision. `assert '[]' not in panel` is satisfied by any '[]' substring; the REAL guard value is that the renderer takes the `if not priced_points: return absence_html` exit BEFORE constructing any `<script type="application/json">` data block. Rec: tighten comment to 'The Python renderer exits via the absence path before constructing any JSON data block, so neither type="application/json" nor any JSON content (including []) appears in the absence output. This guards the structural invariant, not a substring coincidence.'

**F2 LOW (stale forward-reference comments — regression magnets)**: tests/test_telemetry.py:3781-3784 ('Phase 2 next-step note: the Chart.js init script... lands in a separate slice — see HANDOFF...step 4 (the CSP design fork).') and line 3887 ('before step 4 ships. The Phase 2 init script removes the hidden attribute on first draw.'). Step 4 shipped in e70cfd3; comments now describe a past state in future tense. Same pattern as session 15 fold of HIGH stale 'When step 4 ships' comments.

**F3 Info (no action)**: dashboard-chart.js autoSkip '~800 px / future slice widens to ~250 events' forward advisory is NOT stale — describes a genuine future design fork.

**Confirmed Passing Checks**: qa F3 assertion logic sound; qa F5 banner-check accurate; qa F6 formatTimeLabel guard comment accurate; SHA-384 triple-lockstep verified end-to-end (file=14242 bytes / README=vA8Q... / test constant=vA8Q...); 3 dashboard-chart.js edits are comment-only (no executable code changed); README pin table parseable by _read_sha384_pin_from_readme (cell-scan is alignment-agnostic); arch F3 + arch F4 wording correct; security F3 SRI clarification accurate.

**Strengths**: SHA-384 triple-lockstep exemplary first-party supply-chain discipline; `_read_sha384_pin_from_readme` parser is column-position-agnostic by design; qa F5 clarification earns its line count; ux F3 autoSkip comment includes scoped actionable forward-advisory.

---

## Turn 3 — architecture-consultant (proposal)
*2026-06-08T05:01:39.369327+00:00 | confidence: 0.92*
*tags: verdict:approve, blocking:0, advisory:0, info:3*

**Verdict**: APPROVE (3 Info findings; no action required this batch)

**F1 Info (Rule-of-Three trigger — defer)**: dashboard-chart.js:51-52 + dashboard.py:868,871 + test_telemetry.py (6 anchor lines). The rephrased arch F3 comment makes the 3-location id-string pattern EXPLICIT — the same pattern that already earned palette literals a regression pin (`_SHARED_PALETTE_HEX_LITERALS` from arch F1 fold). Phase 2 has 1 chart panel; when weekly-chart slice lands, 2 panels × 2 ids = Rule-of-Three trigger. Add an _id-pinning regression test mirroring `test_dashboard_chart_palette_literals_are_synchronised_with_python_css` AT THAT POINT — not now. Logged here so next reviewer doesn't re-derive.

**F2 Info (Trust model column completeness)**: README.md:11-15 — 2-value vocab (third-party / first-party) is correct for current rows since every row is integrity-pinned. Richer labels would add no discriminating info. No change required this batch; if a non-pinned asset is ever added, expand vocab at that point.

**F3 Info (column + prose redundancy intentional)**: README.md:11-15 vs README.md:50-61 — column answers a scanning reader; prose answers a deliberating reader. Removing either weakens the README for one audience. Keep both; not duplication-debt. Door-policy: would become drift-debt only if prose later restates column values verbatim.

**Architectural Alignment**: ADR-0020 honesty discipline materially strengthened (Not-browser-SRI callout + qa F5 banner clarification explicitly name what the integrity anchor IS vs ISN'T). Principle #8 (least-complex intervention first): both arch F3 and arch F4 are prose interventions, not abstractions — correct intervention scale.

**Boundary Analysis**: Python→JS dependency direction preserved (JS hard-codes id strings, no template interpolation surface under script-src 'self' CSP). README↔test-constant contract parser is column-position-agnostic; arch F4 column-count change is safe end-to-end (verified against new table). Trust-boundary axis (third-party / first-party) correctly names the only boundary that matters for the pin-table's purpose.

**Strengths**: arch F3 names an asymmetry (Python = source of truth, JS+tests = copies) not a symmetry — preserves authority hierarchy a future rename needs; arch F4 column preserves parser contract by design; door policy across the batch is exemplary (closes comprehension door, opens no structural doors).

---

## Turn 4 — security-specialist (proposal)
*2026-06-08T05:01:52.006669+00:00 | confidence: 0.97*
*tags: verdict:approve, blocking:0, advisory:0, info:0*

**Verdict**: APPROVE (no findings)

This change set is documentation-only in security terms: 3 comment additions to a first-party JS file, a README clarification of the supply-chain integrity model, and a pin rotation driven by those comment additions. The threat surface is unchanged.

**SHA-384 re-pin lockstep verified by direct computation**: computed hash = `vA8QifhIA8IT53aPS8bi8qRF7WKKV3V4lKrxZ7OxnNaPeTpsxLbUibR/Qzr7sAIk`, byte count = 14242. Matches README.md:15 pin AND `_DASHBOARD_CHART_JS_SHA384_PIN` at tests/test_dashboard_server.py:814 exactly. Three-way lockstep intact; `test_vendored_dashboard_chart_sha384_matches_readme_pin` will pass.

**F3 SRI clarification appropriately calibrated**: README.md:28-32 correctly states the digests are NOT browser `integrity=` attributes, same-origin under script-src 'self' makes browser SRI redundant, and digests are CI-side anchors only. Critically does NOT overclaim ('prevents runtime tampering' / 'protects against MITM'). Honest about what CI-side enforcement does (catches byte drift before merge) and implicitly honest about what it does not do.

**Comment-only edits — no executable change**: all 3 dashboard-chart.js edits inside JSDoc/inline comment regions. IIFE structure, 'use strict' pragma, all dataset construction, htmx listeners, DOMContentLoaded handler unchanged.

**Escape chain intact**: dashboard.py:1002-1007 retains all 3 replacements (`</` → `<\/`, `<!--` → `<\!--`, `-->` → `--\>`) with `allow_nan=False`. No edit touches that function.

**'First-party' label is honest**: README.md:50-61 correctly distinguishes the two supply chains (CDN→npm→upstream GitHub for third-party vs local commit history for first-party). The 'supply chain is just the local commit history' framing matches the file's actual provenance with no overstatement.

**Trust Boundaries**: Python-to-browser data seam in dashboard.py controls (json.dumps allow_nan=False + 3-way escape chain) remain intact at lines 1002-1007. Static asset serving under script-src 'self' unchanged.

**No false reassurance introduced**: README does not assert pin provides runtime protection, blocks deployment-side substitution, or replaces CSP. The 'Not browser SRI' callout actively CORRECTS a potential misreading rather than adding one.

---

## Turn 5 — facilitator (critique)
*2026-06-08T05:04:34.870915+00:00 | confidence: 0.8*
*tags: finding-verification, in-session-folds:3*

**Finding verification**: 3 LOW findings from qa-specialist (F1 + F2-A + F2-B); 3 INFO findings from architecture-consultant; 0 from security-specialist. All verified against actual file content (qa F1 comment at test_telemetry.py:3809-3814 matches description; qa F2-A stale forward-ref at lines 3781-3784 matches verbatim; qa F2-B stale 'before step 4 ships' at lines 3886-3888 matches verbatim). 0 discarded. 0 inconclusive. Architecture INFO findings explicitly tagged 'no action this batch' by the reporting specialist — preserved in the report as forward-context for the next reviewer.

**In-session folds (3)**:
1. qa F1 LOW (comment-accuracy refinement) — FOLDED at test_telemetry.py:3809-3816. Tightened to explicitly name the structural invariant: 'no JSON scaffolding reaches the absence path' (vs the prior wording that read as a substring-coincidence guard).
2. qa F2-A LOW (stale forward-ref) — FOLDED at test_telemetry.py:3781-3787. Replaced 'Phase 2 next-step note... lands in a separate slice — see HANDOFF...' with shipped-state framing pointing at e70cfd3 + dashboard-chart.js + the arch F3 Python-as-source-of-truth comment.
3. qa F2-B LOW (stale 'before step 4 ships') — FOLDED at test_telemetry.py:3886-3891. Replaced 'before step 4 ships. The Phase 2 init script removes the hidden attribute...' with shipped-state framing that names the Python-renderer-PERMANENT wire format + the JS runtime mutation + the gatekeeper-protection rationale.

Three architecture INFO findings deferred-as-context (no action required this batch):
- arch F1 INFO: Rule-of-Three id-string pinning trigger — defer until weekly-chart slice lands (2nd panel → 4 id instances → trigger fires).
- arch F2 INFO: Trust model column 2-value vocab is correct for current rows.
- arch F3 INFO: README column + prose are intentional reinforcement, not duplication-debt.

Test files do not affect the SHA-384 pin (only dashboard-chart.js bytes feed the pin). No re-pin needed for the in-session folds.

---

## Turn 6 — facilitator (synthesis)
*2026-06-08T05:05:01.883450+00:00 | confidence: 0.94*
*tags: blocking:0, advisory:3, info:3, speculative:0, model-tiers:qa-specialist:sonnet, architecture-consultant:sonnet, security-specialist:sonnet, verdict:approve-with-changes-post-fold-approve, in-session-folds:3*

## Request Context
- **What was requested**: Drain the 7 deferred-as-advisory items from REV-20260608-044128 (the polish batch identified as option B and the default in the supervisor handoff after step 4 / e70cfd3 shipped).
- **Files/scope**: src/telemetry/static/dashboard-chart.js (3 comment-only edits: arch F3 + qa F6 + ux F3), src/telemetry/static/README.md (arch F4 + security F3 + SHA-384 re-pin), tests/test_telemetry.py (qa F3 new assertion + 2 in-session fold updates from this review), tests/test_dashboard_server.py (qa F5 comment + _DASHBOARD_CHART_JS_SHA384_PIN re-pin).
- **Developer-stated motivation**: Default per handoff after no allow-list reply to session-start ASK; closes 7 tracked advisories in a single small cohort commit.
- **Explicit constraints**: NO push; preserve all prior load-bearing guards; SHA-384 lockstep across README + test constant; no behavior change in dashboard-chart.js.

**Verdict**: APPROVE-WITH-CHANGES → APPROVE post-fold

**Ensemble** (3 specialists, parallel): qa-specialist 0.94 + architecture-consultant 0.92 + security-specialist 0.97 → weighted ~0.94.

**Findings**: 0 BLOCKING. 3 LOW from qa-specialist (qa F1 comment-accuracy refinement + qa F2-A + qa F2-B stale forward-references) — ALL 3 FOLDED IN-SESSION. 3 INFO from architecture-consultant (Rule-of-Three id-string pin trigger for next slice, Trust model column completeness, column+prose intentional reinforcement) — all explicitly 'no action this batch' per the reporting specialist; preserved as forward-context. 0 findings from security-specialist.

**Verification**: 3 verified true, 0 discarded, 0 inconclusive. The qa F1 + F2 stale-comment findings match verbatim against the actual file content.

**Confidence annotation**: 0 findings in speculative section (all >= 0.90). 0 retained as unscored.

**Model tiers**: qa-specialist:sonnet, architecture-consultant:sonnet, security-specialist:sonnet (cost flag default; all default-tier per agent definitions).

**Notable convergence**: security-specialist + architecture-consultant + qa-specialist independently confirm SHA-384 triple-lockstep is intact (file=14242 bytes / README pin / _DASHBOARD_CHART_JS_SHA384_PIN test constant all = vA8QifhIA8IT53aPS8bi8qRF7WKKV3V4lKrxZ7OxnNaPeTpsxLbUibR/Qzr7sAIk). The _read_sha384_pin_from_readme parser is column-position-agnostic (cell-scan by prefix), so arch F4's Trust model column addition does not break the pin-matching tests. The 'Not browser SRI' callout is appropriately calibrated (no overclaim).

**ADR-0020 honesty discipline**: materially strengthened — both the README 'Not browser SRI' callout and the qa F5 banner-vs-pin clarification explicitly name what the integrity anchor IS vs ISN'T (no false equivalence).

**Education gate**: Not required (low risk; comment/doc edits only; no new contract surface). Optional walkthrough of the cross-language Python↔JS contract (canvas id / data-block id / palette literals / htmx event seam) would remain useful before the weekly-chart slice — same recommendation as REV-20260608-044128.

**Quality gate**: 7/7 (post-fold; tests unchanged at 289, ruff clean, ledger 39 guards).

---
