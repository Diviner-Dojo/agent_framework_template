---
discussion_id: DISC-20260305-144939-advisory-triage-sprint-a4-3a-4e
started: 2026-03-05T14:51:05.445004+00:00
ended: 2026-03-05T14:59:31.265018+00:00
agents: [architecture-consultant, facilitator, qa-specialist]
total_turns: 4
---

# Discussion: DISC-20260305-144939-advisory-triage-sprint-a4-3a-4e

## Turn 1 — facilitator (evidence)
*2026-03-05T14:51:05.445004+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Advisory triage sprint — fix A-4 (SCHEDULE_EXACT_ALARM silent failure loop), plus selected Phase 3A and Phase 4E advisories from REV-20260304-085452, REV-20260304-142456, REV-20260304-145506, REV-20260304-015709. Exclude cosmetic and architectural-migration advisories.
- **Files/scope**: notification_scheduler_service.dart, notification_providers.dart, session_list_screen.dart, journal_session_screen.dart, check_in_history_screen.dart, and their test files; ADR-0033 note.
- **Developer-stated motivation**: ADHD roadmap spec is fully shipped; reduce tech debt before planning Phase 5. A-4 elevated to important (silent failure loop on every cold start after SCHEDULE_EXACT_ALARM revoked).
- **Explicit constraints**: No new features. No CPP exposure (no provider default changes). Quality gate >=80% coverage. Exclude StateNotifier→Notifier<T> migration and cosmetic changes.

---

## Turn 2 — qa-specialist (critique)
*2026-03-05T14:57:22.757478+00:00 | confidence: 0.87*
*tags: spec-review, qa*

## QA Specialist Review — SPEC-20260305-144939

### Findings

**F1 (High) — Missing test for PlatformException catch path**: The A-4 fix adds an on PlatformException catch in rescheduleFromTasks, but no Group 2 test covers this path. Group 2 A2 tests the !_initialized early-return, not the exception path. Need a test that injects a mock plugin whose zonedSchedule throws PlatformException, passes a task with stale notificationId, and asserts the DAO nullifies the column. Without this, the fix is untestable and invisible to regression.

**F2 (High) — A2 test description is wrong**: Calling rescheduleFromTasks([]) on uninitialized service tests tasks.isEmpty, not !_initialized. Revise: pass [someTask] to uninitialized service to exercise the correct branch.

**F3 (Medium) — deleteTasksBySession test**: Use _FakeScheduler daoWithScheduler pattern. Assert cancelledIds containsAll([1042, 1099]) and hasLength(2) for a session with two tasks with known IDs.

**F4 (Medium) — viewPadding.bottom change has no test**: Add a code comment explaining why padding.bottom (not viewPadding.bottom) is correct with resizeToAvoidBottomInset:true. Add regression-ledger entry.

**F5 (Medium) — capturePhotoDescription non-paused test**: Must set orchestrator in continuous mode, assert sttService.isListening==true after call returns. FakeSttService.isListening is sufficient.

**F6 (Medium) — pulse_check_in dispatch test scope**: Existing palette test already pins the return value. New test should pump SessionListScreen in full MaterialApp with onGenerateRoute, simulate Check-In tile tap, assert navigator pushes /check_in. Navigation is the missing piece, not the palette return value.

**F7 (Low) — hasMissingDataWarning test belongs in correlation_service_test.dart**: Pure logic test — no UI needed. Assert hasMissingDataWarning:true AND insights.isNotEmpty for pairedCount:7, r:0.75, totalDays:14.

**F8 (Low) — setMode ordering no test**: Timing makes widget-layer test impractical. Add comment referencing REV-142456-A2 explaining ordering is intentional.

**F9 (Low) — Correlation empty state wording must be clinically safe**: New wording must not reference days elapsed, gap frequency, or missed sessions. 'Correlations appear after 5 or more days with data for the same dimensions.' is safe. Avoid 'you haven't done enough check-ins' patterns.

### Edge Cases
- Past-due tasks with stale notificationId not cleared by A-4 fix (pre-existing gap, separate from this sprint)
- taskDao optional parameter: if caller does not pass it, PlatformException catch cannot nullify stale ID — document clearly
- maxLines:4 regression test may assert exactly 6 — verify compatibility
- Y-axis subtitle reservedSize interaction on small screens

### Verdict: APPROVE with two blocking recommendations (F1: add PlatformException test; F2: fix A2 test description)

---

## Turn 3 — architecture-consultant (critique)
*2026-03-05T14:57:35.454382+00:00 | confidence: 0.89*
*tags: spec-review, architecture*

## Architecture Consultant Review — SPEC-20260305-144939

### Findings

