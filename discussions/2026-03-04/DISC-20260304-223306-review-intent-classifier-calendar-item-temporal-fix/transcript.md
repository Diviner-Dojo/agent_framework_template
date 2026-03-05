---
discussion_id: DISC-20260304-223306-review-intent-classifier-calendar-item-temporal-fix
started: 2026-03-04T22:33:24.147620+00:00
ended: 2026-03-04T22:39:23.064328+00:00
agents: [facilitator, independent-perspective, qa-specialist]
total_turns: 6
---

# Discussion: DISC-20260304-223306-review-intent-classifier-calendar-item-temporal-fix

## Turn 1 — facilitator (evidence)
*2026-03-04T22:33:24.147620+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Fix intent classifier to be more flexible/permissive for natural language calendar intent — specifically 'I need to set a calendar item for Friday night with Shawn' was routed as journal instead of calendarEvent. Also add support for bare weekday+time-of-day temporal references ('friday night', 'saturday morning').
- **Files/scope**: lib/services/intent_classifier.dart, test/services/intent_classifier_test.dart, memory/bugs/regression-ledger.md
- **Developer-stated motivation**: Device testing revealed natural language phrases like 'I need to set a calendar item' and 'for Friday night' were not recognized as scheduling intent. User wants more permissive/flexible NL recognition.
- **Explicit constraints**: Must not break existing keyword+filter search. No false positives on journaling sentences like 'I had a meeting last week'. Regression tests required.

---

## Turn 2 — qa-specialist (proposal)
*2026-03-04T22:37:08.669903+00:00 | confidence: 0.82*
*tags: qa, coverage, false-positive*

## QA Analysis — Intent Classifier Calendar/Temporal Fix

**Confidence**: 0.82

### Coverage Assessment
Five new positive tests cover three of the four distinct pattern additions. One existing negative test guards the past-temporal path. Several untested branches identified.

**Tested paths:**
- \ compound pattern fires via primary regression test
- \ via friday night/friday evening tests
- \ via 'set a meeting for this Friday'
- \ via 'add a dinner for Friday evening' and primary regression test
- \ fires 
### Findings

**F1 — Medium** (resolved in-review): Test 'I want to create a calendar entry for Saturday morning' does not isolate the \ compound pattern — also matches \ which alone reaches threshold. Added 'I need to set a calendar entry for next Monday' to isolate the compound noun arm.

**F2 — Medium** (resolved in-review): \ added to \ had no test. Added 'I need to make a reservation for Saturday night' (positive) and 'I need to make a note about this Friday' (false-positive guard).

**F3 — Low**: \ newly added to \ (was only in \). Temporal-boost branch for this pattern is not exercised. Advisory: add 'schedule a meeting on Monday' test to confirm combined 0.75 confidence.

**F4 — Low**: No negative test for past-narrative sentences with 'on friday'. 'I was so nervous about the meeting on Friday' — event noun + \ in \ scores +0.4 calendar. Advisory: add this test and verify behavior.

**F5 — Low** (resolved in-review): Negative test used \ — tightened to \.

### Strengths
- \ correctly applied to primary regression test
- Regression ledger entry documents all three root causes with fix descriptions
- Test comment block at lines 501-509 precisely describes each gap fixed
- Existing false-positive guard infrastructure (gym/doc false positive tests) is consistent with this PR's approach
- 59-test suite with 7/7 quality gate

---

## Turn 3 — independent-perspective (proposal)
*2026-03-04T22:37:30.036149+00:00 | confidence: 0.82*
*tags: false-positive, adhd-ux, architecture*

## Independent Analysis — Intent Classifier Calendar/Temporal Fix

**Confidence**: 0.82

### Hidden Assumptions Identified

1. 'calendar item' is always scheduling intent — false. Appears in past-narrative naturally.
2. Temporal and scheduling signals are additive, not canceling — past-temporal compounds instead of neutralizing the calendar score.
3. Confirmation gate backstops all false positives — load-bearing assumption that may erode UX over time.
4. 'set' and 'make' in _hasFutureActionContext are narrow enough — bounded by modal prefix but still broad.
5. 'this (weekday)' is always future-referring — not true after the referenced day has passed.

### Critical False-Positive Scenarios

**Scenario 1 (Blocking)**: 'I remember we had a calendar item last week' — calendarScore=0.5 from compound noun pattern (no verb guard), then temporal boost adds 0.25, reaching 0.75 calendar confidence. This is a recall, not scheduling. The pattern needs a verb proximity or temporal-preposition anchor.

**Scenario 2 (Advisory)**: 'I need to set expectations' — 'need to set' fires _hasFutureActionContext, temporal boost applies if weekday present. With an event noun also present ('appointment'), this could misroute.

**Scenario 3 (Advisory)**: 'I worked friday night' — 'friday night' now in _temporalPattern. Without calendar/task signals, this flows to narrative +0.05 queryScore. Safe in isolation but compounding factor.

**Scenario 4 (Architectural)**: Confirmation gate UX erosion — active journaling users seeing repeated false-positive calendar prompts may develop prompt blindness, causing them to dismiss genuine scheduling intents.

### Alternatives Proposed

