---
spec_id: SPEC-20260304-061650
title: "Scheduled Local Notifications for Timed Reminders"
status: reviewed
risk_level: high
reviewed_by:
  - architecture-consultant
  - security-specialist
  - qa-specialist
discussion_id: DISC-20260304-061753-scheduled-local-notifications-spec-review
---

## Goal

When a user says "remind me to give the cat meds in an hour" or "set a task to call Mom
tomorrow at 4pm", the app schedules an OS-level local notification that fires at the
specified time — even if the app is closed. The notification opens the relevant task or
context when tapped.

## Context

### Current State

- **Tasks** have a `dueDate` column (nullable `DateTime`) — date-level precision only, no
  time-of-day component.
- **Reminder intent** (`IntentType.reminder`) is classified by `IntentClassifier` and
  routed to `_handleReminderIntent()`, which feeds the same Google Calendar extraction
  flow as calendar events. "Give the cat meds in an hour" currently tries to create a
  Google Calendar event — not a local notification.
- **No notification package** exists in `pubspec.yaml`.
- **Phase 4D** added in-app reminder banners (daily journaling nudge) — deliberately
  chose in-app over OS push for low-pressure ADHD design. Task-level timed reminders are
  a different problem: the user explicitly requested the reminder at a specific time.
- **Current schema**: v10 (four-table Pulse Check-In; `user_checkin_config` reserved for v11).

### Why Now

The gap between "I set a reminder" and "nothing happens at the promised time" breaks the
core personal-assistant contract. Tasks with due dates are silently ignored by the OS.
Voice-captured "cat meds in an hour" reminders disappear into a Google Calendar sync that
may never fire.

## Requirements

### Functional

1. **Explicit time triggers a notification**: Any message with an explicit time reference
   (`in an hour`, `at 4pm`, `tomorrow morning`, `in 30 minutes`) that is classified as
   `IntentType.reminder` OR `IntentType.task` results in a scheduled OS local
   notification at that time.

2. **Task due dates with time precision**: When a task is created with a due date that
   includes a time component (e.g., "tomorrow at 4pm"), a notification is scheduled at
   that exact time. Date-only due dates (e.g., "tomorrow") do NOT auto-schedule a
   notification — the user must supply an explicit time to avoid unsolicited alarms.
   *(ADHD contract: only fire when the user explicitly asked for a reminder.)*

3. **Pure reminders (no task entity needed)**: "Give the cat meds in an hour" creates a
   Task with `isQuickReminder: true` and schedules a notification. It does NOT require
   Google Calendar sync. Quick-reminder tasks may be shown in a separate "Reminders"
   section of the Tasks screen or filtered differently from project tasks.

4. **Notification content**:
   - Title: task/reminder title (e.g., "Cat meds")
   - Body: "Tap to view" or session context
   - Tap action: opens the Tasks screen (or specific task detail if navigable)
   - **Lock-screen visibility**: `NotificationVisibility.private` — notification title/body
     must NOT appear on the lock screen (medical/personal content). Only a generic "Reminder"
     placeholder is shown on lock screen.

5. **Cancellation**: If a task is completed or deleted, its scheduled notification is
   cancelled using the stored `notificationId`.

