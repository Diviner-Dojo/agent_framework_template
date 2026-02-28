// ===========================================================================
// file: lib/services/google_tasks_service.dart
// purpose: Google Tasks API client for CRUD operations on tasks.
//
// Pattern: Injectable callable (matches GoogleCalendarService).
//   Production code uses the real googleapis TasksApi. Tests inject fakes
//   without touching platform channels.
//
// Task list strategy: The app creates an "Agentic Journal" list in Google
//   Tasks to isolate from the user's personal task lists. The list ID is
//   cached in SharedPreferences to avoid repeated API calls.
//
// See: Phase 13 plan (Google Tasks + Personal Assistant)
// ===========================================================================

import 'package:flutter/foundation.dart';
import 'package:googleapis/tasks/v1.dart' as gtasks;
import 'package:googleapis_auth/googleapis_auth.dart' as googleapis_auth;
import 'package:shared_preferences/shared_preferences.dart';

/// SharedPreferences key for the cached task list ID.
const _taskListIdKey = 'google_tasks_list_id';

/// The name of the task list created in Google Tasks.
const _taskListName = 'Agentic Journal';

/// Result of a successful Google Tasks creation.
class TaskCreateResult {
  /// The Google Tasks task ID.
  final String googleTaskId;

  /// The Google Tasks task list ID.
  final String googleTaskListId;

  /// Create a [TaskCreateResult].
  const TaskCreateResult({
    required this.googleTaskId,
    required this.googleTaskListId,
  });
}

/// Typed error for Google Tasks API failures.
class GoogleTasksException implements Exception {
  final String message;
  const GoogleTasksException(this.message);

  @override
  String toString() => 'GoogleTasksException: $message';
}

/// Google Tasks API service for CRUD operations.
///
/// Manages the "Agentic Journal" task list and provides methods for
/// creating, completing, updating, and deleting tasks.
class GoogleTasksService {
  final gtasks.TasksApi _api;

  /// Create a GoogleTasksService with a Tasks API instance.
  GoogleTasksService._(this._api);

  /// Create a GoogleTasksService backed by a real Google Tasks API client.
  factory GoogleTasksService.withClient(googleapis_auth.AuthClient authClient) {
    final api = gtasks.TasksApi(authClient);
    return GoogleTasksService._(api);
  }

  /// Get or create the "Agentic Journal" task list.
  ///
  /// Checks SharedPreferences for a cached ID first. If not cached or
  /// the cached list no longer exists, searches existing lists or creates
  /// a new one. Caches the ID for future calls.
  Future<String> getOrCreateTaskList() async {
    // Check cache first.
    final prefs = await SharedPreferences.getInstance();
    final cachedId = prefs.getString(_taskListIdKey);
    if (cachedId != null) {
      // Verify the cached list still exists.
      try {
        await _api.tasklists.get(cachedId);
        return cachedId;
      } on gtasks.DetailedApiRequestError catch (e) {
        if (e.status == 404) {
          // Cached list was deleted — fall through to search/create.
          await prefs.remove(_taskListIdKey);
        } else {
          rethrow;
        }
      }
    }

    // Search existing lists.
    try {
      final lists = await _api.tasklists.list();
      final existing = lists.items?.firstWhere(
        (l) => l.title == _taskListName,
        orElse: () => gtasks.TaskList(),
      );
      if (existing?.id != null && existing!.id!.isNotEmpty) {
        await prefs.setString(_taskListIdKey, existing.id!);
        return existing.id!;
      }
    } on Exception catch (e) {
      if (kDebugMode) {
        debugPrint('Failed to list task lists: $e');
      }
    }

    // Create new list.
    try {
      final newList = await _api.tasklists.insert(
        gtasks.TaskList(title: _taskListName),
      );
      final id = newList.id;
      if (id == null || id.isEmpty) {
        throw const GoogleTasksException(
          'Google Tasks returned a list without an ID',
        );
      }
      await prefs.setString(_taskListIdKey, id);
      return id;
    } on gtasks.DetailedApiRequestError catch (e) {
      throw GoogleTasksException('Google Tasks API error (HTTP ${e.status})');
    }
  }

  /// Create a task in Google Tasks.
  Future<TaskCreateResult> createTask({
    required String title,
    String? notes,
    DateTime? dueDate,
    String? taskListId,
  }) async {
    final listId = taskListId ?? await getOrCreateTaskList();

    final task = gtasks.Task(
      title: title,
      notes: notes,
      due: dueDate?.toUtc().toIso8601String(),
    );

    try {
      final created = await _api.tasks.insert(task, listId);
      final taskId = created.id;
      if (taskId == null || taskId.isEmpty) {
        throw const GoogleTasksException(
          'Google Tasks returned a task without an ID',
        );
      }
      return TaskCreateResult(googleTaskId: taskId, googleTaskListId: listId);
    } on gtasks.DetailedApiRequestError catch (e) {
      if (kDebugMode) {
        debugPrint('Google Tasks API detail: ${e.message}');
      }
      throw GoogleTasksException('Google Tasks API error (HTTP ${e.status})');
    } on Exception catch (e) {
      if (kDebugMode) {
        debugPrint('GoogleTasksService.createTask failed: $e');
      }
      throw const GoogleTasksException('Failed to create task');
    }
  }

  /// Mark a task as completed in Google Tasks.
  Future<void> completeTask({
    required String googleTaskId,
    required String taskListId,
  }) async {
    try {
      final task = gtasks.Task(
        status: 'completed',
        completed: DateTime.now().toUtc().toIso8601String(),
      );
      await _api.tasks.patch(task, taskListId, googleTaskId);
    } on gtasks.DetailedApiRequestError catch (e) {
      throw GoogleTasksException('Google Tasks API error (HTTP ${e.status})');
    } on Exception catch (e) {
      if (kDebugMode) {
        debugPrint('GoogleTasksService.completeTask failed: $e');
      }
      throw const GoogleTasksException('Failed to complete task');
    }
  }

  /// Update a task in Google Tasks (partial update via patch).
  Future<void> updateTask({
    required String googleTaskId,
    required String taskListId,
    String? title,
    String? notes,
    DateTime? dueDate,
  }) async {
    try {
      final task = gtasks.Task(
        title: title,
        notes: notes,
        due: dueDate?.toUtc().toIso8601String(),
      );
      await _api.tasks.patch(task, taskListId, googleTaskId);
    } on gtasks.DetailedApiRequestError catch (e) {
      throw GoogleTasksException('Google Tasks API error (HTTP ${e.status})');
    } on Exception catch (e) {
      if (kDebugMode) {
        debugPrint('GoogleTasksService.updateTask failed: $e');
      }
      throw const GoogleTasksException('Failed to update task');
    }
  }

  /// Delete a task from Google Tasks.
  Future<void> deleteTask({
    required String googleTaskId,
    required String taskListId,
  }) async {
    try {
      await _api.tasks.delete(taskListId, googleTaskId);
    } on gtasks.DetailedApiRequestError catch (e) {
      throw GoogleTasksException('Google Tasks API error (HTTP ${e.status})');
    } on Exception catch (e) {
      if (kDebugMode) {
        debugPrint('GoogleTasksService.deleteTask failed: $e');
      }
      throw const GoogleTasksException('Failed to delete task');
    }
  }
}