**F1 (Medium) — taskDao injection approach breaks service-layer boundary**: Passing taskDao as optional parameter to rescheduleFromTasks() creates a write path from the service layer into the DAO layer. The existing contract is clean: service returns (taskId, newNotificationId) pairs, provider persists them. Introducing a silent side-effect (nullify stale ID inside the service) contradicts the established pattern and deepens ADR-0033-A7 bidirectional coupling.

Recommended alternative: catch PlatformException in rescheduleFromTasks, return failed taskIds alongside successful ones in a result record:
  ({List<({String taskId, int newNotificationId})> rescheduled, List<String> failedTaskIds})
Then notificationBootRestoreProvider iterates failedTaskIds calling taskDao.updateNotificationId(taskId, null). Service stays pure (no DAO dependency); provider owns persistence. This is a non-blocking advisory.

**F2 (Low) — setMode ordering fix approved**: Reordering is a correct UX fix aligned with context.mounted guard convention throughout the codebase. No architectural concern.

**F3 (Low) — viewPadding.bottom fix approved**: Correct and well-understood. Verify during emulator smoke test.

**F4 (Info) — ADR-0033 note**: Should reflect whichever approach is used. If return-value approach adopted, note that bidirectional coupling is limited to import of Task model type; service does not mutate database.

**F5 (Info) — _normalizeValue exclusion appropriate**: Screen-level 0.0 vs service-level 0.5 for degenerate scale is a design decision, not a quick fix. Exclusion correct.

**F6 (Info) — maxLines regression test**: Verify existing test asserts maxLines is non-null rather than exactly 6. Compatible with change to 4.

### Exclusions Assessment
All exclusions appropriate: StateNotifier migration (cross-cutting refactor), DraggableScrollableSheet (disproportionate), _shortLabel consolidation (design decision needed), correlation threshold (clinical implications, needs deliberation).

### Strengths
- A-4 elevation from Low to priority is correct — silent failure loop compounding on every cold start.
- Grouping strategy is well-structured for incremental commits.
- No CPP exposure (no provider default changes).
- context.mounted fix and padding.bottom fix are well-understood low-risk corrections.

### Verdict: APPROVE with advisory recommendation (F1: prefer return-value approach to preserve service boundary)

---

## Turn 4 — facilitator (synthesis)
*2026-03-05T14:59:31.265018+00:00 | confidence: 0.89*

## Request Context
- **What was requested**: Advisory triage sprint — fix A-4 (SCHEDULE_EXACT_ALARM silent failure loop) + selected Phase 3A and Phase 4E advisories from four prior reviews. Exclude cosmetic and architectural-migration items.
- **Files/scope**: notification_scheduler_service.dart, notification_providers.dart, session_list_screen.dart, journal_session_screen.dart, check_in_history_screen.dart and test files; ADR-0033 note.
- **Developer-stated motivation**: ADHD roadmap fully shipped. Reduce tech debt before Phase 5 planning. A-4 elevated to important (silent failure loop on every cold start after SCHEDULE_EXACT_ALARM revoked).
- **Explicit constraints**: No new features. No CPP exposure. Quality gate >=80%. Exclude StateNotifier→Notifier migration and cosmetic changes.

## Synthesis

Both specialists approved with recommendations. Two high-severity QA findings and one medium-severity architecture finding resolved by spec revision.

### Blocking-equivalent findings addressed in spec revision

**[QA-F1] PlatformException test missing**: The A-4 fix had no test for the actual catch path. Added as spec Group 2 item 8: mock plugin throws PlatformException, assert failedTaskIds populated. Without this test the fix was unverifiable.

**[QA-F2] A2 test description wrong**: 'Uninitialized + empty list' tested tasks.isEmpty, not !_initialized. Revised to pass non-empty task list to uninitialized service.

**[ARCH-F1] Service-layer boundary violation**: Optional taskDao parameter to rescheduleFromTasks would create a service→DAO write path contradicting the existing return-value contract. Revised to return-value approach:
  ({List<({String taskId, int newNotificationId})> rescheduled, List<String> failedTaskIds})
  Provider iterates failedTaskIds calling updateNotificationId(id, null). Service stays pure.

### Advisory findings (no spec change needed)

- [QA-F4] viewPadding fix: add inline comment + regression-ledger entry (incorporated into spec item 11)
- [QA-F6] pulse_check_in test: clarified in spec — test navigation (/check_in route push), not palette return value
- [QA-F7] hasMissingDataWarning test: moved to correlation_service_test.dart (pure logic, no UI)
- [QA-F8] setMode ordering: comment in code referencing REV-142456-A2 (test not feasible at widget layer)
- [QA-F9] Correlation empty state wording: confirmed safe — no gap-shaming language
- [ARCH-F6] maxLines regression test: verify existing test asserts non-null, not exactly 6

### Spec status after revision: REVIEWED
19 implementation items across 5 groups, 10 test assertions, 11 files. Education gate: deferred per CLAUDE.md ADHD roadmap autonomous execution authorization.

---