**Alternative 1 (Adopted in-review)**: Require scheduling-verb proximity OR future-temporal preposition anchor for calendar-item compound pattern:
- Arm 1: '(schedule|book|set up|add|create|plan|set|make|put) [0-40 chars] calendar (item|entry)'
- Arm 2: 'calendar (item|entry) [0-40 chars] (for|on|this|next|tomorrow)'

**Alternative 2 (Advisory)**: Separate _futureTemporalPattern from _temporalPattern architecturally — keep _temporalPattern conservative for the general temporal boost, let _futureTemporalPattern be the permissive superset only for the eventNoun guard.

### Post-Fix Assessment
With the verb-anchor fix applied (B1 resolved in-review):
- 'I remember we had a calendar item last week' — arm 1 has no scheduling verb, arm 2 has 'last week' not a future preposition. Correctly stays as journal.
- 'The calendar entry got deleted' — neither arm matches. Correctly stays as journal.
- Primary target phrase — arm 1 fires ('set ... calendar item'). Correctly routes as calendarEvent.

The fix is sound. Residual risk is in the _hasFutureActionContext expansion ('set'/'make' verbs) which is bounded by the modal prefix requirement and tested by two new false-positive guard tests.

---

## Turn 4 — facilitator (synthesis)
*2026-03-04T22:37:46.294032+00:00 | confidence: 0.91*
*tags: blocking:1, advisory:3*

## Request Context
- **What was requested**: Fix intent classifier for natural language calendar intent — 'I need to set a calendar item for Friday night with Shawn' was routed as journal. Also add bare weekday+time-of-day temporal references.
- **Files/scope**: lib/services/intent_classifier.dart, test/services/intent_classifier_test.dart, memory/bugs/regression-ledger.md
- **Developer-stated motivation**: Device testing showed 'calendar item' and 'Friday night' phrases not recognized as scheduling intent.
- **Explicit constraints**: No false positives on journaling sentences. Regression tests required.

## Verdict: approve-with-changes

1 blocking finding resolved in-review. 3 advisory findings remain open.

### B1 — calendar item pattern too broad without verb guard (resolved in-review)
The original pattern matched ANY sentence containing 'calendar item/entry' (e.g., 'I remember we had a calendar item last week' scored 0.75 calendar). Fixed by requiring a scheduling-verb anchor (preceding) OR a future-temporal preposition (following) — two-arm pattern. False-positive guard tests added for 'I remember we had a calendar item last week' and 'The calendar entry got deleted'.

### Advisory Findings

A1 (Low): 'on (weekday)' newly added to _temporalPattern but temporal-boost branch not exercised by any test. Add 'schedule a meeting on Monday' to confirm 0.75 confidence from combined paths.

A2 (Low): No explicit test for 'I was so nervous about the meeting on Friday' — event noun + 'on friday' in _futureTemporalPattern scores +0.4 calendar. Should be documented as accepted behavior or guarded.

A3 (Low/Architecture): Confirmation gate is load-bearing for remaining false-positive territory. As intent classifier grows more permissive, UX disruption risk for ADHD journaling users increases. Consider tracking calendar-prompt dismissal rate to detect false-positive drift.

### Strengths
- Verb-proximity dual-arm pattern for 'calendar item/entry' is clean and precise — zero false positives in all tested scenarios
- 59-test suite with comprehensive positive + negative coverage
- Regression ledger documents all three root causes with fix descriptions
- Temporal additions are correctly scoped to future-only context (futureTemporalPattern guard preserved)
- 7/7 quality gate passes

---

## Turn 5 — qa-specialist (reflection)
*2026-03-04T22:39:16.518416+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed
For each regex arm added to a scoring branch, I should verify a test isolates that arm's contribution to the final score — not just verify the end-to-end target phrase. Also did not check whether 'this (weekday)' could refer to a past day-of-week. Combined-path tests alone do not confirm that the new arm fires versus a pre-existing arm carrying the score.

## Candidate Improvement Rule
When a regex pattern is added to a branch that modifies a composite score (temporal boost, event-noun guard, etc.), at least one test must isolate that specific arm's contribution — not just verify the end-to-end target phrase.

## Confidence Calibration
Original: 0.82, Revised: 0.85, Delta: +0.03

---

## Turn 6 — independent-perspective (reflection)
*2026-03-04T22:39:23.064328+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed
The 'on (weekday)' overlap between _temporalPattern and _futureTemporalPattern deserved sharper scrutiny. Adding it to _temporalPattern means it can fire the temporal boost across all five branches of the conditional, not just the calendar path. A sentence like 'I was talking on Monday about the budget' now picks up a minimal query score. The scoring-path implication — that _hasFutureActionContext becomes load-bearing for correctness — was not fully traced. Next time: map every new pattern addition through all five branches of the temporal-boost conditional.

## Candidate Improvement Rule
Regex Temporal Coverage Rule: When a pattern is added to a shared temporal disambiguation bucket, the review must include a branch-coverage trace showing which of the five temporal-boost branches the new token can reach, with a representative test for each reachable branch. A pattern with no test for a reachable branch is blocking, not advisory.

## Confidence Calibration
Original: 0.91, Revised: 0.83, Delta: -0.08

---
