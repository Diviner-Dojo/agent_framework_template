---
adr_id: ADR-0033
title: "NotificationSchedulerService: flutter_local_notifications, Abstraction Boundary, and Notification ID Namespace"
status: accepted
date: 2026-03-04
decision_makers: [architect, facilitator, architecture-consultant, security-specialist, qa-specialist]
discussion_id: DISC-20260304-061753-scheduled-local-notifications-spec-review
supersedes: null
risk_level: high
confidence: 0.92
tags: [notifications, local-notifications, flutter, android, ios, adhd-ux]
---

## Context

The app needed OS-level local notifications so that timed reminders ("give cat meds in an
hour", "call Mom tomorrow at 4pm") fire at the scheduled time even when the app is closed.
No notification package existed in `pubspec.yaml`. The design required:

- Exact-alarm scheduling (not polling) to avoid battery drain
- ADHD-safe contract: fires once, no re-escalation, no badge accumulation, no unsolicited
  auto-nudge for date-only tasks
- Lock-screen privacy: personal/medical content must not appear on the lock screen
- Testability: unit tests must not invoke real platform channels
- Post-reboot survival: scheduled alarms must be rescheduled after device restart

Three packages were evaluated during the planning phase:
- `flutter_local_notifications` — widely-used, stable, comprehensive Android/iOS support
- `awesome_notifications` — richer action buttons, but heavier dependency footprint and
  less stable maintenance history
- `android_alarm_manager_plus` — lower-level, Android-only, incompatible with iOS path

## Decision

### 1. Package: `flutter_local_notifications`

Use `flutter_local_notifications` as the sole notification package. It provides:
- Exact alarm scheduling on Android (via `AndroidScheduleMode.exactAllowWhileIdle`)
- Full iOS support (local notification entitlement not required)
- Notification channel configuration (visibility, importance, sound, badge behavior)
- Plugin instance injectable via constructor — enables mock injection in tests

`awesome_notifications` was rejected: its richer action buttons are not needed in v1, and
its maintenance history has had breaking release gaps. Complexity is added only when earned.

### 2. Abstraction: `NotificationSchedulerService`

A new `lib/services/notification_scheduler_service.dart` encapsulates all platform
notification logic behind a Dart class. The `FlutterLocalNotificationsPlugin` instance is
injected via constructor — the production provider passes a real plugin; tests inject a
mock.

This follows the same boundary pattern as `SpeechRecognitionService` (ADR-0022) and
`DeepgramSttService` (ADR-0031): platform coupling lives in one service, not scattered
across DAOs or providers.

### 3. Notification ID Namespace

Notification IDs are stored as `notificationId int?` on the `tasks` table row. IDs are
generated as sequential integers managed by the service. The namespace is segmented:
- Task reminders: IDs in range 1000–1999 (max 1000 concurrent task notifications)
- Reserved for future use (digest, daily nudge): 2000+

This avoids collisions between notification categories. On reinstall, IDs reset — this is
acceptable because reinstall clears all scheduled notifications anyway.

### 4. Android Permissions

- `SCHEDULE_EXACT_ALARM` — required for exact alarms on Android 12+. `USE_EXACT_ALARM`
  was considered but rejected: it targets alarm-clock apps and triggers Play Store review
  implications not applicable to a journal app.
- `POST_NOTIFICATIONS` — runtime permission required on Android 13+, requested on first
  timed reminder creation.
- `RECEIVE_BOOT_COMPLETED` — required so a `BootReceiver` can reschedule pending
  notifications after device reboot.

### 5. Lock-Screen Visibility

All task/reminder notifications use `NotificationVisibility.private`. The notification
title and body are hidden on the lock screen; a generic "Reminder" placeholder is shown
instead. This protects potentially sensitive content (health reminders, personal tasks).

### 6. ADHD Notification Contract

- Fires exactly once at scheduled time. No re-fire, no escalation.
- If dismissed, does not reappear (OS-level dismiss is final).
- No badge count accumulation (`showBadge: false` on Android channel).
- Date-only tasks do NOT auto-schedule a notification — user must supply explicit time.
- Past-time scheduling is rejected at the service layer with an in-app error.

## Alternatives Considered

### Alternative 1: `awesome_notifications`
- **Pros**: Richer action buttons (mark complete from notification shade), more visual customization
- **Cons**: Heavier dependency, less stable release history, action buttons not needed in v1
- **Reason rejected**: Complexity not earned by current requirements. Can be adopted later
  if action button support becomes a priority.

### Alternative 2: `android_alarm_manager_plus`
- **Pros**: Lower-level control on Android, well-tested exact alarm scheduling
- **Cons**: Android-only — separate iOS implementation would be required. Doubles the
  platform surface.
- **Reason rejected**: `flutter_local_notifications` covers both platforms uniformly.

### Alternative 3: Push notifications via Supabase
- **Pros**: Works even when app is uninstalled from memory
- **Cons**: Requires server-side scheduling infrastructure, network dependency, APNs + FCM
  registration — massively disproportionate complexity for user-set reminders. ADR-0005
  proxies Claude through Edge Functions; adding FCM would require a separate subscription
  service.
- **Reason rejected**: Local scheduling satisfies the requirement; server-side push is
  reserved for team/collaborative features not yet designed.

## Consequences

### Positive
- Reminders fire at the exact scheduled time, even with app closed
- Unit tests are deterministic (mock plugin via constructor injection)
- Lock-screen privacy enforced by design
- ADHD contract is explicit and enforceable in code review

### Negative
- Android exact alarm permission adds a manifest entry visible to security reviewers;
  must be justified in Play Store listing
- Post-reboot rescheduling requires a `BootReceiver` — another Android-specific surface
- Notification IDs stored in SQLite can diverge from OS state on reinstall (acceptable;
  reinstall clears OS notifications anyway)

### Neutral
- `NotificationVisibility.private` means power users cannot see notification content on
  lock screen — this is intentional, not a limitation
- Notification ID namespace segmentation anticipates future digest/nudge notification
  types without schema changes

## Linked Discussion

See: discussions/2026-03-04/DISC-20260304-061753-scheduled-local-notifications-spec-review/
