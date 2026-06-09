---
discussion_id: DISC-20260609-060229-phase3-unit2-config-drift-rows
started: 2026-06-09T06:02:48.100901+00:00
ended: 2026-06-09T06:14:17.833437+00:00
agents: [architecture-consultant, facilitator, qa-specialist, ux-evaluator]
total_turns: 6
---

# Discussion: DISC-20260609-060229-phase3-unit2-config-drift-rows

## Turn 1 — facilitator (evidence)
*2026-06-09T06:02:48.100901+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Phase 3 Unit 2 — config-drift rows (per SPEC-20260607-183136 §Phase 3 'failure intelligence'). Build a detector + render path that surfaces configuration-drift signals between the current pricing/subscription configs and the captured discussion window. From the rolling handoff: '/plan first (detector design + render shape is a genuine design fork — the choice between extending the failure panel and adding a sibling panel changes the data flow).' Workflow: build → quality gate → /review → commit (NO push) → roll.
- **Files/scope**: NEW src/telemetry/drift.py (~280 LOC pure detector module). Modified src/telemetry/dashboard.py (DashboardData + 3 new render helpers + console summary + absence counter), src/telemetry/pricing.py (PricingTable.last_updated), src/telemetry/value.py (parse_subscription_fee date normalisation), scripts/telemetry/dashboard.py (NEW load_drift_inputs + wired detect_config_drift into assemble_dashboard_data), tests/test_telemetry.py (+26 tests), memory/bugs/regression-ledger.md (entry).
- **Developer-stated motivation**: The current cost figure silently re-prices old discussions at today's rates; unknown model ids are silently uncosted; the leverage denominator (subscription fee) is applied across captured spend that may predate the fee. Surface these provenance gaps as 'rows the gatekeeper can read alongside the existing A2 failures or as a sibling sub-panel' (handoff wording).
- **Explicit constraints**: NO push (autonomous authorization). NO modifications to .claude/settings.json. /review must run before commit. ADR-0020 honesty discipline carries forward: a drift kind that cannot be determined renders as honest absence, never a fabricated 'no-drift'. ADR-0013 compute-don't-store: drift detection is read-side; no DB mutation.

---

## Turn 2 — qa-specialist (proposal)
*2026-06-09T06:06:51.704269+00:00 | confidence: 0.88*
*tags: phase3-unit2, review, blocking:0, high:2, medium:3, low:3*

## qa-specialist findings (8) — APPROVE-WITH-CHANGES
F1 HIGH (missing edge case): all-NULL created_at column branch in load_drift_inputs is documented but never tested; detect_stale_subscription_drift has no symmetric no-corpus test (pricing path does). Add unit + integration coverage.
F2 HIGH (content defect): _render_config_drift_panel not_run absence tile says 'Run scripts/telemetry/analyze_cost.py' but analyze_cost.py does NOT populate discussions table — the user would loop. Should point at the actual capture path (ingest_token_usage.py or 'capture a session').
F3 MED (boundary): date() truncation is load-bearing but no explicit boundary-at-midnight test pins it.
F4 MED (helper hole): _pricing_with('') in tests doesn't insert empty-string key into YAML — silently exercises key-absent path. Add explicit empty-string test.
F5 MED (symmetry gap): no test for malformed subscription effective_date (pricing has one).
F6 LOW: no empty model_ids test (logic correct, just unpinned).
F7 LOW: no parse_subscription_fee date-scalar normalisation test (pricing has one).
F8 LOW: load_drift_inputs missing-table branch is not reachable from integration tests.
Strengths: symmetric-key test, double-assert XSS escape pattern, R3a true-zero pin, regression markers.

---

## Turn 3 — architecture-consultant (proposal)
*2026-06-09T06:07:00.369044+00:00 | confidence: 0.86*
*tags: phase3-unit2, review, blocking:0, high:0, medium:0, low:2, info:3*

