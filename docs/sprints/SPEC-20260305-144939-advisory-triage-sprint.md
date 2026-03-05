---
spec_id: SPEC-20260305-144939
title: "Advisory Triage Sprint — A-4 + Phase 3A + Phase 4E"
status: reviewed
risk_level: medium
discussion_id: DISC-20260305-144939-advisory-triage-sprint-a4-3a-4e
reviewed_by: [qa-specialist, architecture-consultant]
---

## Goal

Resolve the highest-value open advisories from three review batches:
REV-20260304-085452 (notification), REV-20260304-142456 + REV-20260304-145506
(Phase 3A/bug-fix sprint), and REV-20260304-015709 (Phase 4E trend view).

Priority filter: correctness bugs > test coverage gaps > clear UX wins.
Excluded: cosmetic copy changes, architectural migrations (StateNotifier→Notifier<T>),
and changes requiring new deliberation (correlation threshold, _shortLabel consolidation).

---

## Context

All four source review reports are post-ship advisories. No new features are introduced.
The ADHD roadmap spec is fully shipped; this sprint reduces technical debt before
planning Phase 5.

Elevated priority: A-4 (SCHEDULE_EXACT_ALARM revocation) is tagged "important" in
BUILD_STATUS.md — it creates a silent failure loop on every cold start after the OS
revokes the exact-alarm permission, and the stale `notificationId` is never cleared.

---

## Requirements

### Group 1 — A-4: SCHEDULE_EXACT_ALARM Silent Failure Loop (Correctness)

**Source**: REV-20260304-085452 advisory A6 (elevated to "important" in BUILD_STATUS.md)
**Spec revision**: Architecture-consultant (F1) recommended return-value approach to preserve service-layer boundary.

1. In `rescheduleFromTasks()`, add `on PlatformException` catch to the existing
   try/catch block. Instead of injecting TaskDao into the service, **return a
   result record** with both successful reschedules and failed task IDs:
   ```dart
   Future<({
     List<({String taskId, int newNotificationId})> rescheduled,
     List<String> failedTaskIds,
   })> rescheduleFromTasks(List<Task> tasks) async { ... }
   ```
   The catch block appends `task.taskId` to `failedTaskIds`.
2. Update `notificationBootRestoreProvider` (in `notification_providers.dart`) to
   iterate `result.failedTaskIds` and call
   `taskDao.updateNotificationId(taskId, null)` for each — provider owns DB writes.
   The existing `rescheduleAndPersist` loop already calls `updateNotificationId`
   for successful tasks; failed task IDs follow the same pattern symmetrically.
3. Document in ADR-0033: `SCHEDULE_EXACT_ALARM` revocation handled gracefully;
   failed-reschedule IDs returned to caller; service does not mutate database (the
   `Task` import coupling is intentional, but limited to model type only).
4. Add a unit test: mock plugin whose `zonedSchedule` throws `PlatformException`,
   task with stale `notificationId`, call `rescheduleFromTasks`, assert
   `failedTaskIds` contains the task ID and `rescheduled` is empty.

### Group 2 — Notification Test Coverage (Tests)

**Source**: REV-20260304-085452 A1, A2, A4
**Spec revision**: QA-specialist (F1, F2) corrected A2 test description and added PlatformException test.

5. **A1**: Add test using `_FakeScheduler` / `daoWithScheduler` pattern. Insert a
   session with two tasks with known `notificationId` values (e.g., 1042, 1099).
   Call `deleteTasksBySession(sessionId)`. Assert
   `fakeScheduler.cancelledIds` `containsAll([1042, 1099])` AND `hasLength(2)`.
6. **A2**: Construct `NotificationSchedulerService` without calling `initialize()`,
   call `rescheduleFromTasks([aTaskWithReminderTime])` (NON-empty list — tests
   `!_initialized` branch, not `tasks.isEmpty`). Assert result contains empty
   `rescheduled` and empty `failedTaskIds`.
7. **A4**: Add test with `status: TaskStatus.pendingCreate` verifying the task
   appears in `getTasksWithPendingReminders` results (confirms `isNotIn([completed])`
   logic includes `pendingCreate`).
8. **PlatformException test** (new — QA-specialist F1): Pass a mock plugin whose
   `zonedSchedule` throws `PlatformException`. Call `rescheduleFromTasks([task])`.
   Assert `result.failedTaskIds` contains `task.taskId` and `result.rescheduled`
   is empty.

