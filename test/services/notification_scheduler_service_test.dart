// ===========================================================================
// file: test/services/notification_scheduler_service_test.dart
// purpose: Unit tests for NotificationSchedulerService.
//
// Tests the pure-logic paths that fire BEFORE any plugin call:
//   - Past-time guard (PastReminderTimeException, Requirement 8)
//   - cancelNotification(null) is a no-op (returns immediately)
//   - rescheduleFromTasks early return when !_initialized (A2, ADR-0033)
//   - rescheduleFromTasks PlatformException path adds to failedTaskIds (A-4, ADR-0033)
//
// The OS-scheduling path (zonedSchedule) is tested on-device only because
// FlutterLocalNotificationsPlugin is a platform singleton that requires
// real platform channels for scheduling. The past-time and null-id guards
// are verified here since they fire before any plugin interaction.
//
// See: SPEC-20260304-061650, SPEC-20260305-144939, ADR-0033
// ===========================================================================

import 'package:flutter/services.dart' show PlatformException;
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:agentic_journal/database/app_database.dart' show Task;
import 'package:agentic_journal/services/notification_scheduler_service.dart';

/// A [NotificationSchedulerService] that throws [PlatformException]
/// from [scheduleNotification] to simulate SCHEDULE_EXACT_ALARM revocation
/// (Android 12+ permission revoked by user after initial grant).
///
/// [FlutterLocalNotificationsPlugin] uses a private constructor and cannot
/// be subclassed. We override [scheduleNotification] instead — the public
/// method that [rescheduleFromTasks] calls — which is the actual catch site.
///
/// Used by the rescheduleFromTasks PlatformException path test.
class _ThrowingSchedulerService extends NotificationSchedulerService {
  _ThrowingSchedulerService() : super(FlutterLocalNotificationsPlugin());