## architecture-consultant findings (5) — APPROVE-WITH-CHANGES
F1 LOW (pattern inconsistency): load_drift_inputs(conn) takes open connection, load_weekly_trends(db_path, pricing) opens its own. Defensible but uncommented — risk that the next slice calls _connect_readonly directly thinking 'drift uses an open conn, I will too.' Add 1-2 line comment.
F2 LOW (duplication, Rule-of-Two): subscription YAML parsed TWICE in assemble_dashboard_data (once inside assemble_value_inputs, once via load_subscription_fee for drift). Acceptable at N=2 with inline comment pinning the Rule-of-Three trigger.
F3 INFO: failures-panel-mirror pattern (_group_*_by_* + _render_*_group + DRIFT_KINDS + REMEDIATION_HINTS) is duplicated structurally. Correctly NOT extracted at N=2; the regression-ledger entry already names the trigger. No action.
F4 INFO: YAML date-scalar normalisation duplicated at N=2 between pricing + value. Correctly inline; promote to helper on third occurrence.
F5 INFO: PricingTable.last_updated is pure additive (default ''); no deprecation needed.
ADR alignment: ADR-0013 + ADR-0020 + ADR-0016 all honored. drift.py is pure; transport seam is clean; no circular imports; sibling-panel choice was argued from data shape (textbook 'door-policy' move). Strong architectural shape.

---

## Turn 4 — ux-evaluator (proposal)
*2026-06-09T06:07:11.664700+00:00 | confidence: 0.88*
*tags: phase3-unit2, review, blocking:0, high:2, medium:2, low:2*

## ux-evaluator findings (6) — APPROVE-WITH-CHANGES
F1 HIGH (CONVERGENT with qa F2 — honest-absence violation): not_run absence tile says 'Run scripts/telemetry/analyze_cost.py after capturing a session' — analyze_cost.py is the WRONG action; it does not populate the discussions corpus. User would follow the hint and stay stuck. Fix: point at the actual capture flow (a session + ingest, not the analyzer).
F2 HIGH (missing orientation cue): sub-copy 'tells you how to read it' has no triage 'start there' pointer. Drift has no cost dimension so cannot copy the failures-panel 'most costly class' wording; need an alternative anchored in the UNKNOWN_MODEL→undercount logic.
F3 MED (jargon): 'hypothetical at today's prices' (STALE_PRICING) reads as 'unreliable' to a non-engineer; 'denominator' (STALE_SUBSCRIPTION_FEE) is math-speak — the gatekeeper profile (per user_education_perspective) struggles with that.
F4 MED (label opacity): kind.replace('_', ' ').capitalize() yields 'Unknown model' / 'Stale pricing' / 'Stale subscription fee' — adequate but misses 'name the consequence' opportunity. Static label map (mirrors _LANE_STATUS_LABEL / _RUNWAY_LABEL) would let each kind carry a manager-facing label: 'Unpriced model id' / 'Stale pricing config' / 'Stale subscription fee'.
F5 LOW: 'Config drift' title is engineer vocabulary; consider 'Config freshness' or 'Pricing config check'.
F6 LOW: 'Observed' column header is clinical; 'What was found' is plainer.
Strengths: not_run vs true-zero R3a distinction; no-cost-column decision is correctly the 'C4 anti-pattern' guard; canonical ordering + rationale documented in drift.py; XSS escape pinned with double-assert; layout consistency with failures panel.

---

## Turn 5 — facilitator (critique)
*2026-06-09T06:13:43.975742+00:00 | confidence: 0.8*
*tags: finding-verification*

Finding verification (Step 6.3): 19 verified, 0 inconclusive, 0 discarded. All findings reference real file:line locations or testable invariants. Convergent HIGH finding (qa F2 + ux F1 on the wrong action script in the absence tile) verified by direct read of analyze_cost.py + load_drift_inputs schema. Convergence is strong — same defect, two independent specialists, both correctly identified the C4-anti-pattern violation (the absence-tile copy ITSELF lied about what action would resolve the absence, which is exactly the kind of fabricated-state mismatch ADR-0020 forbids).

---

## Turn 6 — facilitator (synthesis)
*2026-06-09T06:14:17.833437+00:00 | confidence: 0.873*
*tags: phase3-unit2, blocking:0, advisory:14, speculative:0, model-tiers:qa:opus+arch:opus+ux:opus+fac:opus, verdict:approve-with-changes-then-approve-post-fold*

## Request Context
- **What was requested**: Phase 3 Unit 2 — config-drift rows (per SPEC-20260607-183136 §Phase 3 'failure intelligence'). Build a detector + render path surfacing configuration-drift signals between current pricing/subscription configs and the captured discussion window.
- **Files/scope**: NEW src/telemetry/drift.py + modified dashboard/pricing/value/transport + 33 new tests + regression-ledger entry.
- **Developer-stated motivation**: Current cost figure silently re-prices old discussions; unknown model ids silently uncosted; leverage denominator may post-date captured spend.
- **Explicit constraints**: NO push. ADR-0020 honesty + ADR-0013 compute-don't-store discipline. /review before commit.

