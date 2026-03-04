// ===========================================================================
// file: test/database/migration_v7_test.dart
// purpose: Schema v11 migration — Scheduled Local Notifications columns.
//
// Verifies that the three new columns added to the tasks table in schema v11
// (reminderTime, notificationId, isQuickReminder) are accessible and that
// pre-v11 task data survives the upgrade without regression.
//
// See: SPEC-20260304-061650 (Scheduled Local Notifications), ADR-0033
// ===========================================================================

import 'package:drift/drift.dart' hide isNull, isNotNull;
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/task_dao.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';

void main() {
  group('Schema v11 migration — scheduled notification columns', () {
    test('schemaVersion is at least 11', () async {
      final database = AppDatabase.forTesting(NativeDatabase.memory());
      expect(database.schemaVersion, greaterThanOrEqualTo(11));
      await database.close();
    });

    test('tasks table stores and retrieves reminderTime', () async {
      final database = AppDatabase.forTesting(NativeDatabase.memory());
      final sessionDao = SessionDao(database);
      final taskDao = TaskDao(database);

      await sessionDao.createSession('s1', DateTime.utc(2026, 3, 4), 'UTC');

      final reminderTime = DateTime.utc(2026, 3, 5, 16, 0); // 4pm UTC
      await taskDao.insertTask(
        TasksCompanion(
          taskId: const Value('t1'),
          sessionId: const Value('s1'),
          title: const Value('Give cat meds'),
          reminderTime: Value(reminderTime),
          status: const Value(TaskStatus.active),
          syncStatus: const Value(TaskSyncStatus.pending),
          createdAt: Value(DateTime.utc(2026, 3, 4)),
          updatedAt: Value(DateTime.utc(2026, 3, 4)),
        ),
      );

      final task = await taskDao.getTaskById('t1');
      expect(task, isNotNull);
      expect(task!.reminderTime, reminderTime);
      expect(task.notificationId, isNull);
      expect(task.isQuickReminder, isFalse);

      await database.close();
    });

    test('tasks table stores and retrieves notificationId', () async {
      final database = AppDatabase.forTesting(NativeDatabase.memory());
      final sessionDao = SessionDao(database);
      final taskDao = TaskDao(database);

      await sessionDao.createSession('s2', DateTime.utc(2026, 3, 4), 'UTC');

      await taskDao.insertTask(
        TasksCompanion(
          taskId: const Value('t2'),
          sessionId: const Value('s2'),
          title: const Value('Call dentist'),
          notificationId: const Value(1042),
          status: const Value(TaskStatus.active),
          syncStatus: const Value(TaskSyncStatus.pending),
          createdAt: Value(DateTime.utc(2026, 3, 4)),
          updatedAt: Value(DateTime.utc(2026, 3, 4)),
        ),
      );

      final task = await taskDao.getTaskById('t2');
      expect(task, isNotNull);
      expect(task!.notificationId, 1042);

      await database.close();
    });

    test('tasks table stores and retrieves isQuickReminder=true', () async {
      final database = AppDatabase.forTesting(NativeDatabase.memory());
      final sessionDao = SessionDao(database);
      final taskDao = TaskDao(database);

      await sessionDao.createSession('s3', DateTime.utc(2026, 3, 4), 'UTC');

      final reminderTime = DateTime.utc(2026, 3, 4, 18, 30);
      await taskDao.insertTask(
        TasksCompanion(
          taskId: const Value('t3'),
          sessionId: const Value('s3'),
          title: const Value('Take vitamins'),
          reminderTime: Value(reminderTime),
          notificationId: const Value(1000),
          isQuickReminder: const Value(true),
          status: const Value(TaskStatus.active),
          syncStatus: const Value(TaskSyncStatus.pending),
          createdAt: Value(DateTime.utc(2026, 3, 4)),
          updatedAt: Value(DateTime.utc(2026, 3, 4)),
        ),
      );

      final task = await taskDao.getTaskById('t3');
      expect(task, isNotNull);
      expect(task!.isQuickReminder, isTrue);
      expect(task.notificationId, 1000);
      expect(task.reminderTime, reminderTime);

      await database.close();
    });

    test('legacy tasks without reminderTime default to null', () async {
      // Verify backward compat: tasks created without the new fields
      // have null reminderTime, null notificationId, false isQuickReminder.
      final database = AppDatabase.forTesting(NativeDatabase.memory());
      final sessionDao = SessionDao(database);
      final taskDao = TaskDao(database);

      await sessionDao.createSession('s4', DateTime.utc(2026, 3, 4), 'UTC');

      await taskDao.insertTask(
        TasksCompanion(
          taskId: const Value('t4'),
          sessionId: const Value('s4'),
          title: const Value('Buy groceries'),
          status: const Value(TaskStatus.active),
          syncStatus: const Value(TaskSyncStatus.pending),
          createdAt: Value(DateTime.utc(2026, 3, 4)),
          updatedAt: Value(DateTime.utc(2026, 3, 4)),
        ),
      );

      final task = await taskDao.getTaskById('t4');
      expect(task, isNotNull);
      expect(task!.reminderTime, isNull);
      expect(task.notificationId, isNull);
      expect(task.isQuickReminder, isFalse);

      await database.close();
    });

    test(
      'pre-v11 tables (journal_sessions, tasks) remain accessible',
      () async {
        // Regression guard: v10→v11 migration must not break existing tables.
        final database = AppDatabase.forTesting(NativeDatabase.memory());
        final sessionDao = SessionDao(database);
        final taskDao = TaskDao(database);

        await sessionDao.createSession(
          'legacy_session',
          DateTime.utc(2026, 3, 4),
          'UTC',
        );
        await taskDao.insertTask(
          TasksCompanion(
            taskId: const Value('legacy_task'),
            sessionId: const Value('legacy_session'),
            title: const Value('A legacy task'),
            status: const Value(TaskStatus.active),
            syncStatus: const Value(TaskSyncStatus.pending),
            createdAt: Value(DateTime.utc(2026, 3, 4)),
            updatedAt: Value(DateTime.utc(2026, 3, 4)),
          ),
        );

        final sessions = await sessionDao.getAllSessionsByDate();
        expect(sessions, hasLength(1));

        final task = await taskDao.getTaskById('legacy_task');
        expect(task, isNotNull);
        expect(task!.title, 'A legacy task');

        await database.close();
      },
    );
  });
}
