import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:drift/drift.dart' hide isNull, isNotNull;
import 'package:drift/native.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/task_dao.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';
import 'package:agentic_journal/services/notification_scheduler_service.dart';

/// Fake NotificationSchedulerService that records cancellation calls.
///
/// Used to assert that TaskDao calls cancelNotification() with the correct
/// notificationId on deleteTask() and completeTask() (advisory A-2 from
/// REV-20260304-074715).
class _FakeScheduler extends NotificationSchedulerService {
  final List<int?> cancelledIds = [];

  _FakeScheduler() : super(FlutterLocalNotificationsPlugin());

  @override
  Future<void> cancelNotification(int? notificationId) async {
    cancelledIds.add(notificationId);
  }
}

void main() {
  late AppDatabase database;
  late TaskDao taskDao;
  late SessionDao sessionDao;

  setUp(() async {
    database = AppDatabase.forTesting(NativeDatabase.memory());
    taskDao = TaskDao(database);
    sessionDao = SessionDao(database);
    // Create sessions for tasks to reference via foreign key.
    await sessionDao.createSession('s1', DateTime.utc(2026, 2, 25), 'UTC');
    await sessionDao.createSession('s2', DateTime.utc(2026, 2, 26), 'UTC');
  });

  tearDown(() async {
    await database.close();
  });

  /// Helper to create a standard TasksCompanion with sensible defaults.
  TasksCompanion makeTask({
    required String taskId,
    String? sessionId = 's1',
    String title = 'Test Task',
    String? notes,
    DateTime? dueDate,
    String? userId,
    String? rawUserMessage,
    String? status,
    String? syncStatus,
  }) {
    return TasksCompanion(
      taskId: Value(taskId),
      sessionId: Value(sessionId),
      title: Value(title),
      notes: Value.absentIfNull(notes),
      dueDate: Value.absentIfNull(dueDate),
      userId: Value.absentIfNull(userId),
      rawUserMessage: Value.absentIfNull(rawUserMessage),
      status: status != null ? Value(status) : const Value.absent(),
      syncStatus: syncStatus != null ? Value(syncStatus) : const Value.absent(),
    );
  }

  group('insertTask and getTaskById', () {
    test('inserts and retrieves a task', () async {
      await taskDao.insertTask(
        makeTask(
          taskId: 't1',
          title: 'Buy groceries',
          notes: 'Milk, eggs, bread',
          dueDate: DateTime.utc(2026, 2, 28, 17, 0),
          rawUserMessage: 'I need to buy groceries by Friday',
        ),
      );

      final task = await taskDao.getTaskById('t1');
      expect(task, isNotNull);
      expect(task!.taskId, 't1');
      expect(task.sessionId, 's1');
      expect(task.title, 'Buy groceries');
      expect(task.notes, 'Milk, eggs, bread');
      expect(task.dueDate, DateTime.utc(2026, 2, 28, 17, 0));
      expect(task.status, TaskStatus.pendingCreate);
      expect(task.syncStatus, TaskSyncStatus.pending);
      expect(task.googleTaskId, isNull);
      expect(task.googleTaskListId, isNull);
      expect(task.completedAt, isNull);
      expect(task.rawUserMessage, 'I need to buy groceries by Friday');
    });

    test('returns null for non-existent task', () async {
      final task = await taskDao.getTaskById('no-such');
      expect(task, isNull);
    });

    test('inserts task with userId', () async {
      await taskDao.insertTask(makeTask(taskId: 't2', userId: 'user-123'));

      final task = await taskDao.getTaskById('t2');
      expect(task!.userId, 'user-123');
    });

    test('inserts task without sessionId', () async {
      await taskDao.insertTask(
        makeTask(taskId: 't3', sessionId: null, title: 'Standalone task'),
      );

      final task = await taskDao.getTaskById('t3');
      expect(task, isNotNull);
      expect(task!.sessionId, isNull);
      expect(task.title, 'Standalone task');
    });

    test('inserts task without dueDate', () async {
      await taskDao.insertTask(makeTask(taskId: 't4'));

      final task = await taskDao.getTaskById('t4');
      expect(task!.dueDate, isNull);
    });

    test('inserts task without notes', () async {
      await taskDao.insertTask(makeTask(taskId: 't5'));

      final task = await taskDao.getTaskById('t5');
      expect(task!.notes, isNull);
    });

    test('defaults to PENDING_CREATE status and PENDING syncStatus', () async {
      await taskDao.insertTask(makeTask(taskId: 't6'));

      final task = await taskDao.getTaskById('t6');
      expect(task!.status, TaskStatus.pendingCreate);
      expect(task.syncStatus, TaskSyncStatus.pending);
    });
  });

  group('updateTask', () {
    test('updates task title', () async {
      await taskDao.insertTask(makeTask(taskId: 't1', title: 'Original title'));

      final updated = await taskDao.updateTask(
        't1',
        const TasksCompanion(title: Value('Updated title')),
      );
      expect(updated, 1);

      final task = await taskDao.getTaskById('t1');
      expect(task!.title, 'Updated title');
    });

    test('updates task notes', () async {
      await taskDao.insertTask(makeTask(taskId: 't1'));

      await taskDao.updateTask(
        't1',
        const TasksCompanion(notes: Value('New notes')),
      );

      final task = await taskDao.getTaskById('t1');
      expect(task!.notes, 'New notes');
    });

    test('updates task dueDate', () async {
      await taskDao.insertTask(makeTask(taskId: 't1'));

      final newDue = DateTime.utc(2026, 3, 15, 9, 0);
      await taskDao.updateTask('t1', TasksCompanion(dueDate: Value(newDue)));

      final task = await taskDao.getTaskById('t1');
      expect(task!.dueDate, newDue);
    });

    test('returns 0 for non-existent task', () async {
      final updated = await taskDao.updateTask(
        'no-such',
        const TasksCompanion(title: Value('New title')),
      );
      expect(updated, 0);
    });

    test('updates multiple fields at once', () async {
      await taskDao.insertTask(
        makeTask(taskId: 't1', title: 'Old', notes: null),
      );

      await taskDao.updateTask(
        't1',
        TasksCompanion(
          title: const Value('New title'),
          notes: const Value('Added notes'),
          dueDate: Value(DateTime.utc(2026, 4, 1)),
        ),
      );

      final task = await taskDao.getTaskById('t1');
      expect(task!.title, 'New title');
      expect(task.notes, 'Added notes');
      expect(task.dueDate, DateTime.utc(2026, 4, 1));
    });
  });

  group('deleteTask', () {
    test('deletes a single task', () async {
      await taskDao.insertTask(makeTask(taskId: 't1'));

      final deleted = await taskDao.deleteTask('t1');
      expect(deleted, 1);

      final task = await taskDao.getTaskById('t1');
      expect(task, isNull);
    });

    test('returns 0 for non-existent task', () async {
      final deleted = await taskDao.deleteTask('no-such');
      expect(deleted, 0);
    });

    test('does not affect other tasks', () async {
      await taskDao.insertTask(makeTask(taskId: 't1'));
      await taskDao.insertTask(makeTask(taskId: 't2'));

      await taskDao.deleteTask('t1');

      final t1 = await taskDao.getTaskById('t1');
      final t2 = await taskDao.getTaskById('t2');
      expect(t1, isNull);
      expect(t2, isNotNull);
    });
  });

  group('watchAllTasks', () {
    test('emits updates when tasks are added', () async {
      final stream = taskDao.watchAllTasks();

      // First emission: empty. Second after insert.
      expect(stream, emitsInOrder([isEmpty, hasLength(1)]));

      await taskDao.insertTask(makeTask(taskId: 't1'));
    });

    test('returns tasks ordered by createdAt descending', () async {
      // Use explicit createdAt to guarantee ordering (in-memory DB can
      // produce identical timestamps for rapid sequential inserts).
      await taskDao.insertTask(
        TasksCompanion(
          taskId: const Value('t1'),
          sessionId: const Value('s1'),
          title: const Value('First'),
          createdAt: Value(DateTime.utc(2026, 2, 25, 10, 0)),
        ),
      );
      await taskDao.insertTask(
        TasksCompanion(
          taskId: const Value('t2'),
          sessionId: const Value('s1'),
          title: const Value('Second'),
          createdAt: Value(DateTime.utc(2026, 2, 26, 10, 0)),
        ),
      );

      final stream = taskDao.watchAllTasks();
      final tasks = await stream.first;

      expect(tasks.length, 2);
      // Newest first.
      expect(tasks[0].taskId, 't2');
      expect(tasks[1].taskId, 't1');
    });

    test('includes tasks of all statuses', () async {
      await taskDao.insertTask(
        makeTask(taskId: 't1', status: TaskStatus.pendingCreate),
      );
      await taskDao.insertTask(
        makeTask(taskId: 't2', status: TaskStatus.active),
      );
      await taskDao.insertTask(
        makeTask(taskId: 't3', status: TaskStatus.completed),
      );
      await taskDao.insertTask(
        makeTask(taskId: 't4', status: TaskStatus.failed),
      );

      final tasks = await taskDao.watchAllTasks().first;
      expect(tasks.length, 4);
    });
  });

  group('watchActiveTasks', () {
    test('returns only ACTIVE and PENDING_CREATE tasks', () async {
      await taskDao.insertTask(
        makeTask(taskId: 't1', status: TaskStatus.pendingCreate),
      );
      await taskDao.insertTask(
        makeTask(taskId: 't2', status: TaskStatus.active),
      );
      await taskDao.insertTask(
        makeTask(taskId: 't3', status: TaskStatus.completed),
      );
      await taskDao.insertTask(
        makeTask(taskId: 't4', status: TaskStatus.failed),
      );

      final tasks = await taskDao.watchActiveTasks().first;
      expect(tasks.length, 2);

      final ids = tasks.map((t) => t.taskId).toSet();
      expect(ids, containsAll(['t1', 't2']));
    });

    test('orders by dueDate ascending then createdAt descending', () async {
      await taskDao.insertTask(
        makeTask(
          taskId: 't1',
          status: TaskStatus.active,
          dueDate: DateTime.utc(2026, 3, 10),
        ),
      );
      await Future<void>.delayed(const Duration(milliseconds: 10));
      await taskDao.insertTask(
        makeTask(
          taskId: 't2',
          status: TaskStatus.active,
          dueDate: DateTime.utc(2026, 3, 5),
        ),
      );

      final tasks = await taskDao.watchActiveTasks().first;
      expect(tasks.length, 2);
      // Earlier due date first.
      expect(tasks[0].taskId, 't2');
      expect(tasks[1].taskId, 't1');
    });

    test('emits updates when task status changes', () async {
      await taskDao.insertTask(
        makeTask(taskId: 't1', status: TaskStatus.active),
      );

      final stream = taskDao.watchActiveTasks();

      // First emission: 1 active task. Second after completing: 0.
      expect(stream, emitsInOrder([hasLength(1), isEmpty]));

      await taskDao.completeTask('t1', DateTime.now().toUtc());
    });

    test('returns empty list when no active tasks', () async {
      await taskDao.insertTask(
        makeTask(taskId: 't1', status: TaskStatus.completed),
      );

      final tasks = await taskDao.watchActiveTasks().first;
      expect(tasks, isEmpty);
    });
  });

  group('watchCompletedTasks', () {
    test('returns only COMPLETED tasks', () async {
      await taskDao.insertTask(
        makeTask(taskId: 't1', status: TaskStatus.active),
      );
      await taskDao.insertTask(
        makeTask(taskId: 't2', status: TaskStatus.completed),
      );
      await taskDao.insertTask(
        makeTask(taskId: 't3', status: TaskStatus.completed),
      );

      final tasks = await taskDao.watchCompletedTasks().first;
      expect(tasks.length, 2);

      final ids = tasks.map((t) => t.taskId).toSet();
      expect(ids, containsAll(['t2', 't3']));
    });

    test('orders by completedAt descending', () async {
      final earlier = DateTime.utc(2026, 2, 25, 10, 0);
      final later = DateTime.utc(2026, 2, 26, 10, 0);

      await taskDao.insertTask(
        makeTask(taskId: 't1', status: TaskStatus.active),
      );
      await taskDao.insertTask(
        makeTask(taskId: 't2', status: TaskStatus.active),
      );

      await taskDao.completeTask('t1', earlier);
      await taskDao.completeTask('t2', later);

      final tasks = await taskDao.watchCompletedTasks().first;
      expect(tasks.length, 2);
      // Most recently completed first.
      expect(tasks[0].taskId, 't2');
      expect(tasks[1].taskId, 't1');
    });

    test('returns empty list when no completed tasks', () async {
      await taskDao.insertTask(
        makeTask(taskId: 't1', status: TaskStatus.active),
      );

      final tasks = await taskDao.watchCompletedTasks().first;
      expect(tasks, isEmpty);
    });

    test('emits updates when task is completed', () async {
      await taskDao.insertTask(
        makeTask(taskId: 't1', status: TaskStatus.active),
      );

      final stream = taskDao.watchCompletedTasks();

      // First emission: empty. Second after completing: 1.
      expect(stream, emitsInOrder([isEmpty, hasLength(1)]));

      await taskDao.completeTask('t1', DateTime.now().toUtc());
    });
  });

  group('completeTask', () {
    test('sets status to COMPLETED and records completedAt', () async {
      await taskDao.insertTask(
        makeTask(taskId: 't1', status: TaskStatus.active),
      );

      final completedAt = DateTime.utc(2026, 2, 27, 15, 30);
      final updated = await taskDao.completeTask('t1', completedAt);
      expect(updated, 1);

      final task = await taskDao.getTaskById('t1');
      expect(task!.status, TaskStatus.completed);
      expect(task.completedAt, completedAt);
    });

    test('sets syncStatus to PENDING for re-sync', () async {
      await taskDao.insertTask(
        makeTask(
          taskId: 't1',
          status: TaskStatus.active,
          syncStatus: TaskSyncStatus.synced,
        ),
      );

      await taskDao.completeTask('t1', DateTime.utc(2026, 2, 27));

      final task = await taskDao.getTaskById('t1');
      expect(task!.syncStatus, TaskSyncStatus.pending);
    });

    test('updates updatedAt timestamp', () async {
      await taskDao.insertTask(makeTask(taskId: 't1'));
      final before = (await taskDao.getTaskById('t1'))!.updatedAt;

      await Future<void>.delayed(const Duration(milliseconds: 10));
      await taskDao.completeTask('t1', DateTime.utc(2026, 2, 27));

      final after = (await taskDao.getTaskById('t1'))!.updatedAt;
      expect(after.isAfter(before) || after.isAtSameMomentAs(before), isTrue);
    });

    test('returns 0 for non-existent task', () async {
      final updated = await taskDao.completeTask(
        'no-such',
        DateTime.utc(2026, 2, 27),
      );
      expect(updated, 0);
    });
  });

  group('uncompleteTask', () {
    test('sets status back to ACTIVE and clears completedAt', () async {
      await taskDao.insertTask(
        makeTask(taskId: 't1', status: TaskStatus.active),
      );
      await taskDao.completeTask('t1', DateTime.utc(2026, 2, 27));

      final updated = await taskDao.uncompleteTask('t1');
      expect(updated, 1);

      final task = await taskDao.getTaskById('t1');
      expect(task!.status, TaskStatus.active);
      expect(task.completedAt, isNull);
    });

    test('sets syncStatus to PENDING for re-sync', () async {
      await taskDao.insertTask(
        makeTask(
          taskId: 't1',
          status: TaskStatus.active,
          syncStatus: TaskSyncStatus.synced,
        ),
      );
      await taskDao.completeTask('t1', DateTime.utc(2026, 2, 27));
      // After completing, mark as synced.
      await taskDao.updateSyncStatus('t1', TaskSyncStatus.synced);

      await taskDao.uncompleteTask('t1');

      final task = await taskDao.getTaskById('t1');
      expect(task!.syncStatus, TaskSyncStatus.pending);
    });

    test('updates updatedAt timestamp', () async {
      await taskDao.insertTask(
        makeTask(taskId: 't1', status: TaskStatus.active),
      );
      await taskDao.completeTask('t1', DateTime.utc(2026, 2, 27));
      final before = (await taskDao.getTaskById('t1'))!.updatedAt;

      await Future<void>.delayed(const Duration(milliseconds: 10));
      await taskDao.uncompleteTask('t1');

      final after = (await taskDao.getTaskById('t1'))!.updatedAt;
      expect(after.isAfter(before) || after.isAtSameMomentAs(before), isTrue);
    });

    test('returns 0 for non-existent task', () async {
      final updated = await taskDao.uncompleteTask('no-such');
      expect(updated, 0);
    });
  });

  group('getTasksDueToday', () {
    test('returns tasks due today that are not completed', () async {
      final now = DateTime.now();
      final todayMorning = DateTime(now.year, now.month, now.day, 9, 0);
      final todayEvening = DateTime(now.year, now.month, now.day, 18, 0);

      await taskDao.insertTask(
        makeTask(
          taskId: 't1',
          status: TaskStatus.active,
          dueDate: todayMorning,
          title: 'Morning task',
        ),
      );
      await taskDao.insertTask(
        makeTask(
          taskId: 't2',
          status: TaskStatus.active,
          dueDate: todayEvening,
          title: 'Evening task',
        ),
      );

      final tasks = await taskDao.getTasksDueToday();
      expect(tasks.length, 2);
    });

    test('excludes completed tasks', () async {
      final now = DateTime.now();
      final todayNoon = DateTime(now.year, now.month, now.day, 12, 0);

      await taskDao.insertTask(
        makeTask(taskId: 't1', status: TaskStatus.active, dueDate: todayNoon),
      );
      await taskDao.insertTask(
        makeTask(
          taskId: 't2',
          status: TaskStatus.completed,
          dueDate: todayNoon,
        ),
      );

      final tasks = await taskDao.getTasksDueToday();
      expect(tasks.length, 1);
      expect(tasks[0].taskId, 't1');
    });

    test('excludes tasks due yesterday', () async {
      final now = DateTime.now();
      final yesterday = DateTime(
        now.year,
        now.month,
        now.day,
      ).subtract(const Duration(days: 1));

      await taskDao.insertTask(
        makeTask(taskId: 't1', status: TaskStatus.active, dueDate: yesterday),
      );

      final tasks = await taskDao.getTasksDueToday();
      expect(tasks, isEmpty);
    });

    test('excludes tasks due tomorrow', () async {
      final now = DateTime.now();
      final tomorrow = DateTime(
        now.year,
        now.month,
        now.day,
      ).add(const Duration(days: 1));

      await taskDao.insertTask(
        makeTask(taskId: 't1', status: TaskStatus.active, dueDate: tomorrow),
      );

      final tasks = await taskDao.getTasksDueToday();
      expect(tasks, isEmpty);
    });

    test('returns tasks ordered by dueDate ascending', () async {
      final now = DateTime.now();
      final todayLate = DateTime(now.year, now.month, now.day, 20, 0);
      final todayEarly = DateTime(now.year, now.month, now.day, 8, 0);

      await taskDao.insertTask(
        makeTask(
          taskId: 't1',
          status: TaskStatus.active,
          dueDate: todayLate,
          title: 'Late task',
        ),
      );
      await taskDao.insertTask(
        makeTask(
          taskId: 't2',
          status: TaskStatus.active,
          dueDate: todayEarly,
          title: 'Early task',
        ),
      );

      final tasks = await taskDao.getTasksDueToday();
      expect(tasks.length, 2);
      expect(tasks[0].taskId, 't2');
      expect(tasks[1].taskId, 't1');
    });

    test('returns empty list when no tasks are due today', () async {
      final tasks = await taskDao.getTasksDueToday();
      expect(tasks, isEmpty);
    });

    test('includes PENDING_CREATE tasks due today', () async {
      final now = DateTime.now();
      final todayNoon = DateTime(now.year, now.month, now.day, 12, 0);

      await taskDao.insertTask(
        makeTask(
          taskId: 't1',
          status: TaskStatus.pendingCreate,
          dueDate: todayNoon,
        ),
      );

      final tasks = await taskDao.getTasksDueToday();
      expect(tasks.length, 1);
      expect(tasks[0].taskId, 't1');
    });
  });

  group('getTasksDueTomorrow', () {
    test('returns tasks due tomorrow that are not completed', () async {
      final now = DateTime.now();
      final tomorrowMorning = DateTime(now.year, now.month, now.day + 1, 9, 0);
      final tomorrowEvening = DateTime(now.year, now.month, now.day + 1, 18, 0);

      await taskDao.insertTask(
        makeTask(
          taskId: 't1',
          status: TaskStatus.active,
          dueDate: tomorrowMorning,
          title: 'Morning task',
        ),
      );
      await taskDao.insertTask(
        makeTask(
          taskId: 't2',
          status: TaskStatus.active,
          dueDate: tomorrowEvening,
          title: 'Evening task',
        ),
      );

      final tasks = await taskDao.getTasksDueTomorrow();
      expect(tasks.length, 2);
    });

    test('excludes completed tasks', () async {
      final now = DateTime.now();
      final tomorrowNoon = DateTime(now.year, now.month, now.day + 1, 12, 0);

      await taskDao.insertTask(
        makeTask(
          taskId: 't1',
          status: TaskStatus.active,
          dueDate: tomorrowNoon,
        ),
      );
      await taskDao.insertTask(
        makeTask(
          taskId: 't2',
          status: TaskStatus.completed,
          dueDate: tomorrowNoon,
        ),
      );

      final tasks = await taskDao.getTasksDueTomorrow();
      expect(tasks.length, 1);
      expect(tasks[0].taskId, 't1');
    });

    test('excludes tasks due today', () async {
      final now = DateTime.now();
      final todayNoon = DateTime(now.year, now.month, now.day, 12, 0);

      await taskDao.insertTask(
        makeTask(taskId: 't1', status: TaskStatus.active, dueDate: todayNoon),
      );

      final tasks = await taskDao.getTasksDueTomorrow();
      expect(tasks, isEmpty);
    });

    test('excludes tasks due the day after tomorrow', () async {
      final now = DateTime.now();
      final dayAfterTomorrow = DateTime(
        now.year,
        now.month,
        now.day + 2,
        12,
        0,
      );

      await taskDao.insertTask(
        makeTask(
          taskId: 't1',
          status: TaskStatus.active,
          dueDate: dayAfterTomorrow,
        ),
      );

      final tasks = await taskDao.getTasksDueTomorrow();
      expect(tasks, isEmpty);
    });

    test('returns tasks ordered by dueDate ascending', () async {
      final now = DateTime.now();
      final tomorrowLate = DateTime(now.year, now.month, now.day + 1, 20, 0);
      final tomorrowEarly = DateTime(now.year, now.month, now.day + 1, 8, 0);

      await taskDao.insertTask(
        makeTask(
          taskId: 't1',
          status: TaskStatus.active,
          dueDate: tomorrowLate,
          title: 'Late task',
        ),
      );
      await taskDao.insertTask(
        makeTask(
          taskId: 't2',
          status: TaskStatus.active,
          dueDate: tomorrowEarly,
          title: 'Early task',
        ),
      );

      final tasks = await taskDao.getTasksDueTomorrow();
      expect(tasks.length, 2);
      expect(tasks[0].taskId, 't2');
      expect(tasks[1].taskId, 't1');
    });

    test('returns empty list when no tasks are due tomorrow', () async {
      final tasks = await taskDao.getTasksDueTomorrow();
      expect(tasks, isEmpty);
    });
  });

  group('getTasksToSync', () {
    test('returns ACTIVE tasks with PENDING syncStatus', () async {
      await taskDao.insertTask(
        makeTask(
          taskId: 't1',
          status: TaskStatus.active,
          syncStatus: TaskSyncStatus.pending,
        ),
      );

      final tasks = await taskDao.getTasksToSync();
      expect(tasks.length, 1);
      expect(tasks[0].taskId, 't1');
    });

    test('returns ACTIVE tasks with FAILED syncStatus', () async {
      await taskDao.insertTask(
        makeTask(
          taskId: 't1',
          status: TaskStatus.active,
          syncStatus: TaskSyncStatus.failed,
        ),
      );

      final tasks = await taskDao.getTasksToSync();
      expect(tasks.length, 1);
      expect(tasks[0].taskId, 't1');
    });

    test('returns COMPLETED tasks with PENDING syncStatus', () async {
      await taskDao.insertTask(
        makeTask(
          taskId: 't1',
          status: TaskStatus.completed,
          syncStatus: TaskSyncStatus.pending,
        ),
      );

      final tasks = await taskDao.getTasksToSync();
      expect(tasks.length, 1);
      expect(tasks[0].taskId, 't1');
    });

    test('returns COMPLETED tasks with FAILED syncStatus', () async {
      await taskDao.insertTask(
        makeTask(
          taskId: 't1',
          status: TaskStatus.completed,
          syncStatus: TaskSyncStatus.failed,
        ),
      );

      final tasks = await taskDao.getTasksToSync();
      expect(tasks.length, 1);
      expect(tasks[0].taskId, 't1');
    });

    test('excludes ACTIVE tasks already SYNCED', () async {
      await taskDao.insertTask(
        makeTask(
          taskId: 't1',
          status: TaskStatus.active,
          syncStatus: TaskSyncStatus.synced,
        ),
      );

      final tasks = await taskDao.getTasksToSync();
      expect(tasks, isEmpty);
    });

    test('excludes PENDING_CREATE tasks', () async {
      // PENDING_CREATE tasks are not yet confirmed — they should not sync.
      await taskDao.insertTask(
        makeTask(
          taskId: 't1',
          status: TaskStatus.pendingCreate,
          syncStatus: TaskSyncStatus.pending,
        ),
      );

      final tasks = await taskDao.getTasksToSync();
      expect(tasks, isEmpty);
    });

    test('excludes FAILED status tasks', () async {
      await taskDao.insertTask(
        makeTask(
          taskId: 't1',
          status: TaskStatus.failed,
          syncStatus: TaskSyncStatus.pending,
        ),
      );

      final tasks = await taskDao.getTasksToSync();
      expect(tasks, isEmpty);
    });

    test('returns mixed PENDING and FAILED sync statuses', () async {
      await taskDao.insertTask(
        makeTask(
          taskId: 't1',
          status: TaskStatus.active,
          syncStatus: TaskSyncStatus.pending,
        ),
      );
      await taskDao.insertTask(
        makeTask(
          taskId: 't2',
          status: TaskStatus.active,
          syncStatus: TaskSyncStatus.failed,
        ),
      );
      await taskDao.insertTask(
        makeTask(
          taskId: 't3',
          status: TaskStatus.active,
          syncStatus: TaskSyncStatus.synced,
        ),
      );

      final tasks = await taskDao.getTasksToSync();
      expect(tasks.length, 2);

      final ids = tasks.map((t) => t.taskId).toSet();
      expect(ids, containsAll(['t1', 't2']));
    });

    test('returns empty list when nothing needs sync', () async {
      final tasks = await taskDao.getTasksToSync();
      expect(tasks, isEmpty);
    });
  });

  group('updateGoogleTaskId', () {
    test('sets googleTaskId, googleTaskListId, and status to ACTIVE', () async {
      await taskDao.insertTask(makeTask(taskId: 't1'));

      final updated = await taskDao.updateGoogleTaskId(
        't1',
        'google-task-abc123',
        'google-list-xyz789',
      );
      expect(updated, 1);

      final task = await taskDao.getTaskById('t1');
      expect(task!.googleTaskId, 'google-task-abc123');
      expect(task.googleTaskListId, 'google-list-xyz789');
      expect(task.status, TaskStatus.active);
      expect(task.syncStatus, TaskSyncStatus.synced);
    });

    test('updates updatedAt timestamp', () async {
      await taskDao.insertTask(makeTask(taskId: 't1'));
      final before = (await taskDao.getTaskById('t1'))!.updatedAt;

      await Future<void>.delayed(const Duration(milliseconds: 10));
      await taskDao.updateGoogleTaskId('t1', 'g-id', 'g-list');

      final after = (await taskDao.getTaskById('t1'))!.updatedAt;
      expect(after.isAfter(before) || after.isAtSameMomentAs(before), isTrue);
    });

    test('returns 0 for non-existent task', () async {
      final updated = await taskDao.updateGoogleTaskId(
        'no-such',
        'g-id',
        'g-list',
      );
      expect(updated, 0);
    });

    test('transitions PENDING_CREATE to ACTIVE', () async {
      await taskDao.insertTask(
        makeTask(taskId: 't1', status: TaskStatus.pendingCreate),
      );
      expect(
        (await taskDao.getTaskById('t1'))!.status,
        TaskStatus.pendingCreate,
      );

      await taskDao.updateGoogleTaskId('t1', 'g-id', 'g-list');

      final task = await taskDao.getTaskById('t1');
      expect(task!.status, TaskStatus.active);
    });
  });

  group('updateSyncStatus', () {
    test('updates sync status to SYNCED', () async {
      await taskDao.insertTask(makeTask(taskId: 't1'));

      await taskDao.updateSyncStatus('t1', TaskSyncStatus.synced);

      final task = await taskDao.getTaskById('t1');
      expect(task!.syncStatus, TaskSyncStatus.synced);
    });

    test('updates sync status to FAILED', () async {
      await taskDao.insertTask(makeTask(taskId: 't1'));

      await taskDao.updateSyncStatus('t1', TaskSyncStatus.failed);

      final task = await taskDao.getTaskById('t1');
      expect(task!.syncStatus, TaskSyncStatus.failed);
    });

    test('updates sync status back to PENDING', () async {
      await taskDao.insertTask(makeTask(taskId: 't1'));
      await taskDao.updateSyncStatus('t1', TaskSyncStatus.synced);

      await taskDao.updateSyncStatus('t1', TaskSyncStatus.pending);

      final task = await taskDao.getTaskById('t1');
      expect(task!.syncStatus, TaskSyncStatus.pending);
    });

    test('updates updatedAt timestamp', () async {
      await taskDao.insertTask(makeTask(taskId: 't1'));
      final before = (await taskDao.getTaskById('t1'))!.updatedAt;

      await Future<void>.delayed(const Duration(milliseconds: 10));
      await taskDao.updateSyncStatus('t1', TaskSyncStatus.synced);

      final after = (await taskDao.getTaskById('t1'))!.updatedAt;
      expect(after.isAfter(before) || after.isAtSameMomentAs(before), isTrue);
    });

    test('returns 0 for non-existent task', () async {
      final updated = await taskDao.updateSyncStatus(
        'no-such',
        TaskSyncStatus.synced,
      );
      expect(updated, 0);
    });
  });

  group('countActiveTasks', () {
    test('counts ACTIVE and PENDING_CREATE tasks', () async {
      await taskDao.insertTask(
        makeTask(taskId: 't1', status: TaskStatus.active),
      );
      await taskDao.insertTask(
        makeTask(taskId: 't2', status: TaskStatus.pendingCreate),
      );
      await taskDao.insertTask(
        makeTask(taskId: 't3', status: TaskStatus.completed),
      );
      await taskDao.insertTask(
        makeTask(taskId: 't4', status: TaskStatus.failed),
      );

      final count = await taskDao.countActiveTasks();
      expect(count, 2);
    });

    test('returns 0 when no active tasks exist', () async {
      final count = await taskDao.countActiveTasks();
      expect(count, 0);
    });

    test('returns 0 when only completed and failed tasks exist', () async {
      await taskDao.insertTask(
        makeTask(taskId: 't1', status: TaskStatus.completed),
      );
      await taskDao.insertTask(
        makeTask(taskId: 't2', status: TaskStatus.failed),
      );

      final count = await taskDao.countActiveTasks();
      expect(count, 0);
    });

    test('updates count after completing a task', () async {
      await taskDao.insertTask(
        makeTask(taskId: 't1', status: TaskStatus.active),
      );
      await taskDao.insertTask(
        makeTask(taskId: 't2', status: TaskStatus.active),
      );

      expect(await taskDao.countActiveTasks(), 2);

      await taskDao.completeTask('t1', DateTime.now().toUtc());

      expect(await taskDao.countActiveTasks(), 1);
    });

    test('updates count after uncompleting a task', () async {
      await taskDao.insertTask(
        makeTask(taskId: 't1', status: TaskStatus.active),
      );
      await taskDao.insertTask(
        makeTask(taskId: 't2', status: TaskStatus.active),
      );
      await taskDao.completeTask('t2', DateTime.now().toUtc());

      expect(await taskDao.countActiveTasks(), 1);

      await taskDao.uncompleteTask('t2');

      expect(await taskDao.countActiveTasks(), 2);
    });
  });

  group('deleteTasksBySession', () {
    test('deletes all tasks for a session', () async {
      await taskDao.insertTask(makeTask(taskId: 't1', sessionId: 's1'));
      await taskDao.insertTask(makeTask(taskId: 't2', sessionId: 's1'));

      final deleted = await taskDao.deleteTasksBySession('s1');
      expect(deleted, 2);

      final t1 = await taskDao.getTaskById('t1');
      final t2 = await taskDao.getTaskById('t2');
      expect(t1, isNull);
      expect(t2, isNull);
    });

    test('does not affect tasks in other sessions', () async {
      await taskDao.insertTask(makeTask(taskId: 't1', sessionId: 's1'));
      await taskDao.insertTask(makeTask(taskId: 't2', sessionId: 's2'));

      await taskDao.deleteTasksBySession('s1');

      final t1 = await taskDao.getTaskById('t1');
      final t2 = await taskDao.getTaskById('t2');
      expect(t1, isNull);
      expect(t2, isNotNull);
    });

    test('returns 0 for session with no tasks', () async {
      final deleted = await taskDao.deleteTasksBySession('s1');
      expect(deleted, 0);
    });

    test('does not affect tasks with null sessionId', () async {
      await taskDao.insertTask(
        makeTask(taskId: 't1', sessionId: null, title: 'Standalone'),
      );
      await taskDao.insertTask(makeTask(taskId: 't2', sessionId: 's1'));

      await taskDao.deleteTasksBySession('s1');

      final standalone = await taskDao.getTaskById('t1');
      final sessionTask = await taskDao.getTaskById('t2');
      expect(standalone, isNotNull);
      expect(sessionTask, isNull);
    });

    test('deletes tasks of all statuses for the session', () async {
      await taskDao.insertTask(
        makeTask(taskId: 't1', sessionId: 's1', status: TaskStatus.active),
      );
      await taskDao.insertTask(
        makeTask(taskId: 't2', sessionId: 's1', status: TaskStatus.completed),
      );
      await taskDao.insertTask(
        makeTask(
          taskId: 't3',
          sessionId: 's1',
          status: TaskStatus.pendingCreate,
        ),
      );
      await taskDao.insertTask(
        makeTask(taskId: 't4', sessionId: 's1', status: TaskStatus.failed),
      );

      final deleted = await taskDao.deleteTasksBySession('s1');
      expect(deleted, 4);
    });
  });

  group('lifecycle transitions', () {
    test(
      'full lifecycle: PENDING_CREATE -> ACTIVE -> COMPLETED -> ACTIVE',
      () async {
        // Create task (defaults to PENDING_CREATE).
        await taskDao.insertTask(makeTask(taskId: 't1'));
        expect(
          (await taskDao.getTaskById('t1'))!.status,
          TaskStatus.pendingCreate,
        );

        // Sync to Google Tasks — promotes to ACTIVE.
        await taskDao.updateGoogleTaskId('t1', 'g-task', 'g-list');
        expect((await taskDao.getTaskById('t1'))!.status, TaskStatus.active);

        // User completes the task.
        final completedAt = DateTime.utc(2026, 2, 28, 12, 0);
        await taskDao.completeTask('t1', completedAt);
        final completed = await taskDao.getTaskById('t1');
        expect(completed!.status, TaskStatus.completed);
        expect(completed.completedAt, completedAt);

        // User uncompletes the task.
        await taskDao.uncompleteTask('t1');
        final uncompleted = await taskDao.getTaskById('t1');
        expect(uncompleted!.status, TaskStatus.active);
        expect(uncompleted.completedAt, isNull);
      },
    );

    test(
      'sync status transitions: PENDING -> SYNCED -> PENDING (on update)',
      () async {
        await taskDao.insertTask(makeTask(taskId: 't1'));
        expect(
          (await taskDao.getTaskById('t1'))!.syncStatus,
          TaskSyncStatus.pending,
        );

        // Mark as synced.
        await taskDao.updateSyncStatus('t1', TaskSyncStatus.synced);
        expect(
          (await taskDao.getTaskById('t1'))!.syncStatus,
          TaskSyncStatus.synced,
        );

        // Complete triggers re-sync (sets syncStatus back to PENDING).
        await taskDao.completeTask('t1', DateTime.utc(2026, 2, 28));
        expect(
          (await taskDao.getTaskById('t1'))!.syncStatus,
          TaskSyncStatus.pending,
        );
      },
    );

    test('sync status transitions: PENDING -> FAILED -> PENDING', () async {
      await taskDao.insertTask(makeTask(taskId: 't1'));

      // Sync fails.
      await taskDao.updateSyncStatus('t1', TaskSyncStatus.failed);
      expect(
        (await taskDao.getTaskById('t1'))!.syncStatus,
        TaskSyncStatus.failed,
      );

      // Retry resets to PENDING.
      await taskDao.updateSyncStatus('t1', TaskSyncStatus.pending);
      expect(
        (await taskDao.getTaskById('t1'))!.syncStatus,
        TaskSyncStatus.pending,
      );
    });
  });

  // Advisory A-2 from REV-20260304-074715: TaskDao notification cancellation
  // wiring must be tested with an injected mock/fake scheduler.
  group('notification cancellation wiring', () {
    late _FakeScheduler fakeScheduler;
    late TaskDao daoWithScheduler;

    setUp(() {
      fakeScheduler = _FakeScheduler();
      daoWithScheduler = TaskDao(database, scheduler: fakeScheduler);
    });

    test(
      'deleteTask cancels notification when task has a notificationId',
      () async {
        await daoWithScheduler.insertTask(
          makeTask(taskId: 't1').copyWith(
            reminderTime: Value(DateTime.now().add(const Duration(hours: 1))),
            notificationId: const Value(1042),
          ),
        );

        await daoWithScheduler.deleteTask('t1');

        expect(fakeScheduler.cancelledIds, contains(1042));
      },
    );

    test(
      'deleteTask is a no-op on notification when task has no notificationId',
      () async {
        await daoWithScheduler.insertTask(makeTask(taskId: 't1'));

        await daoWithScheduler.deleteTask('t1');

        // null is passed to cancelNotification, which is a no-op per contract.
        expect(fakeScheduler.cancelledIds, contains(null));
      },
    );

    test(
      'completeTask cancels notification when task has a notificationId',
      () async {
        await daoWithScheduler.insertTask(
          makeTask(taskId: 't1').copyWith(
            reminderTime: Value(DateTime.now().add(const Duration(hours: 1))),
            notificationId: const Value(1099),
          ),
        );

        await daoWithScheduler.completeTask('t1', DateTime.utc(2026, 3, 4));

        expect(fakeScheduler.cancelledIds, contains(1099));
      },
    );

    test('completeTask clears notificationId from the task row', () async {
      await daoWithScheduler.insertTask(
        makeTask(taskId: 't1').copyWith(notificationId: const Value(1099)),
      );

      await daoWithScheduler.completeTask('t1', DateTime.utc(2026, 3, 4));

      final completed = await daoWithScheduler.getTaskById('t1');
      expect(completed!.notificationId, isNull);
    });
  });

  // Advisory A-2 from REV-20260304-074715: getTasksWithPendingReminders query.
  group('getTasksWithPendingReminders', () {
    test(
      'returns tasks with future reminderTime and a notificationId',
      () async {
        final future = DateTime.now().add(const Duration(hours: 2));
        await taskDao.insertTask(
          makeTask(taskId: 't1').copyWith(
            reminderTime: Value(future),
            notificationId: const Value(1001),
          ),
        );

        final results = await taskDao.getTasksWithPendingReminders();

        expect(results.map((t) => t.taskId), contains('t1'));
      },
    );

    test('excludes tasks with past reminderTime', () async {
      final past = DateTime.now().subtract(const Duration(hours: 1));
      await taskDao.insertTask(
        makeTask(taskId: 't1').copyWith(
          reminderTime: Value(past),
          notificationId: const Value(1002),
        ),
      );

      final results = await taskDao.getTasksWithPendingReminders();

      expect(results.map((t) => t.taskId), isNot(contains('t1')));
    });

    test('excludes tasks with no notificationId', () async {
      await taskDao.insertTask(
        makeTask(taskId: 't1').copyWith(
          reminderTime: Value(DateTime.now().add(const Duration(hours: 1))),
        ),
      );

      final results = await taskDao.getTasksWithPendingReminders();

      expect(results.map((t) => t.taskId), isNot(contains('t1')));
    });

    test('excludes completed tasks', () async {
      await taskDao.insertTask(
        makeTask(taskId: 't1', status: TaskStatus.completed).copyWith(
          reminderTime: Value(DateTime.now().add(const Duration(hours: 1))),
          notificationId: const Value(1003),
        ),
      );

      final results = await taskDao.getTasksWithPendingReminders();

      expect(results.map((t) => t.taskId), isNot(contains('t1')));
    });
  });

  // Advisory A-2 from REV-20260304-074715 (blocking fix B2 from
  // REV-20260304-084207): updateNotificationId must persist the new OS alarm
  // ID after rescheduling. Without this, stale IDs remain in the database
  // across reboots.
  group('updateNotificationId', () {
    test('updates the notificationId column for an existing task', () async {
      await taskDao.insertTask(
        TasksCompanion(
          taskId: const Value('t-upd-notif'),
          sessionId: const Value('s1'),
          title: const Value('Update notif ID'),
          status: const Value(TaskStatus.active),
          syncStatus: const Value(TaskSyncStatus.pending),
          notificationId: const Value(1042),
          createdAt: Value(DateTime.now().toUtc()),
          updatedAt: Value(DateTime.now().toUtc()),
        ),
      );

      final rowsUpdated = await taskDao.updateNotificationId(
        't-upd-notif',
        2000,
      );

      expect(rowsUpdated, 1);
      final task = await taskDao.getTaskById('t-upd-notif');
      expect(task!.notificationId, 2000);
    });

    test('sets notificationId to null', () async {
      await taskDao.insertTask(
        TasksCompanion(
          taskId: const Value('t-upd-notif-null'),
          sessionId: const Value('s1'),
          title: const Value('Clear notif ID'),
          status: const Value(TaskStatus.active),
          syncStatus: const Value(TaskSyncStatus.pending),
          notificationId: const Value(1099),
          createdAt: Value(DateTime.now().toUtc()),
          updatedAt: Value(DateTime.now().toUtc()),
        ),
      );

      await taskDao.updateNotificationId('t-upd-notif-null', null);

      final task = await taskDao.getTaskById('t-upd-notif-null');
      expect(task!.notificationId, isNull);
    });

    test('returns 0 when task does not exist', () async {
      final rowsUpdated = await taskDao.updateNotificationId('no-such', 1000);
      expect(rowsUpdated, 0);
    });
  });
}