## Verdict: APPROVE post-fold

Ensemble weighted confidence: qa 0.88 + arch 0.86 + ux 0.88 = **0.873**.
Pre-fold: 0 BLOCKING / 2 convergent HIGH + 2 HIGH + 4 MED + 5 LOW + 3 INFO.
Post-fold (this session): **0 BLOCKING / 0 HIGH / 0 MED / 0 LOW open**. 9 advisories folded in-session, 5 LOW deferred-as-advisory, 3 INFO confirmed-no-action.

## Folded in-session (9)
- **CONVERGENT HIGH (qa F2 + ux F1)**: not_run absence tile no longer points at analyze_cost.py (which reads but does not populate the discussions corpus); now points at the framework command pipeline. New regression test pins the fix.
- **HIGH (ux F2)**: data+signals sub-copy gained a 'first group has the most direct effect on the cost figure — start there' triage cue (replaces the prior 'tells you how to read it' dead end).
- **MED (ux F3)**: STALE_PRICING + STALE_SUBSCRIPTION_FEE hints rewritten without 'hypothetical' / 'denominator' jargon (manager-gatekeeper plain-language bar).
- **MED (ux F4)**: kind labels now come from a static _DRIFT_KIND_LABEL map ('Unpriced model id' / 'Stale pricing config' / 'Stale subscription fee') with fail-loud [kind] lookup, mirroring _LANE_STATUS_LABEL / _RUNWAY_LABEL precedent.
- **MED (qa F1A)**: detect_stale_subscription_drift_silent_when_no_corpus added (symmetric to the pricing test).
- **MED (qa F1B)**: COUNT(*) tiebreaker branch was dead code (discussions.created_at NOT NULL); simplified + new test pins the schema invariant so a future migration that drops NOT NULL fires the test.
- **MED (qa F5)**: detect_stale_subscription_drift_silent_when_effective_date_malformed added.
- **LOW (qa F4)**: explicit empty-string YAML test for PricingTable.last_updated.
- **LOW (qa F7)**: parse_subscription_fee date-scalar normalisation test (symmetric to pricing).
- **LOW (arch F1)**: load_drift_inputs docstring explains why it takes an open conn (composes inside assemble_dashboard_data) rather than wrapping _connect_readonly (the load_weekly_trends shape applies only when an external transport needs a read-side surface).
- **LOW (arch F2)**: Rule-of-Three trigger comment on the subscription fee double-load (acceptable at N=2; refactor on a third consumer).

## Deferred-as-advisory (5 LOW)
- qa F3 (date() truncation boundary tests at midnight UTC)
- qa F6 (empty model_ids list test — logic correct, just unpinned)
- qa F8 (direct unit tests for load_drift_inputs missing-table branch — currently covered only via integration)
- ux F5 ('Config drift' title rename — borderline jargon, sub-copy compensates adequately; defer unless user feedback)
- ux F6 ('Observed' column header rename — clinical but defensible)

## Confirmed-no-action (3 INFO)
- arch F3 (failures-panel mirror pattern — Rule-of-Three trigger correctly named in ledger entry for Unit 3)
- arch F4 (YAML date-scalar normalisation seam — promote to helper on third occurrence)
- arch F5 (PricingTable.last_updated additive contract — no deprecation needed)

## Model tiers
qa-specialist:opus, architecture-consultant:opus, ux-evaluator:opus, facilitator:opus (Phase 3 default panel; no --cost flag).

## Education gate recommendation
**Not needed**. The new module is a near-mirror of the Unit 1 failures.py pattern (which the developer already worked through in session 18); the design fork (sibling panel vs CONFIG-group) is documented in the ledger entry; the honesty disciplines are inherited contracts. Walkthrough/quiz would be redundant with the recent Unit 1 education.

Quality gate 7/7 (242+ telemetry tests; ledger 43 guards; ruff clean). Sibling-panel decision validated by data shape (ConfigDriftSignal vs FailureSignal mismatch + C4-anti-pattern concern); intentional duplication with failures.py correctly NOT extracted at N=2.

---
