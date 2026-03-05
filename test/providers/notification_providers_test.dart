// ===========================================================================
// file: test/providers/notification_providers_test.dart
// purpose: Tests for notificationBootRestoreProvider (ADR-0033).
//
// Coverage targets:
//   - failedTaskIds loop: provider nullifies stale notificationId for tasks
//     whose reschedule failed due to PlatformException (A2 advisory finding,
//     REV-20260305-164139).
// ===========================================================================

// Hide drift's isNull/isNotNull which conflict with flutter_test matchers.
import 'package:drift/drift.dart' hide isNull, isNotNull;
import 'package:drift/native.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/task_dao.dart';
import 'package:agentic_journal/providers/database_provider.dart';
import 'package:agentic_journal/providers/notification_providers.dart';
import 'package:agentic_journal/services/notification_scheduler_service.dart';

// ---------------------------------------------------------------------------
// Fake scheduler that returns a preset failedTaskIds list without
// invoking any platform channels.
// ---------------------------------------------------------------------------

/// A [NotificationSchedulerService] that immediately returns a preset result
/// from [rescheduleFromTasks], bypassing all platform-channel calls.
///
/// Used to drive the [notificationBootRestoreProvider] failedTaskIds code path
/// in unit tests without requiring the flutter_local_notifications plugin.
class _FakeSchedulerService extends NotificationSchedulerService {
  final List<String> _failedTaskIds;

  _FakeSchedulerService({required List<String> failedTaskIds})
    : _failedTaskIds = failedTaskIds,
      super(FlutterLocalNotificationsPlugin());

  @override
  Future<
    ({
      List<({String taskId, int newNotificationId})> rescheduled,
      List<String> failedTaskIds,
    })
  >
  rescheduleFromTasks(List<Task> tasks) async {
    return (
      rescheduled: <({String taskId, int newNotificationId})>[],
      failedTaskIds: List<String>.unmodifiable(_failedTaskIds),
    );
  }
}