### Group 3 — Phase 3A Correctness + UX (session_list_screen + journal_session_screen)

**Source**: REV-20260304-142456 A2; REV-20260304-145506 A1, A2, A5, A6, A8

8. **REV-142456-A2**: In `_openQuickCapturePalette`, move `setMode(modeName)` call
   to AFTER the second `context.mounted` check (currently it persists the mode
   even when the user abandons the palette without navigating anywhere).
9. **REV-145506-A5**: In `journal_session_screen.dart`, change the text input field
   from `maxLines: 6` to `minLines: 1, maxLines: 4` to prevent consuming too much
   screen space on 360dp devices with voice controls active.
10. **REV-145506-A6**: Add `textInputAction: TextInputAction.send` to the text input
    field so the keyboard Enter key submits the message (multi-line mode changes
    default to newline).
11. **REV-145506-A8**: Replace `MediaQuery.of(context).viewPadding.bottom` with
    `MediaQuery.of(context).padding.bottom` in the input container to prevent
    double-counting the bottom inset when keyboard is visible. Add an inline
    comment explaining why (`viewPadding` does not collapse when keyboard opens;
    `padding` does, which is correct when `resizeToAvoidBottomInset: true`).
    Add entry to `memory/bugs/regression-ledger.md`.

### Group 4 — Phase 3A Test Coverage

12. **REV-145506-A1**: Add test for `capturePhotoDescription` non-paused continuous
    case. Set orchestrator in continuous mode via `startContinuousMode()` (do NOT
    call `pause()` before). Call `capturePhotoDescription()`. Assert
    `sttService.isListening == true` after return — confirms path 2 (wasInContinuousMode
    && previousPhase != idle) calls `_startListening()`.
13. **REV-145506-A2**: Pump `SessionListScreen` in full `MaterialApp` with
    `onGenerateRoute`. Simulate Check-In tile tap in the palette. Assert the
    navigator pushes `/check_in` route. (The palette return value is already pinned
    by existing `quick_capture_palette_test.dart` — this tests the navigation
    dispatch, which is the missing piece.)

### Group 5 — Phase 4E UX + Test (check_in_history_screen + test)

**Source**: REV-20260304-015709 A1, A3, A4, A5, A7, A8

14. **A1**: Add subtitle `'Values normalized to 0–1 (1 = highest recorded)'` below
    the "Rolling averages" section header in `_buildRollingSection`.
15. **A3**: Remove `r = x.xx` from correlation tile subtitle. Keep the strength label
    and direction + paired-count in days.
16. **A4**: Update correlation empty state text:
    `'Not enough shared check-in days to compute correlations yet.'`
    → `'Correlations appear after 5 or more days with data for the same dimensions.'`
17. **A5**: Remove `tapTargetSize: MaterialTapTargetSize.shrinkWrap` from
    `SegmentedButton.styleFrom` in the history tab (restores 48dp minimum).
18. **A7**: Add a comment in `_CheckInTrendTab` explaining that screen-level
    `_normalizeValue` returns 0.0 for degenerate range (scaleMin == scaleMax)
    while `CorrelationService.normalizeAnswer` returns 0.5 — intentionally
    different (screen-side avoids chart point at midpoint for degenerate data).
19. **A8**: Add test to `test/services/correlation_service_test.dart` (pure logic,
    no UI needed). In the `generateInsights` group: `pairedCount: 7, r: 0.75,
    totalDays: 14` → assert `hasMissingDataWarning: true` AND
    `insights.isNotEmpty` (narrative card present — guards against degenerate pass
    if method returns low-data sentinel instead).

---

## Affected Components

| File | Changes |
|------|---------|
| `lib/services/notification_scheduler_service.dart` | `rescheduleFromTasks`: catch PlatformException, nullify stale ID |
| `lib/providers/notification_providers.dart` | Pass `taskDao` to `rescheduleFromTasks` |
| `lib/ui/screens/session_list_screen.dart` | setMode ordering (A2), padding.bottom (A8) |
| `lib/ui/screens/journal_session_screen.dart` | minLines/maxLines (A5), textInputAction (A6) |
| `lib/ui/screens/check_in_history_screen.dart` | Y-axis subtitle (A1), r-value removal (A3), empty state (A4), shrinkWrap (A5), _normalizeValue comment (A7) |
| `test/database/task_dao_test.dart` | deleteTasksBySession cancel test (A1), pendingCreate test (A4) |
| `test/services/notification_scheduler_service_test.dart` | !_initialized early-return test (A2) |
| `test/services/voice_session_orchestrator_test.dart` | capturePhotoDescription non-paused test (A1) |
| `test/ui/session_list_screen_test.dart` | pulse_check_in dispatch test (A2) |
| `test/ui/check_in_history_screen_test.dart` | hasMissingDataWarning test (A8) |
| `docs/adr/ADR-0033-scheduled-local-notifications.md` | Note on PlatformException + coupling intent |

