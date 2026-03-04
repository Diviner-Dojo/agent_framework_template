---
discussion_id: DISC-20260304-061753-scheduled-local-notifications-spec-review
started: 2026-03-04T06:18:09.005273+00:00
ended: 2026-03-04T06:28:37.261701+00:00
agents: [architecture-consultant, facilitator, qa-specialist, security-specialist]
total_turns: 5
---

# Discussion: DISC-20260304-061753-scheduled-local-notifications-spec-review

## Turn 1 — facilitator (evidence)
*2026-03-04T06:18:09.005273+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Plan scheduled OS local notifications for timed reminders — 'set a task to remind me tomorrow at 4pm' or 'set a reminder to give cat meds in an hour' should trigger a phone alert at the right time, even with the app closed.
- **Files/scope**: New spec SPEC-20260304-061650-scheduled-local-notifications.md; affects task schema, intent routing, session providers, and requires a new NotificationSchedulerService and flutter_local_notifications package.
- **Developer-stated motivation**: The gap between 'I set a reminder' and 'nothing happens at the promised time' breaks the personal-assistant contract. Current reminder intent routes to Google Calendar, not local notifications.
- **Explicit constraints**: ADHD notification contract (fires once, no re-escalation, no badge accumulation, no guilt on dismiss). Must work with app closed. Must handle Android 13+ exact alarm permissions.

---

## Turn 2 — architecture-consultant (critique)
*2026-03-04T06:23:49.017711+00:00 | confidence: 0.91*
*tags: architecture, adr, schema, adhd-contract*

## Architecture Review: Scheduled Local Notifications
**Verdict**: APPROVE WITH CHANGES (3 blocking items)
**Confidence**: 0.91

