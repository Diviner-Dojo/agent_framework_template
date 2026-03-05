---
discussion_id: DISC-20260303-143553-analyze-mhabit
started: 2026-03-03T14:44:40.292399+00:00
ended: 2026-03-03T14:45:00.855921+00:00
agents: [architecture-consultant, facilitator, independent-perspective, project-analyst, qa-specialist]
total_turns: 5
---

# Discussion: DISC-20260303-143553-analyze-mhabit

## Turn 1 — project-analyst (proposal)
*2026-03-03T14:44:40.292399+00:00 | confidence: 0.92*

Scout Report: mhabit/Table Habit (FriesI23) - 1,231 stars, Flutter/Dart, Apache-2.0. ~20,600 LOC, 444 Dart files, 22 test files. sqflite+Provider (not Drift/Riverpod). 6 notable patterns: NotificationService abstract interface with FakeNotificationService, whenNeeded data-anchored scheduling, injectable AppClock, segmented notification ID namespace, HabitExporter factory+strategy+mixin, per-channel AppNotifyConfig. Anti-patterns: singleton factory conflicts with Riverpod, sqflite raw SQL, FakeNotificationService never actually used in tests.

---

## Turn 2 — architecture-consultant (proposal)
*2026-03-03T14:44:43.932563+00:00 | confidence: 0.88*

Architecture review: 4 applicable patterns. (1) NotificationService abstract interface - adapt with Riverpod provider, discard singleton factory. (2) whenNeeded data-anchored scheduling - maps to 'no session today' trigger, materially different from Daily_You entry-existence guard (determines scheduling TIME vs just gating). (3) AppClock injectable - prerequisite for testing scheduling logic, 15 lines, no dependency needed. (4) HabitExporter factory+strategy+mixin - adapt to SessionExporter with Drift DAOs. Defer: per-channel AppNotifyConfig (over-engineered for 2 channels).

---

## Turn 3 — qa-specialist (proposal)
*2026-03-03T14:44:47.497987+00:00 | confidence: 0.85*

QA review: 3 applicable patterns. whenNeeded test suite has 7 exemplary test cases with fixed DateTimes covering the full decision tree (future lastUntrackDate, past with today not passed, past with today passed, null date, timezone crossover). Should be replicated exactly. FakeNotificationService needs adaptation: const no-op returns are insufficient for meaningful tests, add call recording. AppClock enables deterministic scheduling tests. Coverage gap: FakeNotificationService is never actually used as test double in mhabit's own tests.

---

## Turn 4 — independent-perspective (proposal)
*2026-03-03T14:44:50.410835+00:00 | confidence: 0.82*

Independent review: whenNeeded requires rescheduling trigger in session-logging flow (cancel reminder when session saved, reschedule at app startup). Singleton factory is highest-risk adoption mistake with Riverpod. Under-flagged pattern: l10n notification channel name update callback prevents stale channel names after language change. Pre-mortem: fixed-time reminder without whenNeeded leads to auto-disable after 3 dismissals (per ADHD spec), permanently losing the user. whenNeeded avoids this by only firing when there is actual unfinished work.

---

## Turn 5 — facilitator (synthesis)
*2026-03-03T14:45:00.855921+00:00 | confidence: 0.88*

## Request Context
Developer is building Phase 4D (non-escalating reminders) and Phase 2C (data export) of the ADHD-informed feature roadmap. mhabit was identified as complementary to Daily_You analysis — focuses on testable notification architecture and data-anchored scheduling.

## Synthesis
Three specialists reviewed mhabit (architecture-consultant, qa-specialist, independent-perspective). Strong consensus on 4 adopt patterns, 1 simplified adopt, 1 defer. Key differentiator from Daily_You: mhabit provides the testable notification SERVICE ARCHITECTURE while Daily_You provided the SCHEDULING ALGORITHM. Together they form a complete notification implementation blueprint. The whenNeeded pattern is materially different from Daily_You's entry-existence guard: it determines scheduling TIME based on data state, not just gating. Independent-perspective flagged critical pre-mortem: fixed-time reminders without whenNeeded lead to auto-disable after 3 dismissals, permanently losing ADHD users.

## Scoring Summary
- NotificationService abstract interface: 22/25 (adopt)
- whenNeeded data-anchored scheduling: 23/25 (adopt)
- Injectable AppClock: 21/25 (adopt)
- Segmented notification ID namespace: 19/25 (adopt simplified)
- HabitExporter factory+strategy+mixin: 21/25 (adopt adapted)
- Per-channel AppNotifyConfig: 16/25 (defer)

---
