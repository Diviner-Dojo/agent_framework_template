// ===========================================================================
// file: lib/database/daos/task_dao.dart
// purpose: Data Access Object for Tasks table (Phase 13).
//
// Pattern: Constructor-injected DAO (same as CalendarEventDao, SessionDao).
// Receives the AppDatabase instance via constructor for testability.
//
// Lifecycle states (status column):
//   PENDING_CREATE → ACTIVE (confirmed / synced)
//   ACTIVE → COMPLETED (user marked done)
//   COMPLETED → ACTIVE (user uncompleted)
//   PENDING_CREATE → FAILED (sync error)
//
// Sync states (syncStatus column) — independent from lifecycle:
//   PENDING → SYNCED (on successful Google Tasks API call)
//   PENDING → FAILED (on sync error)
// ===========================================================================

import 'package:drift/drift.dart';

import '../app_database.dart';

/// Typed constants for the task lifecycle status column.
abstract final class TaskStatus {
  static const pendingCreate = 'PENDING_CREATE';
  static const active = 'ACTIVE';
  static const completed = 'COMPLETED';
  static const failed = 'FAILED';
}

/// Typed constants for the task sync status column.
abstract final class TaskSyncStatus {
  static const pending = 'PENDING';
  static const synced = 'SYNCED';
  static const failed = 'FAILED';
}

/// Data Access Object for tasks.
///
/// Provides CRUD operations and reactive streams for the Tasks table.
class TaskDao {
  final AppDatabase _db;

  /// Create a TaskDao with the given database.
  TaskDao(this._db);

  /// Insert a new task.
  Future<void> insertTask(TasksCompanion task) {
    return _db.into(_db.tasks).insert(task);
  }

  /// Get a single task by ID.
  Future<Task?> getTaskById(String taskId) {
    return (_db.select(
      _db.tasks,
    )..where((t) => t.taskId.equals(taskId))).getSingleOrNull();
  }

  /// Update an existing task.
  Future<int> updateTask(String taskId, TasksCompanion companion) {
    return (_db.update(
      _db.tasks,
    )..where((t) => t.taskId.equals(taskId))).write(companion);
  }

  /// Delete a single task.
  Future<int> deleteTask(String taskId) {
    return (_db.delete(_db.tasks)..where((t) => t.taskId.equals(taskId))).go();
  }

  /// Watch all tasks ordered by creation time (newest first).
  Stream<List<Task>> watchAllTasks() {
    return (_db.select(
      _db.tasks,
    )..orderBy([(t) => OrderingTerm.desc(t.createdAt)])).watch();
  }

  /// Watch active (non-completed) tasks ordered by due date, then creation.
  Stream<List<Task>> watchActiveTasks() {
    return (_db.select(_db.tasks)
          ..where(
            (t) =>
                t.status.equals(TaskStatus.active) |
                t.status.equals(TaskStatus.pendingCreate),
          )
          ..orderBy([
            (t) => OrderingTerm.asc(t.dueDate),
            (t) => OrderingTerm.desc(t.createdAt),
          ]))
        .watch();
  }

  /// Watch completed tasks ordered by completion time (newest first).
  Stream<List<Task>> watchCompletedTasks() {
    return (_db.select(_db.tasks)
          ..where((t) => t.status.equals(TaskStatus.completed))
          ..orderBy([(t) => OrderingTerm.desc(t.completedAt)]))
        .watch();
  }

  /// Get tasks due today (local date comparison).
  Future<List<Task>> getTasksDueToday() async {
    final now = DateTime.now();
    final startOfDay = DateTime(now.year, now.month, now.day);
    final endOfDay = startOfDay.add(const Duration(days: 1));

    return (_db.select(_db.tasks)
          ..where(
            (t) =>
                t.dueDate.isBiggerOrEqualValue(startOfDay) &
                t.dueDate.isSmallerThanValue(endOfDay) &
                t.status.isNotIn([TaskStatus.completed]),
          )
          ..orderBy([(t) => OrderingTerm.asc(t.dueDate)]))
        .get();
  }

  /// Get tasks due tomorrow (local date comparison).
  Future<List<Task>> getTasksDueTomorrow() async {
    final now = DateTime.now();
    final startOfTomorrow = DateTime(now.year, now.month, now.day + 1);
    final endOfTomorrow = startOfTomorrow.add(const Duration(days: 1));

    return (_db.select(_db.tasks)
          ..where(
            (t) =>
                t.dueDate.isBiggerOrEqualValue(startOfTomorrow) &
                t.dueDate.isSmallerThanValue(endOfTomorrow) &
                t.status.isNotIn([TaskStatus.completed]),
          )
          ..orderBy([(t) => OrderingTerm.asc(t.dueDate)]))
        .get();
  }

  /// Mark a task as completed.
  Future<int> completeTask(String taskId, DateTime completedAt) {
    return (_db.update(_db.tasks)..where((t) => t.taskId.equals(taskId))).write(
      TasksCompanion(
        status: const Value(TaskStatus.completed),
        completedAt: Value(completedAt),
        syncStatus: const Value(TaskSyncStatus.pending),
        updatedAt: Value(DateTime.now().toUtc()),
      ),
    );
  }

  /// Mark a completed task as active again (uncomplete).
  Future<int> uncompleteTask(String taskId) {
    return (_db.update(_db.tasks)..where((t) => t.taskId.equals(taskId))).write(
      TasksCompanion(
        status: const Value(TaskStatus.active),
        completedAt: const Value(null),
        syncStatus: const Value(TaskSyncStatus.pending),
        updatedAt: Value(DateTime.now().toUtc()),
      ),
    );
  }

  /// Get tasks that need syncing to Google Tasks.
  Future<List<Task>> getTasksToSync() {
    return (_db.select(_db.tasks)..where(
          (t) =>
              t.status.isIn([TaskStatus.active, TaskStatus.completed]) &
              t.syncStatus.isNotIn([TaskSyncStatus.synced]),
        ))
        .get();
  }

  /// Set the Google Task ID after successful creation.
  Future<int> updateGoogleTaskId(
    String taskId,
    String googleTaskId,
    String googleTaskListId,
  ) {
    return (_db.update(_db.tasks)..where((t) => t.taskId.equals(taskId))).write(
      TasksCompanion(
        googleTaskId: Value(googleTaskId),
        googleTaskListId: Value(googleTaskListId),
        status: const Value(TaskStatus.active),
        syncStatus: const Value(TaskSyncStatus.synced),
        updatedAt: Value(DateTime.now().toUtc()),
      ),
    );
  }

  /// Update the sync status of a task.
  Future<int> updateSyncStatus(String taskId, String syncStatus) {
    return (_db.update(_db.tasks)..where((t) => t.taskId.equals(taskId))).write(
      TasksCompanion(
        syncStatus: Value(syncStatus),
        updatedAt: Value(DateTime.now().toUtc()),
      ),
    );
  }

  /// Count all active (non-completed) tasks.
  Future<int> countActiveTasks() async {
    final count = _db.tasks.taskId.count();
    final query = _db.selectOnly(_db.tasks)
      ..addColumns([count])
      ..where(
        _db.tasks.status.isIn([TaskStatus.active, TaskStatus.pendingCreate]),
      );
    final result = await query.getSingle();
    return result.read(count) ?? 0;
  }

  /// Delete all tasks for a session (cascade delete support).
  Future<int> deleteTasksBySession(String sessionId) {
    return (_db.delete(
      _db.tasks,
    )..where((t) => t.sessionId.equals(sessionId))).go();
  }
}