### Q1-Q5 Answers
Q1: flutter_local_notifications — Principle #8 (least-complex), better adoption, simpler API, no unused features.
Q2: Task with isQuickReminder bool flag (Option C) — ADR-0032 precedent shows separate tables only when entity has independent metadata. Reminders are tasks with a time component.
Q3: Add reminderTime DateTime? + notificationId int? columns (Option A + C mandatory). Option B (reuse dueDate) is architecturally dangerous — all consumers treat dueDate as date-only.
Q4: Replace _handleReminderIntent body entirely. Default ALL IntentType.reminder to local notification. 'Remind me about the team meeting Friday' already should be calendar — intent classifier handles this. Current conflation is a bug to fix, not a design to preserve.
Q5: Auto-schedule with spoken confirmation + cancel window ('Got it, I'll remind you at 3:47. Say cancel to remove it.'). ADHD effortless capture contract, matches task voice flow, lower friction than confirmation card.

### Blocking Findings
F1 (HIGH): Missing ADR. Every OS platform integration has an ADR (0018-photo, 0019-location, 0020-calendar, 0021-video, 0022-voice). Local notifications introduce SCHEDULE_EXACT_ALARM, new plugin, new background path, schema change. ADR-0033 must be written before implementation begins.
F2 (MEDIUM): Schema version error. Spec says v13 but current schema is v10. ADR-0032 reserved v11 for user_checkin_config (unimplemented). Next migration is v11 or v12. Fix before implementation.
F3 (MEDIUM): 9am auto-nudge for date-only tasks violates ADHD contract. User never requested a timed notification — auto-scheduling one is implicit escalation. Remove or make opt-in via Settings (matching ReminderService.isEnabled pattern).

### Advisory Findings
A1 (MEDIUM): _handleReminderIntent currently calls calendarEventDao.countPendingForSession() and _extractEventDetails — hard coupling to calendar. Full body replacement needed, not partial refactor. ADR-0020 §7 pending cap (5 events) is a calendar concept, does not apply to local notifications.
A2 (MEDIUM): TaskExtractionService._extractDueDate explicitly strips time (returns midnight). Both Layer A (regex) and Layer B (LLM prompt) need time-of-day extraction. Add reminderTime field to ExtractedTask. EventExtractionService already handles full datetime — reuse patterns.
A3 (LOW): Notification ID collision: use first 4 bytes of taskId UUID → deterministic 32-bit int, no counter reset on reinstall. Store as notificationId in Tasks table (already in spec as Q3C).
A4 (LOW): Permission flow detail: POST_NOTIFICATIONS (runtime dialog) and SCHEDULE_EXACT_ALARM (Settings deep-link) are two separate flows. Samsung/Xiaomi battery optimization is a known caveat. Three-step check: POST_NOTIFICATIONS → SCHEDULE_EXACT_ALARM → inexact fallback.

---

## Turn 3 — security-specialist (critique)
*2026-03-04T06:24:07.010341+00:00 | confidence: 0.87*
*tags: security, permissions, data-exposure, android*

## Security Review: Scheduled Local Notifications
**Verdict**: APPROVE WITH CHANGES (2 blocking items)
**Confidence**: 0.87

### Trust Boundaries
Voice/text → AI extraction → OS notification slot. ADR-0005 correctly routes LLM extraction through Edge Function. Existing 200-char title cap in TaskExtractionService is adequate sanitization. No server component = no push token attack surface. allowBackup=false already set in AndroidManifest.xml.

### Blocking Findings
F1 (MEDIUM — Sensitive Data Exposure): Notification content (full task title) appears on lock screen by default. 'Call lawyer about divorce at 4pm' is readable to any bystander. Spec must require NotificationVisibility.private on Android (hides content behind lock screen, shows generic placeholder). iOS: set hiddenPreviewsBodyPlaceholder. Advisory: add optional user-facing 'Private Notifications' toggle in Settings. Default: private.

F2 (MEDIUM — Security Misconfiguration): Spec mentions both SCHEDULE_EXACT_ALARM and USE_EXACT_ALARM without resolving which. USE_EXACT_ALARM requires a specific Play Store category (alarm clocks, calendars) — requesting it for a journaling app risks Play Store rejection. Must specify SCHEDULE_EXACT_ALARM. Graceful degradation must document the UX string: 'Your notification may arrive up to 15 minutes late' — not a silent fallback that breaks the personal-assistant contract.

### Advisory Findings
A1 (LOW): Notification ID derivation should use UUID-based strategy (first 4 bytes of taskId UUID → positive int32) not sequential counter. Counter resets on reinstall cause silent alarm cancellations. Promote Q3C (notificationId column) from 'option' to 'required' in spec.
A2 (LOW): Injection risk is low — Android NotificationManager treats title as plain text, no shell/SQL context. Existing 200-char cap is adequate. Confirm scheduler passes validated ExtractedTask struct, never raw user string.
A3 (LOW — Dependency Trust): flutter_local_notifications: high pub.dev score, actively maintained (MaikuB), no known CVEs, thin platform-channel wrapper with no network calls. Acceptable. Pin version with caret range, not any.

### Additional Boundary Note
SCHEDULE_EXACT_ALARM can be revoked by user post-install (Android battery settings). NotificationSchedulerService should listen for ACTION_SCHEDULE_EXACT_ALARM_PERMISSION_STATE_CHANGED broadcast and surface degradation in UI. flutter_local_notifications does not handle this automatically.

---

## Turn 4 — qa-specialist (critique)
*2026-03-04T06:24:30.817973+00:00 | confidence: 0.88*
*tags: qa, testing, migration, mocking*

## QA Review: Scheduled Local Notifications
**Verdict**: APPROVE WITH CHANGES (5 high-severity test gaps must be resolved)
**Confidence**: 0.88

### Blocking Findings (spec must address before implementation)
F1 (HIGH): NotificationSchedulerService mock pattern unspecified. flutter_local_notifications plugin is a concrete class — if scheduler instantiates it directly, it is untestable without platform channels. Must specify injectable interface pattern: pass FlutterLocalNotificationsPlugin (or abstract wrapper) via constructor. Pattern to follow: _FakeClaudeApiService in task_extraction_service_test.dart.

F2 (HIGH): Cancellation side effects must NOT be in DAO layer. Spec implies TaskDao.completeTask() and deleteTask() cancel notifications — DAO must stay pure persistence. Cancellation belongs in provider layer (SessionNotifier or new TaskNotifier). Provider-level tests must verify cancel(notificationId) is called with correct ID.

F3 (HIGH): Schema migration test required. Project has migration_v2_test.dart through v6 — v13 (or correct version) needs same treatment. Verify: new schema version accepted; fresh task insert has null reminderTime and notificationId; existing task row survives upgrade with null defaults.

F4 (HIGH): Past-time scheduling behavior unspecified. If reminderTime is in the past (system clock drift, restored from backup), flutter_local_notifications behavior is undefined. Spec must specify: short-circuit scheduling when scheduledAt.isBefore(DateTime.now()), return gracefully, do not call zonedSchedule. Add test for this path.

F5 (HIGH): Intent routing disambiguation needs tests BEFORE coding Q4. 'Remind me about the meeting Friday' → calendar vs. 'give cat meds in an hour' → local notification. This is exactly the type of routing change that caused bugs in PR #56 and #57. Tests must exist before refactor.

### Medium Findings
M1: Notification ID uniqueness test missing. Add: 'IDs for two different taskIds do not collide' (sample of 10+ UUIDs); 'scheduling second notification for same task cancels previous'.
M2: Time-of-day extraction tests missing in task_extraction_service_test.dart. Add group 'time-of-day extraction': 'in an hour', 'at 4pm', 'in 30 minutes', 'tomorrow at 9am' — all use fixed now for determinism.
M3: Race condition (complete before notification fires) must be specified as acceptable behavior. Add test: cancel() called even when reminderTime is in the past at completion time.

### Edge Cases for Spec
1. 'in an hour' at 11:30pm wraps to next day
2. RECEIVE_BOOT_COMPLETED permission needed for post-reboot alarm survival (not mentioned in spec)
3. Task deleted while notification inflight — acceptable, document explicitly
4. Android system limit of ~500 AlarmManager entries for high-volume users
5. UI date picker: block past-time selection or warn?
6. uncompleteTask() — should new notification be scheduled? Spec silent on this.

---

## Turn 5 — facilitator (synthesis)
*2026-03-04T06:28:37.261701+00:00 | confidence: 0.92*

## Request Context
- **What was requested**: Plan OS-level local notifications for timed reminders. Any message with explicit time reference classified as reminder or task should result in a scheduled phone alert, even when app is closed.
- **Files/scope**: SPEC-20260304-061650-scheduled-local-notifications.md
- **Developer-stated motivation**: The gap between 'I set a reminder' and 'nothing happens at the promised time' breaks the personal-assistant contract. Tasks with due dates are silently ignored by the OS.
- **Explicit constraints**: ADHD contract (fires once, no escalation, no badge accumulation). Voice-first effortless capture.

## Synthesis

All five architecture questions resolved unanimously across three specialist reviews. Spec updated with the following changes:

### Architecture Decisions Locked
- Q1: flutter_local_notifications (not awesome_notifications)
- Q2: Task with isQuickReminder bool flag (Option C — simplest schema, one entity type)
- Q3: Add reminderTime DateTime? + notificationId int? columns alongside dueDate (Option A)
- Q4: Replace _handleReminderIntent() body entirely — all IntentType.reminder → local notification (calendar-adjacent already classified as calendarEvent, no new classifier needed)
- Q5: Auto-schedule with spoken confirmation + cancel window — no tap required (ADHD effortless capture)

### Blocking Changes Applied to Spec

**B-1 (Security)**: Lock-screen visibility added as explicit requirement. NotificationVisibility.private required — title/body must NOT appear on lock screen. Only generic 'Reminder' placeholder shown.

**B-2 (Security)**: SCHEDULE_EXACT_ALARM explicitly named (not USE_EXACT_ALARM). USE_EXACT_ALARM targets alarm-clock apps and has different Play Store category implications.

**B-3 (Architecture — ADHD violation)**: Removed 9am auto-nudge for date-only due dates. Requirement 2 now states: date-only tasks do NOT schedule any notification. User must supply explicit time. Auto-scheduling at 9am without user request violates ADHD non-escalation contract.

**B-4 (Architecture)**: Schema version corrected. Current schema is v10; ADR-0032 reserved v11 for user_checkin_config (still deferred). Use v11 if still available, v12 if v11 has been consumed.

**B-5 (Architecture)**: ADR-0033 required before implementation — documents flutter_local_notifications selection, NotificationSchedulerService abstraction, and notification ID namespace strategy.

**B-6 (QA)**: Injectable mock pattern mandated. NotificationSchedulerService must accept FlutterLocalNotificationsPlugin via constructor injection for deterministic unit testing.

**B-7 (QA)**: Migration test added to acceptance criteria — existing tasks with null reminderTime/notificationId must survive schema migration without data loss.

**B-8 (QA)**: Past-time short-circuit added as Requirement 8. If scheduledAt.isBefore(DateTime.now()), do not schedule — surface in-app error and prompt for new time.

### Additional Changes
- RECEIVE_BOOT_COMPLETED permission + BootReceiver added to Affected Components and Risk Assessment (post-reboot survival)
- isQuickReminder bool column added to schema change list
- Cancel window clarified in Requirement 9 (spoken 'cancel' within ~10s undo window)
- Discovery sprint Group A patterns noted as layering on top of this spec

### Advisory Items (Non-Blocking, Deferred)
- Notification action buttons (mark-complete from notification shade) — future iteration
- Segmented notification ID namespace (SPEC-20260303-discovery Group A Pattern 8) — adopt when building on top
- Injectable AppClock for deterministic time testing — worth adopting from discovery Group A Pattern 7
- Fuzzy time parsing edge cases (5:45pm, noon, midnight) — cover in extraction service tests
- Riverpod provider initialization order when plugin is platform-dependent — verify at build time

---