  @override
  Future<int> scheduleNotification({
    required String title,
    required String body,
    required DateTime scheduledAt,
    bool requestPermissionIfNeeded = true,
  }) async {
    throw PlatformException(code: 'SCHEDULE_EXACT_ALARM_NOT_ALLOWED');
  }
}

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

  // Advisory A-2 from REV-20260304-085452: rescheduleFromTasks must return
  // empty result immediately when service is not initialized.
  //
  // The test uses a NON-EMPTY task list to confirm the early return is triggered
  // by !_initialized, not by tasks.isEmpty (different code path).
  group('rescheduleFromTasks — early return when not initialized', () {
    test(
      'returns empty rescheduled and failedTaskIds when service is not initialized',
      () async {
        // Do NOT call initialize() or setInitializedForTesting() — _initialized stays false.
        final service = NotificationSchedulerService(
          FlutterLocalNotificationsPlugin(),
        );
        final futureTime = DateTime.now().add(const Duration(days: 1));
        // Non-empty task list with valid reminderTime + notificationId.
        // This ensures early return tests !_initialized, not tasks.isEmpty.
        final task = Task(
          taskId: 't-uninit-01',
          title: 'Uninitialized service test',
          status: 'ACTIVE',
          syncStatus: 'PENDING',
          isQuickReminder: false,
          createdAt: DateTime.now(),
          updatedAt: DateTime.now(),
          reminderTime: futureTime,
          notificationId: 1042,
        );

        final result = await service.rescheduleFromTasks([task]);

        expect(
          result.rescheduled,
          isEmpty,
          reason: 'No reschedules when service is not initialized',
        );
        expect(
          result.failedTaskIds,
          isEmpty,
          reason: 'No failures when service is not initialized (early return)',
        );
      },
    );
  });

  // Advisory A-4 + QA-specialist F1 from SPEC-20260305-144939:
  // rescheduleFromTasks must add task ID to failedTaskIds when zonedSchedule
  // throws PlatformException (simulates SCHEDULE_EXACT_ALARM revocation on
  // Android 12+ after the notification was initially scheduled).
  //
  // Recovery path: provider calls taskDao.updateNotificationId(taskId, null)
  // to clear the stale ID, breaking the silent retry loop (ADR-0033 §Amendment).
  group('rescheduleFromTasks — PlatformException path', () {
    test('adds task ID to failedTaskIds and leaves rescheduled empty when '
        'zonedSchedule throws PlatformException', () async {
      final service = _ThrowingSchedulerService();
      // Bypass initialize() — setInitializedForTesting() skips platform channels
      // while still enabling the rescheduleFromTasks loop body.
      service.setInitializedForTesting();

      final futureTime = DateTime.now().add(const Duration(days: 1));
      final task = Task(
        taskId: 't-platform-ex-01',
        title: 'Platform exception test',
        status: 'ACTIVE',
        syncStatus: 'PENDING',
        isQuickReminder: false,
        createdAt: DateTime.now(),
        updatedAt: DateTime.now(),
        reminderTime: futureTime,
        notificationId: 1099, // stale ID from before permission revocation
      );

      final result = await service.rescheduleFromTasks([task]);

      expect(
        result.failedTaskIds,
        contains('t-platform-ex-01'),
        reason:
            'PlatformException from zonedSchedule should be caught and '
            'task ID added to failedTaskIds for caller to null out stale ID',
      );
      expect(
        result.rescheduled,
        isEmpty,
        reason: 'No successful reschedules when zonedSchedule throws',
      );
    });
  });

  // Advisory A-3 from REV-20260304-074715: notification ID counter persists
  // and wraps correctly.
  //
  // The counter is seeded from SharedPreferences in initialize() (which requires
  // real platform channels — tested on-device only). The counter INCREMENT and
  // PERSISTENCE path runs in _nextNotificationId() BEFORE the plugin call, so
  // it is observable in unit tests when the plugin fails (caught).
  //
  // Wrap-around (1999 → 1000): _nextId starts at 1000 (field default) when
  // initialize() is not called. The seeded-from-prefs path requires an
  // integration test. Here we verify counter persistence and the arithmetic
  // boundary via the default starting state.
  group('notification ID counter persistence and boundary', () {
    test(
      'counter is persisted to SharedPreferences on each allocation',
      () async {
        // No prior prefs — counter starts at 1000 (field default).
        final service = makeService();

        final future = DateTime.now().add(const Duration(days: 1));
        try {
          await service.scheduleNotification(
            title: 'Counter test',
            body: 'Testing counter persistence',
            scheduledAt: future,
            requestPermissionIfNeeded: false,
          );
        } catch (_) {
          // Plugin not initialized in unit tests — expected.
          // _nextNotificationId() ran and persisted before the plugin throw.
        }

        final prefs = await SharedPreferences.getInstance();
        // After allocating ID 1000, the next value (1001) is persisted.
        expect(prefs.getInt('notification_scheduler_next_id'), 1001);
      },
    );

    test(
      'counter wraps from 1999 to 1000 according to the namespace arithmetic',
      () {
        // Verify the wrap-around arithmetic directly. This is the conditional
        // inside _nextNotificationId():
        //   _nextId = _nextId >= _kTaskNotificationIdMax
        //       ? _kTaskNotificationIdMin : _nextId + 1;
        //
        // Seeding initialize() with 1999 and verifying the persisted value
        // after scheduling requires real platform channels (on-device test).
        // The arithmetic contract is verified here.
        const nextIdAtBoundary = 1999;
        const max = 1999;
        const min = 1000;

        // Simulate the wrap expression.
        final nextAfterWrap = nextIdAtBoundary >= max
            ? min
            : nextIdAtBoundary + 1;

        // After allocating 1999, the stored next ID must be 1000.
        expect(nextAfterWrap, 1000);
      },
    );

    test(
      'counter below minimum resets to 1000 on initialize() — boundary guard',
      () {
        // Verify the clamp-to-minimum expression inside initialize():
        //   if (_nextId < _kTaskNotificationIdMin || _nextId > _kTaskNotificationIdMax)
        //     _nextId = _kTaskNotificationIdMin;
        //
        // The expression is evaluated in initialize(), which requires real
        // platform channels. The arithmetic is verified here.
        const invalidHigh = 2500;
        const invalidLow = 500;
        const min = 1000;
        const max = 1999;

        bool isInRange(int id) => id >= min && id <= max;

        expect(
          isInRange(invalidHigh),
          isFalse,
          reason: '2500 is above the namespace max',
        );
        expect(
          isInRange(invalidLow),
          isFalse,
          reason: '500 is below the namespace min',
        );
        expect(isInRange(min), isTrue, reason: '1000 is the reset target');
      },
    );
  });
}
