// ===========================================================================
// file: test/services/notification_scheduler_service_test.dart
// purpose: Unit tests for NotificationSchedulerService.
//
// Tests the pure-logic paths that fire BEFORE any plugin call:
//   - Past-time guard (PastReminderTimeException, Requirement 8)
//   - cancelNotification(null) is a no-op (returns immediately)
//
// The OS-scheduling path (zonedSchedule) is tested on-device only because
// FlutterLocalNotificationsPlugin is a platform singleton that requires
// real platform channels for scheduling. The past-time and null-id guards
// are verified here since they fire before any plugin interaction.
//
// See: SPEC-20260304-061650, ADR-0033
// ===========================================================================

import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:agentic_journal/services/notification_scheduler_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  // Helper: create service with the singleton plugin.
  // The plugin is never called in these tests — guards fire first.
  NotificationSchedulerService makeService() {
    return NotificationSchedulerService(FlutterLocalNotificationsPlugin());
  }

  group('PastReminderTimeException', () {
    test(
      // Requirement 8: scheduleNotification must reject past times immediately
      // (before any plugin call) to prevent ghost OS alarms.
      'thrown when scheduledAt is in the past',
      () async {
        final service = makeService();
        final past = DateTime.now().subtract(const Duration(minutes: 5));

        // scheduleNotification() is async — use expectLater() so the returned
        // Future is awaited and the thrown exception is actually observed.
        // A non-awaited expect() on an async closure silently passes even if
        // the exception is never thrown (false positive).
        await expectLater(
          () => service.scheduleNotification(
            title: 'Cat meds',
            body: 'Time to give cat meds',
            scheduledAt: past,
            requestPermissionIfNeeded: false,
          ),
          throwsA(isA<PastReminderTimeException>()),
        );
      },
    );

    test('PastReminderTimeException carries the rejected time', () {
      final dt = DateTime(2026, 3, 4, 14, 0);
      final e = PastReminderTimeException(dt);
      expect(e.scheduledAt, dt);
      expect(e.toString(), contains('2026'));
    });
  });

  group('cancelNotification', () {
    test(
      // Safety contract: callers pass null when a task has no scheduled
      // notification (e.g. date-only tasks). Must be a no-op.
      'null id returns immediately without throwing',
      () async {
        final service = makeService();
        // Should complete without error — guard returns before plugin call.
        await service.cancelNotification(null);
      },
    );
  });

  group('NotificationPermissionDeniedException', () {
    test('toString is descriptive', () {
      const e = NotificationPermissionDeniedException();
      expect(e.toString(), contains('NotificationPermissionDeniedException'));
    });
  });
}