---

## Acceptance Criteria

- [ ] `SCHEDULE_EXACT_ALARM` revocation: `PlatformException` caught in `rescheduleFromTasks()`, failed task IDs returned to provider, stale `notificationId` nullified in DB by provider — no silent failure loop on next cold start
- [ ] `deleteTasksBySession` cancellation wiring test passes (two-task session, cancelledIds containsAll + hasLength)
- [ ] `rescheduleFromTasks` `!_initialized` early-return test passes (non-empty task list, uninitialized service)
- [ ] `PENDING_CREATE` inclusion in `getTasksWithPendingReminders` test passes
- [ ] `PlatformException` path test passes (mock plugin throws, failedTaskIds populated, rescheduled empty)
- [ ] `setMode` not persisted for abandoned palette navigation
- [ ] Text input: `minLines: 1, maxLines: 4, textInputAction: TextInputAction.send` — keyboard Enter submits message
- [ ] Input container uses `padding.bottom` not `viewPadding.bottom` — no double-counting when keyboard opens
- [ ] `capturePhotoDescription` non-paused branch test passes
- [ ] `pulse_check_in` dispatch test pushes `/check_in` route
- [ ] Rolling averages chart has Y-axis subtitle
- [ ] Correlation tile subtitle has no raw r-value
- [ ] Correlation empty state uses actionable threshold wording
- [ ] SegmentedButton 48dp tap target restored (shrinkWrap removed)
- [ ] `_normalizeValue` vs `normalizeAnswer` asymmetry documented in comment
- [ ] `hasMissingDataWarning` boundary test passes
- [ ] `flutter test` all pass, coverage ≥ 80%
- [ ] `dart analyze` zero errors

---

## Risk Assessment

- **Low risk**: All changes address documented, reviewed issues. No new features.
- **Medium risk (A-4)**: `rescheduleFromTasks` return type change (record with `rescheduled`
  + `failedTaskIds`). The `notificationBootRestoreProvider` is the only production caller
  — must update to destructure the result and call `updateNotificationId(id, null)` for
  failed IDs. All tests using the old return type must be updated.
- **Low risk (UX)**: Text input changes are well-scoped to `journal_session_screen.dart`.
  `textInputAction.send` interacts with the existing `onSubmitted` callback — verify
  it fires correctly with the existing send logic.
- **No CPP exposure**: No provider defaults change. No capability status changes.

## Dependencies

- ADR-0033 (scheduled notifications) — needs a note added, not restructured
- `TaskDao.updateNotificationId` already exists (PR #80 implementation)
- No new dependencies

## Exclusions (Documented)

| Advisory | Reason excluded |
|----------|----------------|
| REV-085452 A3, A5, A7, A8 | Comment-only changes; low sprint value |
| REV-142456 A4 | Cosmetic copy change |
| REV-142456 A5 | Single attribute (barrierLabel); deferred to accessibility sprint |
| REV-142456 A6 | DraggableScrollableSheet — architectural change disproportionate to risk |
| REV-142456 A7 | excludeSemantics low; deferred to accessibility sprint |
| REV-142456 A8 | StateNotifier→Notifier<T> migration — architectural; needs dedicated sprint |
| REV-142456 A10 | Removed journaling modes ADR — documentation; deferred |
| REV-142456 A11 | Mode key constants — low value |
| REV-145506 A3 | Timing assertion comment; very low value |
| REV-145506 A4 | Silence timeout path — acknowledge as known gap |
| REV-145506 A7 | FAB visual dim — low; Semantics label already present |
| REV-015709 A2 | hasSufficientData gate UX — more complex than sprint scope |
| REV-015709 A6 | _shortLabel consolidation — refactor with test impact; dedicated task |
| REV-015709 A9 | Rolling averages in build() — premature optimization |
| REV-015709 A10 | Correlation threshold — design decision; needs deliberation |