void main() {
  group('notificationBootRestoreProvider', () {
    late AppDatabase database;
    late ProviderContainer container;

    setUp(() {
      SharedPreferences.setMockInitialValues({});
    });

    tearDown(() async {
      container.dispose();
      await database.close();
    });

    test('nullifies stale notificationId for failed tasks '
        '(regression: A2, REV-20260305-164139)', () async {
      database = AppDatabase.forTesting(NativeDatabase.memory());

      // Seed a task with a future reminder and a stored notificationId.
      // getTasksWithPendingReminders will return this row, causing the
      // provider to call rescheduleFromTasks → get failedTaskIds → null out.
      final futureReminder = DateTime.now().add(const Duration(hours: 1));
      await database
          .into(database.tasks)
          .insert(
            TasksCompanion(
              taskId: const Value('t-fail-01'),
              title: const Value('Failing task'),
              status: const Value(TaskStatus.active),
              syncStatus: const Value(TaskSyncStatus.pending),
              reminderTime: Value(futureReminder),
              notificationId: const Value(1099),
              createdAt: Value(DateTime.now().toUtc()),
              updatedAt: Value(DateTime.now().toUtc()),
            ),
          );

      final fakeScheduler = _FakeSchedulerService(failedTaskIds: ['t-fail-01']);

      container = ProviderContainer(
        overrides: [
          databaseProvider.overrideWithValue(database),
          notificationSchedulerProvider.overrideWithValue(fakeScheduler),
        ],
      );

      // Run the boot-restore provider to completion.
      await container.read(notificationBootRestoreProvider.future);

      // The provider must have nullified the stale notificationId.
      final task = await (database.select(
        database.tasks,
      )..where((t) => t.taskId.equals('t-fail-01'))).getSingleOrNull();

      expect(task, isNotNull);
      expect(
        task!.notificationId,
        isNull,
        reason:
            'notificationBootRestoreProvider must null out notificationId '
            'for failed tasks so the boot-restore loop does not retry them '
            'on every cold start (ADR-0033 PlatformException handling)',
      );
    });

    test('does not modify tasks that rescheduled successfully', () async {
      database = AppDatabase.forTesting(NativeDatabase.memory());

      final futureReminder = DateTime.now().add(const Duration(hours: 1));
      await database
          .into(database.tasks)
          .insert(
            TasksCompanion(
              taskId: const Value('t-ok-01'),
              title: const Value('Successfully rescheduled task'),
              status: const Value(TaskStatus.active),
              syncStatus: const Value(TaskSyncStatus.pending),
              reminderTime: Value(futureReminder),
              notificationId: const Value(1000),
              createdAt: Value(DateTime.now().toUtc()),
              updatedAt: Value(DateTime.now().toUtc()),
            ),
          );

      // Scheduler returns t-ok-01 as rescheduled with a new ID, not failed.
      final fakeScheduler = _SuccessSchedulerService(
        rescheduled: [(taskId: 't-ok-01', newNotificationId: 1001)],
      );

      container = ProviderContainer(
        overrides: [
          databaseProvider.overrideWithValue(database),
          notificationSchedulerProvider.overrideWithValue(fakeScheduler),
        ],
      );

      await container.read(notificationBootRestoreProvider.future);

      final task = await (database.select(
        database.tasks,
      )..where((t) => t.taskId.equals('t-ok-01'))).getSingleOrNull();

      expect(task, isNotNull);
      // ID must be updated to the new one, not null.
      expect(task!.notificationId, 1001);
    });

    test('skips rescheduling when no tasks have pending reminders', () async {
      // Empty database — no tasks with future reminderTime + stored ID.
      database = AppDatabase.forTesting(NativeDatabase.memory());

      final fakeScheduler = _FakeSchedulerService(failedTaskIds: []);

      container = ProviderContainer(
        overrides: [
          databaseProvider.overrideWithValue(database),
          notificationSchedulerProvider.overrideWithValue(fakeScheduler),
        ],
      );

      // Provider must complete without error even with an empty task list.
      await expectLater(
        container.read(notificationBootRestoreProvider.future),
        completes,
      );
    });

    test('updates rescheduled task and nullifies failed task in one invocation '
        '(A-5: mixed-mode shared-state guard, REV-20260305-175417)', () async {
      database = AppDatabase.forTesting(NativeDatabase.memory());

      final futureReminder = DateTime.now().add(const Duration(hours: 1));

      // Seed t-mixed-ok: reschedule will succeed → ID updated to 2002.
      await database
          .into(database.tasks)
          .insert(
            TasksCompanion(
              taskId: const Value('t-mixed-ok'),
              title: const Value('OK task'),
              status: const Value(TaskStatus.active),
              syncStatus: const Value(TaskSyncStatus.pending),
              reminderTime: Value(futureReminder),
              notificationId: const Value(2001),
              createdAt: Value(DateTime.now().toUtc()),
              updatedAt: Value(DateTime.now().toUtc()),
            ),
          );

      // Seed t-mixed-fail: reschedule will fail → ID nullified.
      await database
          .into(database.tasks)
          .insert(
            TasksCompanion(
              taskId: const Value('t-mixed-fail'),
              title: const Value('Failing task'),
              status: const Value(TaskStatus.active),
              syncStatus: const Value(TaskSyncStatus.pending),
              reminderTime: Value(futureReminder),
              notificationId: const Value(2003),
              createdAt: Value(DateTime.now().toUtc()),
              updatedAt: Value(DateTime.now().toUtc()),
            ),
          );

      container = ProviderContainer(
        overrides: [
          databaseProvider.overrideWithValue(database),
          notificationSchedulerProvider.overrideWithValue(
            _MixedSchedulerService(),
          ),
        ],
      );

      await container.read(notificationBootRestoreProvider.future);

      final okTask = await (database.select(
        database.tasks,
      )..where((t) => t.taskId.equals('t-mixed-ok'))).getSingleOrNull();
      final failTask = await (database.select(
        database.tasks,
      )..where((t) => t.taskId.equals('t-mixed-fail'))).getSingleOrNull();

      expect(okTask, isNotNull);
      expect(
        okTask!.notificationId,
        2002,
        reason:
            'rescheduled task must have its notificationId updated to '
            'the new ID returned by the scheduler',
      );

      expect(failTask, isNotNull);
      expect(
        failTask!.notificationId,
        isNull,
        reason:
            'failed task must have its notificationId nullified so '
            'the boot-restore loop does not retry it on every cold start',
      );
    });
  });
}

/// A [NotificationSchedulerService] that returns both a rescheduled entry
/// and a failed entry in the same invocation.
///
/// Used to verify that the provider's rescheduled loop and failedTaskIds loop
/// operate independently without shared-state interference (A-5,
/// REV-20260305-175417).
class _MixedSchedulerService extends NotificationSchedulerService {
  _MixedSchedulerService() : super(FlutterLocalNotificationsPlugin());

  @override
  Future<
    ({
      List<({String taskId, int newNotificationId})> rescheduled,
      List<String> failedTaskIds,
    })
  >
  rescheduleFromTasks(List<Task> tasks) async {
    return (
      rescheduled: <({String taskId, int newNotificationId})>[
        (taskId: 't-mixed-ok', newNotificationId: 2002),
      ],
      failedTaskIds: List<String>.unmodifiable(['t-mixed-fail']),
    );
  }
}

/// A [NotificationSchedulerService] that returns a preset rescheduled list.
class _SuccessSchedulerService extends NotificationSchedulerService {
  final List<({String taskId, int newNotificationId})> _rescheduled;

  _SuccessSchedulerService({
    required List<({String taskId, int newNotificationId})> rescheduled,
  }) : _rescheduled = rescheduled,
       super(FlutterLocalNotificationsPlugin());

  @override
  Future<
    ({
      List<({String taskId, int newNotificationId})> rescheduled,
      List<String> failedTaskIds,
    })
  >
  rescheduleFromTasks(List<Task> tasks) async {
    return (
      rescheduled: List<({String taskId, int newNotificationId})>.unmodifiable(
        _rescheduled,
      ),
      failedTaskIds: const <String>[],
    );
  }
}