6. **Permission request**: On Android 13+ and iOS, request notification permission on
   first timed reminder creation. If denied, show an in-app fallback ("Reminder saved —
   enable notifications in Settings to get an alert.").

7. **ADHD notification contract**:
   - Fires once at the scheduled time. Does NOT re-fire or escalate.
   - If dismissed by the user at the OS level, it does not reappear.
   - No badge count accumulation.

8. **Past-time short-circuit**: If `scheduledAt.isBefore(DateTime.now())` at the time of
   scheduling, do not schedule a notification — surface an in-app error ("That time has
   already passed. When would you like the reminder?") and prompt for a new time.

9. **Voice confirmation UX**: Auto-schedule with spoken confirmation and a cancel window.
   After "cat meds in an hour" is recognized, the AI responds "Got it, I'll remind you
   at 3:47. Say 'cancel' to undo." — no tap required. If the user says "cancel" within
   the cancel window (~10s), the notification is removed. Lower friction matches the ADHD
   effortless capture contract.

### Non-Functional

- Notifications must fire when the app is closed (background scheduling).
- Must not drain battery excessively (use `flutter_local_notifications` exact alarm, not
  polling).
- Schema migration must be backward-compatible (existing tasks retain null
  `reminderTime` and null `notificationId`).
- `NotificationSchedulerService` must accept the `FlutterLocalNotificationsPlugin`
  instance via constructor injection to enable unit testing with mock plugins.

## Architecture Decisions (Resolved by Specialist Review)

**Q1 — Package**: Use `flutter_local_notifications` (not `awesome_notifications`).
Widely-used, stable, simpler API. `awesome_notifications` richer but heavier and less
stable history.

**Q2 — Reminder entity**: Option C — Task with `isQuickReminder bool` flag. Always creates
a Task (one entity type, simpler schema). Quick-reminder tasks displayed in a separate
"Reminders" section of tasks screen. Task list becomes reminder history. Avoids separate
Reminder table complexity.

**Q3 — Schema**: Option A — Add `reminderTime DateTime?` + `notificationId int?` columns
alongside `dueDate`. `dueDate` stays date-only for display; `reminderTime` is the precise
notification trigger. Requires schema migration (see below).

**Q4 — Intent routing**: Replace `_handleReminderIntent()` body entirely. All
`IntentType.reminder` → local notification scheduling. Calendar-adjacent reminders
("remind me about the meeting on Friday") are already classified as
`IntentType.calendarEvent` by the classifier — do not create a new split classifier.
Reminder intent always means personal local notification.

**Q5 — Voice confirmation**: Option B — Auto-schedule with spoken confirmation + cancel
window (see Requirement 9 above). No tap confirmation card needed.

## Constraints

- **ADHD contract**: Notification fires once. No re-escalation. No badge accumulation.
  No guilt on dismiss. No auto-scheduling for date-only tasks (user must supply explicit time).
- **Android exact alarms**: Use `SCHEDULE_EXACT_ALARM` (not `USE_EXACT_ALARM` — that
  targets alarm clock apps and has different Play Store implications). Must handle graceful
  degradation if not granted: inexact alarm as fallback with in-app notice.
- **Android 13+**: `POST_NOTIFICATIONS` runtime permission required; request on first
  timed reminder creation.
- **Post-reboot survival**: `RECEIVE_BOOT_COMPLETED` permission + `BootReceiver` required
  so scheduled notifications survive device reboot.
- **iOS**: Local notifications require permission. Entitlement not needed for local
  (only push).
- **ADR-0005**: Claude API proxied through Supabase Edge Functions — extraction calls for
  reminder time parsing use the existing `event-extraction` Edge Function.
- **Existing reminder intent routing**: Must not break current `IntentType.reminder`
  handling for existing tests (update tests, do not delete them).
- **No Google Calendar dependency**: Local notifications are OS-level, no sync required.
- **ADR-0033**: Before implementation begins, write ADR-0033 documenting the
  `flutter_local_notifications` package selection, `NotificationSchedulerService`
  abstraction boundary, and notification ID namespace strategy.

## Acceptance Criteria

- [ ] "Remind me to give the cat meds in an hour" → notification fires ~60 minutes later
  with title "Cat meds", app closed or backgrounded.
- [ ] "Add a task to call Mom tomorrow at 4pm" → notification fires at 4:00pm the next
  day.
- [ ] "Add a task to call Mom tomorrow" (date-only, no time) → NO notification scheduled.
  Task created with `dueDate` set, `reminderTime` null.
- [ ] Task due date with time set via Tasks screen UI → notification fires at that time.
- [ ] Past-time scheduling → in-app error, no notification scheduled.
- [ ] Completing a task cancels its pending notification.
- [ ] Deleting a task cancels its pending notification.
- [ ] First timed reminder prompts for notification permission; graceful fallback if denied.
- [ ] Notification tap opens the app (Tasks screen or task detail).
- [ ] Notification does NOT appear on lock screen (visibility = private).
- [ ] `flutter test` passes at ≥80% coverage with scheduler service unit tests
  (mock notification plugin via constructor injection).
- [ ] Migration test: existing tasks with null `reminderTime`/`notificationId` survive
  schema migration without data loss.
- [ ] `dart analyze` reports zero errors.
- [ ] Existing task/reminder/calendar intent tests still pass.
- [ ] ADR-0033 written and accepted before implementation begins.

## Risk Assessment

- **High: Android exact alarm permission** — Android 12+ requires `SCHEDULE_EXACT_ALARM`
  manifest permission. Android 13 added battery optimization interactions. Wrong
  implementation = notifications never fire on physical devices.
  Mitigation: test on SM_G998U1 (Snapdragon 888, Android 13) before merge.
- **Medium: Schema migration** — adding columns to Tasks table requires drift schema
  migration. Current schema is v10; `user_checkin_config` is reserved for v11.
  Use v11 if user_checkin_config is still deferred; use v12 if v11 is taken.
  Existing data safe (nullable columns), but migration must be tested.
- **Medium: Intent routing refactor** — `IntentType.reminder` currently routes to
  Google Calendar. Changing this flow risks breaking calendar-adjacent reminders and
  existing tests. Mitigation: update tests alongside the change.
- **Medium: Post-reboot survival** — notifications are lost on reboot without
  `BootReceiver`. `RECEIVE_BOOT_COMPLETED` permission + receiver must be registered in
  `AndroidManifest.xml`.
- **Low: Notification ID management** — cancelled notifications require storing the
  scheduled ID. ID collisions on reinstall or device restore must be handled.
  Mitigation: use `notificationId` stored on task row; use segmented namespace from
  SPEC-20260303-discovery Group A Pattern 8.

## Affected Components

| File | Change |
|------|--------|
| `pubspec.yaml` | Add `flutter_local_notifications` |
| `android/app/src/main/AndroidManifest.xml` | Add `SCHEDULE_EXACT_ALARM`, `POST_NOTIFICATIONS`, `RECEIVE_BOOT_COMPLETED`, `BootReceiver` |
| `android/app/src/main/kotlin/.../BootReceiver.kt` | NEW — reschedule pending notifications on boot |
| `lib/services/notification_scheduler_service.dart` | NEW — schedule/cancel local notifications (plugin injected via constructor) |
| `lib/providers/notification_providers.dart` | NEW — provider for scheduler service |
| `lib/database/tables.dart` | Add `reminderTime DateTime?`, `notificationId int?`, `isQuickReminder bool` to Tasks |
| `lib/database/app_database.dart` | Schema migration (v11 or v12 — confirm against ADR-0032 reservation) |
| `lib/database/daos/task_dao.dart` | Update create/update/delete to call scheduler |
| `lib/providers/session_providers.dart` | Route `IntentType.reminder` → scheduler |
| `lib/services/task_extraction_service.dart` | Extract time-of-day from text |
| `lib/ui/screens/tasks_screen.dart` | Show scheduled indicator on task cards; quick-reminder section |
| `test/services/notification_scheduler_service_test.dart` | NEW — mock plugin via constructor injection |
| `test/database/task_migration_test.dart` | NEW — schema migration test |
| `docs/adr/ADR-0033-notification-service.md` | NEW — before implementation |

## Dependencies

- Depends on: existing `TaskDao`, `IntentClassifier`, `TaskExtractionService`
- Depends on: ADR-0033 (must be written before implementation begins)
- Blocks: task due date phone alerts (the explicit user request)
- Related: Phase 4D in-app reminders (separate feature, same ADHD contract)
- Related: SPEC-20260303-discovery Group A (notification subsystem patterns 1–8) —
  build this spec first; Group A patterns layer on top
