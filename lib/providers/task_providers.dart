// ===========================================================================
// file: lib/providers/task_providers.dart
// purpose: Riverpod providers for Google Tasks integration.
//
// Follows the pattern of calendar_providers.dart — providers manage
// service instances, connection state, and user preferences.
//
// See: Phase 13 plan (Google Tasks + Personal Assistant)
// ===========================================================================

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../services/task_extraction_service.dart';
import 'database_provider.dart';
import 'session_providers.dart';

/// SharedPreferences key for the task auto-suggest toggle.
const _taskAutoSuggestKey = 'task_auto_suggest';

/// Whether the AI should auto-suggest tasks from conversation.
///
/// Default: true (on). When off, the intent classifier still runs but
/// task intents are not surfaced to the user.
final taskAutoSuggestProvider =
    StateNotifierProvider<TaskAutoSuggestNotifier, bool>((ref) {
      return TaskAutoSuggestNotifier();
    });

/// Manages the task auto-suggest preference.
class TaskAutoSuggestNotifier extends StateNotifier<bool> {
  TaskAutoSuggestNotifier() : super(true) {
    _load();
  }

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    state = prefs.getBool(_taskAutoSuggestKey) ?? true;
  }

  /// Toggle auto-suggest on/off.
  Future<void> setEnabled(bool value) async {
    state = value;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_taskAutoSuggestKey, value);
  }
}

/// Provides the count of active (non-completed) tasks.
///
/// Used by the session list screen to show the tasks icon.
final taskCountProvider = FutureProvider<int>((ref) async {
  final taskDao = ref.watch(taskDaoProvider);
  return taskDao.countActiveTasks();
});

/// Streams all tasks (for the Tasks screen "All" view).
final allTasksStreamProvider = StreamProvider<List>((ref) {
  final taskDao = ref.watch(taskDaoProvider);
  return taskDao.watchAllTasks();
});

/// Streams active (non-completed) tasks.
final activeTasksStreamProvider = StreamProvider<List>((ref) {
  final taskDao = ref.watch(taskDaoProvider);
  return taskDao.watchActiveTasks();
});

/// Streams completed tasks.
final completedTasksStreamProvider = StreamProvider<List>((ref) {
  final taskDao = ref.watch(taskDaoProvider);
  return taskDao.watchCompletedTasks();
});

/// Provides the TaskExtractionService for parsing task details
/// from natural language.
final taskExtractionServiceProvider = Provider<TaskExtractionService>((ref) {
  final claudeApi = ref.watch(claudeApiServiceProvider);
  return TaskExtractionService(claudeApi: claudeApi);
});
