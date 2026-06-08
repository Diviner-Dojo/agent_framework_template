---
discussion_id: DISC-20260608-034041-arch-f1-fold-uncosted-per-event-on-livecostevent
started: 2026-06-08T03:41:04.771572+00:00
ended: 2026-06-08T03:51:58.376663+00:00
agents: [architecture-consultant, facilitator, qa-specialist]
total_turns: 6
---

# Discussion: DISC-20260608-034041-arch-f1-fold-uncosted-per-event-on-livecostevent

## Turn 1 — facilitator (evidence)
*2026-06-08T03:41:04.771572+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Land the arch F1 fold (deferred-as-advisory from REV-20260608-025749) as a standalone slice. Originating advisory: `LiveCostEvent` carries no `uncosted` flag, so the chart panel collides priced-$0 turns with uncosted (unknown-tier) turns at `cost: 0.0` in the JSON payload. Fold per the prior REV's documented recipe: add `uncosted: bool` to `LiveCostEvent`, thread through `_apply_message`, include in `_ChartPoint` TypedDict + chart payload, add regression tests, update ledger.
- **Files/scope**: src/telemetry/live.py (LiveCostEvent + _apply_message constructor call), src/telemetry/dashboard.py (_ChartPoint TypedDict + docstring + chart payload list comprehension), tests/test_telemetry.py (strengthened set==4 field-shape test + 3 new regression tests), memory/bugs/regression-ledger.md (new entry #38→39).
- **Developer-stated motivation**: Land the arch F1 fold ahead of the CSP-blocked step 4 (Chart.js init script). The fold is independent of the CSP design fork (VENDORED-INIT vs EXTEND-CSP-HASH) and unblocks a cleaner scope for the next session. Developer is AFK; CSP question was re-asked via ntfy with plain-language framing and no reply within the polling window — autonomous decision to land the independent slice rather than ROLL with zero progress.
- **Explicit constraints**: Quality gate must pass (7/7 confirmed). No push. Stay on `fix/c-gate-log-integrity` feature branch. /review required before commit per autonomous_workflow rule. Do not weaken any existing guard (JSON-in-script, allow_nan, </script>-escape, WCAG, CSP) — this fold is purely additive (one new boolean field, one new key in the payload, three new regression tests, one strengthened existing test).

---

## Turn 2 — qa-specialist (proposal)
*2026-06-08T03:44:13.934316+00:00 | confidence: 0.88*
*tags: qa-specialist, medium:1, low:2*

## Test Adequacy
Three new regression tests are load-bearing: each fails under a distinct realistic regression path (constructor-call drop, default-required change, payload-key drop). Set==4 strengthening is correct symmetric guard. Two gaps: subagent uncosted has aggregate-level coverage but no per-event flag assertion on recent_events; failure-kind LiveCostEvent has no explicit default-False payload-filter guard.

## Findings

### Finding 1 — Subagent uncosted per-event flag has no direct test (MEDIUM)
Rule: testing edge-case coverage + branch-into-unified-code symmetry.
Location: tests/test_telemetry.py — test_subagent_lane_with_unknown_tier_model_is_uncosted (~line 2631)
Description: All three new tests fire on main lane. The _apply_message code forks at lane_id=='main' vs else branch. Both reach the same unified LiveCostEvent(...) call so propagation is symmetric today, but a future refactor that split the constructor call into the two branches could break the subagent path without triggering any new test. Existing subagent test only asserts state.uncosted_turns==1, not state.recent_events[-1].uncosted is True.
Recommendation: Extend test_subagent_lane_with_unknown_tier_model_is_uncosted (or sibling @pytest.mark.regression) to additionally assert state.recent_events[-1].uncosted is True.

### Finding 2 — Strengthened shape test exercises only False branch isinstance (LOW)
Rule: meaningful assertion completeness.
Location: tests/test_telemetry.py — test_render_per_turn_cost_chart_panel_json_payload_carries_t_cost_lane_id
Description: assert isinstance(entry['uncosted'], bool) currently runs only on False values. True branch is covered by the dedicated arch-F1 regression test. Advisory only — no gap in overall coverage.
Recommendation: Optional — adding one synthetic event with uncosted=True would make the shape test fully self-contained. Acceptable as-is.

### Finding 3 — Failure-kind uncosted=False has no explicit assertion (LOW)
Rule: edge-case documentation.
Location: tests/test_telemetry.py — test_live_cost_event_uncosted_defaults_to_false
Description: Default-False test uses kind='turn'. No test constructs kind='failure' to assert uncosted=False default. Non-risk because (a) default already enforces; (b) renderer filters failure events; (c) failure-filter regression test would catch leakage.
Recommendation: No action required. Optional one-line docstring note in the default test.

## Strengths
- Load-bearing test isolation: three new tests form interlocking chain (each catches what others miss)
- set==4 is the textbook negative guard for additive schema change
- LiveCostEvent.uncosted docstring is above-standard quality (semantic distinction + historical context + failure-event clause)
- _ChartPoint TypedDict + docstring meets cross-language boundary contract requirement
- Test symmetry through fold_events (real _price_message → real _apply_message → recent_events)
- Regression ledger entry #39 accurate and actionable (names failure mode + provides 'do not remove' invariant)

---

## Turn 3 — architecture-consultant (proposal)
*2026-06-08T03:44:31.475298+00:00 | confidence: 0.93*
*tags: architecture-consultant, low:1, info:1*

## Verdict
No structural concerns. Single source of uncosted truth maintained end-to-end (_price_message → local → LiveCostEvent → _ChartPoint), no premature abstraction, schema-evolution contract honored.

## Architectural Alignment
- ADR-0013 cost as single source of truth: HONORED. _price_message remains sole pricing oracle; (cost, uncosted) tuple is the seam; aggregate + per-event both read from same local.
- ADR-0020 telemetry honesty / uncosted ≠ $0: HONORED. Fold extends CostReport.is_fully_covered's discipline into live chart payload.
- R10 / AC14 purity seam: UNCHANGED. Plain bool field; no scripts.* import, no transcript IO, no YAML. replace(state, ...) preserves frozen-dataclass immutability.

## Findings

### Finding 1 — Aggregate-vs-per-event invariant is eventually-consistent (LOW)
Rule: Project Principle #1 (reasoning is the primary artifact) + _ChartPoint schema-evolution discipline.
Location: src/telemetry/live.py:233 (recent_events) and :236 (uncosted_turns).
Description: The invariant sum(1 for ev in state.recent_events if ev.kind=='turn' and ev.uncosted) == state.uncosted_turns holds ONLY while fewer than RECENT_EVENTS_CAP=100 turn events have been folded. After the rolling-window slice, per-event tally drifts below aggregate counter — by design, but not stated. A future consumer computing % partial coverage from recent_events will silently disagree with uncosted_turns once session exceeds 100 turns.
Recommendation: Add one sentence to LiveState.uncosted_turns docstring calling out session-cumulative vs rolling-window distinction.
Exceptions: Moot if dashboard never exposes a recent_events-derived per-event uncosted metric.
ADR Reference: ADR-0020 honest-absence discipline — quiet honesty cliff a future consumer could trip over.

### Finding 2 — Schema-evolution clause has unfulfilled forward obligation (INFO)
Rule: _ChartPoint docstring's own schema-evolution clause.
Location: src/telemetry/dashboard.py:898-901.
Description: The schema-evolution rule is load-bearing for safety of this fold, but the init script does not exist yet (Phase 2 step 4 CSP-blocked). The 'IFF' condition is therefore an unfulfilled forward obligation on the upcoming init script slice, not a property established by commit bd9798c. Vacuously satisfied today.
Recommendation: (a) Augment _ChartPoint docstring with parenthetical noting the Phase 2 init script MUST treat unknown fields as opaque (forward obligation), OR (b) accept this as captured by ledger entry #39. I lean (a) because the docstring is the single artifact a JS developer reads.
Exceptions: Closes naturally when init script lands and treats unknown fields opaquely.

## Premature-abstraction check (Principle #8): CLEAN. No _to_chart_point helper extracted — Rule of Three not crossed, inline list-comprehension is right shape today.

## Layer purity (AC14): CLEAN. No new imports; bool field requires nothing.

## Strengths
- Single source of truth preserved end-to-end (no second oracle, future maintainer cannot accidentally recompute uncosted from cost==0.0)
- Default False is the right additive shape (every existing synthetic construction site continues to pass)
- set==3 → set==4 strengthening is textbook additive-schema landing
- _ChartPoint docstring rewrite replaces 'known limitation' with statement of contract — correct way to retire deferred-as-advisory items
- Ledger entry #39 names the cross-layer obligation explicitly (tripwire that survives refactor)
- Door policy correct: closes the originating advisory's door without opening speculative ones. Fold is exactly the size of the problem.

---

## Turn 4 — facilitator (critique)
*2026-06-08T03:44:45.118178+00:00 | confidence: 0.8*
*tags: finding-verification*

Finding verification: 5 verified (qa F1 subagent test gap at tests/test_telemetry.py:2631 confirmed — test only asserts state.uncosted_turns==1, not state.recent_events[-1].uncosted; qa F2 shape-test bool isinstance only on False at tests/test_telemetry.py:3870; qa F3 failure-kind default unverified by current default-False test; arch F1 LiveState.uncosted_turns docstring at live.py:201-206 lacks rolling-window callout; arch F2 _ChartPoint schema-evolution clause at dashboard.py:898-901 has vacuous IFF given init script doesn't exist yet). 0 inconclusive, 0 discarded.

---

## Turn 5 — facilitator (synthesis)
*2026-06-08T03:50:36.994757+00:00 | confidence: 0.91*
*tags: blocking:0, advisory:5, speculative:0, folded:3, deferred:2, model-tiers:qa-specialist:sonnet+architecture-consultant:sonnet*

## Request Context
- **What was requested**: Land the arch F1 fold (deferred-as-advisory from REV-20260608-025749) as standalone slice — propagate per-event `uncosted` flag from `_price_message` through `LiveCostEvent` into the chart's `_ChartPoint` payload so the Phase 2 init script can render uncosted turns distinctly.
- **Files/scope**: src/telemetry/live.py + src/telemetry/dashboard.py + tests/test_telemetry.py + memory/bugs/regression-ledger.md.
- **Developer-stated motivation**: Independent of the CSP-blocked step 4 design fork; unblocks cleaner scope for next session.
- **Explicit constraints**: No push. Stay on fix/c-gate-log-integrity. Quality gate must pass. /review required before commit. Do not weaken existing guards.

## Verdict: APPROVE (post-fold)

0 BLOCKING / 1 MED folded / 1 LOW folded / 1 INFO folded / 2 LOW deferred-as-advisory (explicitly 'no action required' per qa-specialist).

## Ensemble
qa-specialist (sonnet, conf 0.88) + architecture-consultant (sonnet, conf 0.93); weighted avg 0.905. No security-specialist (JSON-in-script + allow_nan + </script>-escape seams unchanged, no new injection surface). No ux/perf (model + data-shape change, no user-facing copy or hot path).

## In-session folds (3)
- **qa F1 MED → fold**: Extended `test_subagent_lane_with_unknown_tier_model_is_uncosted` to additionally assert per-event `state.recent_events[-1].uncosted is True` for the non-main branch + promoted to `@pytest.mark.regression`. Closes the branch-symmetry gap (future refactor that split the unified constructor call into the two _apply_message branches could break subagent uncosted without triggering main-lane tests).
- **arch F1 LOW → fold**: Extended `LiveState.uncosted_turns` docstring with session-cumulative vs rolling-window distinction. Future consumer computing per-event uncosted ratio from `recent_events` will silently disagree with the aggregate once a session exceeds RECENT_EVENTS_CAP=100 — the doc fix is cheapest possible disambiguation.
- **arch F2 INFO → fold (option a)**: Extended `_ChartPoint` schema-evolution clause with explicit forward obligation on Phase 2 init script (MUST treat unknown fields as opaque). Docstring is the single artifact a JS developer reads; ledger entry is one indirection away.

## Deferred-as-advisory (2, both explicitly 'no action required')
- qa F2 LOW: strengthened shape test's `isinstance(uncosted, bool)` only exercises False branch in that test (True branch is covered by separate dedicated regression test — no overall gap).
- qa F3 LOW: failure-kind LiveCostEvent default=False has no explicit assertion (renderer filters failures + default-False already enforces; failure-filter regression test catches leakage).

## Confidence annotation
0 findings in speculative section (confidence < 0.80). 0 retained as unscored.

## Model tiers
qa-specialist:sonnet, architecture-consultant:sonnet (medium cost default routing).

## Strengths confirmed by both specialists
- Single source of truth preserved end-to-end (no second oracle; uncosted local from _price_message reaches both LiveCostEvent and _bump_totals' aggregate without recomputation)
- Default False is correct additive shape (no existing synthetic construction site breaks)
- set==4 strengthening is textbook negative guard for additive schema change
- Test interlocking chain: each of 3 new tests catches a regression the others would miss
- LiveCostEvent.uncosted docstring quality above standard (semantic distinction + historical context + failure-event clause)
- _ChartPoint schema-evolution rule is the right cross-language boundary invariant
- Premature-abstraction check: CLEAN (no _to_chart_point helper; Rule of Three not crossed)
- Layer purity (AC14): CLEAN (no scripts.* import, no transcript IO, plain bool)
- Door policy: correct (closes the originating advisory, opens no speculative doors; fold exactly the size of the problem)

---

## Turn 6 — facilitator (evidence)
*2026-06-08T03:51:58.376663+00:00 | confidence: 0.8*
*tags: reflection-deferred*

Reflection step deferred for this slice (autonomous-session budget husbandry). 0-BLOCKING fold-review with all actionable advisories folded in-session — reflection yield expected to be low. Tracked as known-gap; may be picked up in retro.

---
