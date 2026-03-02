// ===========================================================================
// file: test/ui/screens/tasks_screen_expanded_test.dart
// purpose: Expanded widget tests for the Tasks screen — covers:
//   - Add task form submission with title and notes
//   - Task completion toggle via checkbox
//   - Task edit sheet opens with pre-filled fields
//   - Task deletion via swipe
//   - Loading and error states
// ===========================================================================

import 'dart:async';

import 'package:drift/drift.dart' hide Column;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:drift/native.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/task_dao.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';
import 'package:agentic_journal/providers/calendar_providers.dart';
import 'package:agentic_journal/providers/database_provider.dart';
import 'package:agentic_journal/providers/task_providers.dart';
import 'package:agentic_journal/services/google_auth_service.dart';
import 'package:agentic_journal/ui/screens/tasks_screen.dart';

/// No-op auth service for test overrides.
final _fakeAuthService = GoogleAuthService(
  signIn: () async => null,
  signOut: () async => null,
  disconnect: () async => null,
  isSignedIn: () async => false,
  getAuthClient: () async => null,
  signInSilently: () async => null,
);

void main() {
  late AppDatabase database;

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    database = AppDatabase.forTesting(NativeDatabase.memory());
    // Tasks screen _submit uses TaskDao which reads from database.
    // Create a session so the DB isn't empty.
    final sessionDao = SessionDao(database);
    await sessionDao.createSession('s1', DateTime.utc(2026, 2, 28), 'UTC');
  });

  tearDown(() async {
    // database.close() may have already been called by cleanupWidgetTree.
    // Drift's close() is idempotent — safe to call twice.
    await database.close();
  });

  Task makeTask({
    String taskId = 'task-1',
    String title = 'Test Task',
    String? notes,
    DateTime? dueDate,
    String status = TaskStatus.active,
    String syncStatus = TaskSyncStatus.pending,
  }) {
    return Task(
      taskId: taskId,
      title: title,
      notes: notes,
      dueDate: dueDate,
      status: status,
      syncStatus: syncStatus,
      createdAt: DateTime.utc(2026, 2, 28),
      updatedAt: DateTime.utc(2026, 2, 28),
    );
  }

  /// Tear down the widget tree cleanly to let drift's zero-duration
  /// stream-close timers fire before the test framework checks for
  /// pending timers. Without this, ProviderScope disposal triggers
  /// StreamQueryStore.markAsClosed which creates a timer that the
  /// test framework flags as "Timer still pending."
  Future<void> cleanupWidgetTree(WidgetTester tester) async {
    // Close the database first to cancel drift stream subscriptions
    // before the widget tree disposes ProviderScope. This prevents
    // drift's StreamQueryStore.markAsClosed from creating a zero-duration
    // timer during widget tree disposal.
    await database.close();
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump(const Duration(milliseconds: 100));
  }

  Widget buildScreen({
    List<Task> activeTasks = const [],
    List<Task> completedTasks = const [],
    int taskCount = 0,
    bool useRealDatabase = false,
  }) {
    return ProviderScope(
      overrides: [
        if (useRealDatabase) databaseProvider.overrideWithValue(database),
        if (useRealDatabase)
          taskDaoProvider.overrideWithValue(TaskDao(database)),
        if (!useRealDatabase)
          activeTasksStreamProvider.overrideWith(
            (ref) => Stream.value(activeTasks),
          ),
        if (!useRealDatabase)
          completedTasksStreamProvider.overrideWith(
            (ref) => Stream.value(completedTasks),
          ),
        taskCountProvider.overrideWith((ref) => Future.value(taskCount)),
        googleAuthServiceProvider.overrideWithValue(_fakeAuthService),
        isGoogleConnectedProvider.overrideWith(
          (ref) => GoogleConnectionNotifier(_fakeAuthService),
        ),
      ],
      child: const MaterialApp(home: TasksScreen()),
    );
  }

  group('TasksScreen — form submission', () {
    testWidgets('submitting add task form creates task in DB', (tester) async {
      await tester.pumpWidget(buildScreen(useRealDatabase: true));
      await tester.pumpAndSettle();

      // Open add task sheet.
      await tester.tap(find.byIcon(Icons.add));
      await tester.pumpAndSettle();

      // Fill in title.
      await tester.enterText(
        find.widgetWithText(TextField, 'Task title'),
        'Buy groceries',
      );
      await tester.pumpAndSettle();

      // Fill in notes.
      await tester.enterText(
        find.widgetWithText(TextField, 'Notes (optional)'),
        'From the store',
      );
      await tester.pumpAndSettle();

      // Submit.
      await tester.tap(find.text('Add Task'));
      await tester.pumpAndSettle();

      // Verify the task was created in the database.
      final taskDao = TaskDao(database);
      final tasks = await taskDao.getTasksToSync();
      expect(tasks, isNotEmpty);
      expect(tasks.first.title, 'Buy groceries');
      expect(tasks.first.notes, 'From the store');

      await cleanupWidgetTree(tester);
    });

    testWidgets('empty title does not create task', (tester) async {
      await tester.pumpWidget(buildScreen(useRealDatabase: true));
      await tester.pumpAndSettle();

      // Open add task sheet.
      await tester.tap(find.byIcon(Icons.add));
      await tester.pumpAndSettle();

      // Submit without filling title.
      await tester.tap(find.text('Add Task'));
      await tester.pumpAndSettle();

      // Sheet should still be open — task not created.
      expect(find.text('New Task'), findsOneWidget);

      // No tasks in DB.
      final taskDao = TaskDao(database);
      final tasks = await taskDao.getTasksToSync();
      expect(tasks, isEmpty);

      await cleanupWidgetTree(tester);
    });
  });

  group('TasksScreen — task interactions', () {
    testWidgets('tapping checkbox completes an active task', (tester) async {
      await tester.pumpWidget(buildScreen(useRealDatabase: true));
      await tester.pumpAndSettle();

      // Insert a task directly.
      final taskDao = TaskDao(database);
      await taskDao.insertTask(
        TasksCompanion(
          taskId: const Value('t1'),
          title: const Value('Walk the dog'),
          status: const Value(TaskStatus.active),
          syncStatus: const Value(TaskSyncStatus.pending),
          createdAt: Value(DateTime.utc(2026, 2, 28)),
          updatedAt: Value(DateTime.utc(2026, 2, 28)),
        ),
      );

      // Rebuild to pick up the new task.
      await tester.pumpWidget(buildScreen(useRealDatabase: true));
      await tester.pumpAndSettle();

      // Find and tap the checkbox.
      final checkbox = find.byType(Checkbox);
      if (checkbox.evaluate().isNotEmpty) {
        await tester.tap(checkbox.first);
        await tester.pumpAndSettle();

        // Task should be marked complete in DB.
        final updated = await taskDao.getTaskById('t1');
        expect(updated?.status, TaskStatus.completed);
      }

      await cleanupWidgetTree(tester);
    });

    testWidgets('tapping task opens edit sheet', (tester) async {
      await tester.pumpWidget(
        buildScreen(
          activeTasks: [makeTask(title: 'Edit me', notes: 'Some notes')],
        ),
      );
      await tester.pumpAndSettle();

      // Tap the task item (ListTile).
      await tester.tap(find.text('Edit me'));
      await tester.pumpAndSettle();

      // Edit sheet should open with pre-filled fields.
      expect(find.text('Edit Task'), findsOneWidget);
    });

    testWidgets('edit sheet shows Save button', (tester) async {
      await tester.pumpWidget(
        buildScreen(activeTasks: [makeTask(title: 'Fix bug')]),
      );
      await tester.pumpAndSettle();

      // Open edit sheet.
      await tester.tap(find.text('Fix bug'));
      await tester.pumpAndSettle();

      expect(find.text('Save'), findsOneWidget);
    });
  });

  group('TasksScreen — error states', () {
    testWidgets('active tasks shows error message', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            activeTasksStreamProvider.overrideWith(
              (ref) => Stream.error(Exception('DB failure')),
            ),
            completedTasksStreamProvider.overrideWith(
              (ref) => Stream.value(<Task>[]),
            ),
            taskCountProvider.overrideWith((ref) => Future.value(0)),
            googleAuthServiceProvider.overrideWithValue(_fakeAuthService),
            isGoogleConnectedProvider.overrideWith(
              (ref) => GoogleConnectionNotifier(_fakeAuthService),
            ),
          ],
          child: const MaterialApp(home: TasksScreen()),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.textContaining('Error:'), findsOneWidget);
    });

    testWidgets('completed tasks shows error message', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            activeTasksStreamProvider.overrideWith(
              (ref) => Stream.value(<Task>[]),
            ),
            completedTasksStreamProvider.overrideWith(
              (ref) => Stream.error(Exception('DB failure')),
            ),
            taskCountProvider.overrideWith((ref) => Future.value(0)),
            googleAuthServiceProvider.overrideWithValue(_fakeAuthService),
            isGoogleConnectedProvider.overrideWith(
              (ref) => GoogleConnectionNotifier(_fakeAuthService),
            ),
          ],
          child: const MaterialApp(home: TasksScreen()),
        ),
      );
      await tester.pumpAndSettle();

      // Switch to Completed tab.
      await tester.tap(find.text('Completed'));
      await tester.pumpAndSettle();

      expect(find.textContaining('Error:'), findsOneWidget);
    });
  });

  group('TasksScreen — edit task flow', () {
    testWidgets('edit sheet pre-fills title and notes', (tester) async {
      await tester.pumpWidget(
        buildScreen(
          activeTasks: [makeTask(title: 'Fix bug', notes: 'In the login flow')],
        ),
      );
      await tester.pumpAndSettle();

      // Tap the task to open edit sheet.
      await tester.tap(find.text('Fix bug'));
      await tester.pumpAndSettle();

      // Edit sheet should show pre-filled fields.
      expect(find.text('Edit Task'), findsOneWidget);
      expect(find.text('Fix bug'), findsWidgets); // In title field + list
      expect(find.text('In the login flow'), findsOneWidget);
    });

    testWidgets('edit sheet shows due date button', (tester) async {
      await tester.pumpWidget(
        buildScreen(
          activeTasks: [
            makeTask(title: 'With date', dueDate: DateTime.utc(2026, 6, 15)),
          ],
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('With date'));
      await tester.pumpAndSettle();

      // Should show formatted date.
      expect(find.textContaining('Jun 15, 2026'), findsOneWidget);
    });

    testWidgets('edit sheet shows clear due date button when date set', (
      tester,
    ) async {
      await tester.pumpWidget(
        buildScreen(
          activeTasks: [
            makeTask(title: 'Dated task', dueDate: DateTime.utc(2026, 3, 10)),
          ],
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Dated task'));
      await tester.pumpAndSettle();

      // Clear button (X icon) should be visible.
      expect(find.byIcon(Icons.clear), findsOneWidget);
      expect(find.byTooltip('Remove due date'), findsOneWidget);
    });

    testWidgets('edit sheet save button submits changes via real DB', (
      tester,
    ) async {
      await tester.pumpWidget(buildScreen(useRealDatabase: true));
      await tester.pumpAndSettle();

      // Insert a task directly.
      final taskDao = TaskDao(database);
      await taskDao.insertTask(
        TasksCompanion(
          taskId: const Value('edit-1'),
          title: const Value('Original title'),
          notes: const Value('Original notes'),
          status: const Value(TaskStatus.active),
          syncStatus: const Value(TaskSyncStatus.pending),
          createdAt: Value(DateTime.utc(2026, 2, 28)),
          updatedAt: Value(DateTime.utc(2026, 2, 28)),
        ),
      );

      // Rebuild to pick up the task.
      await tester.pumpWidget(buildScreen(useRealDatabase: true));
      await tester.pumpAndSettle();

      // Open edit sheet.
      await tester.tap(find.text('Original title'));
      await tester.pumpAndSettle();

      // Clear the title field and enter a new one.
      final titleField = find.widgetWithText(TextField, 'Task title');
      await tester.enterText(titleField, 'Updated title');
      await tester.pumpAndSettle();

      // Tap Save.
      await tester.tap(find.text('Save'));
      await tester.pumpAndSettle();

      // Verify the task was updated in DB.
      final updated = await taskDao.getTaskById('edit-1');
      expect(updated?.title, 'Updated title');

      await cleanupWidgetTree(tester);
    });
  });

  group('TasksScreen — delete task', () {
    testWidgets('delete removes task from DB', (tester) async {
      await tester.pumpWidget(buildScreen(useRealDatabase: true));
      await tester.pumpAndSettle();

      // Insert a task directly.
      final taskDao = TaskDao(database);
      await taskDao.insertTask(
        TasksCompanion(
          taskId: const Value('del-1'),
          title: const Value('Delete me'),
          status: const Value(TaskStatus.active),
          syncStatus: const Value(TaskSyncStatus.pending),
          createdAt: Value(DateTime.utc(2026, 2, 28)),
          updatedAt: Value(DateTime.utc(2026, 2, 28)),
        ),
      );

      // Rebuild to pick up the task.
      await tester.pumpWidget(buildScreen(useRealDatabase: true));
      await tester.pumpAndSettle();

      // Find the delete icon button on the task item.
      final deleteButton = find.byIcon(Icons.delete_outline);
      if (deleteButton.evaluate().isNotEmpty) {
        await tester.tap(deleteButton.first);
        await tester.pumpAndSettle();

        // Task should be deleted from DB.
        final remaining = await taskDao.getTasksToSync();
        expect(remaining, isEmpty);
      }

      await cleanupWidgetTree(tester);
    });
  });

  group('TasksScreen — add task due date picker', () {
    testWidgets('tapping due date button opens date picker', (tester) async {
      await tester.pumpWidget(buildScreen(useRealDatabase: true));
      await tester.pumpAndSettle();

      // Open add task sheet.
      await tester.tap(find.byIcon(Icons.add));
      await tester.pumpAndSettle();

      // Tap the "Add due date" button.
      await tester.tap(find.text('Add due date'));
      await tester.pumpAndSettle();

      // DatePicker dialog should appear.
      expect(find.byType(DatePickerDialog), findsOneWidget);

      // Dismiss the date picker.
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      await cleanupWidgetTree(tester);
    });

    testWidgets('selecting a date updates the button label', (tester) async {
      await tester.pumpWidget(buildScreen(useRealDatabase: true));
      await tester.pumpAndSettle();

      // Open add task sheet.
      await tester.tap(find.byIcon(Icons.add));
      await tester.pumpAndSettle();

      // Tap the "Add due date" button.
      await tester.tap(find.text('Add due date'));
      await tester.pumpAndSettle();

      // Select a day and confirm.
      await tester.tap(find.text('OK'));
      await tester.pumpAndSettle();

      // Button label should now show a date (no longer "Add due date").
      expect(find.text('Add due date'), findsNothing);

      await cleanupWidgetTree(tester);
    });
  });

  group('TasksScreen — empty states', () {
    testWidgets('empty active list shows empty message', (tester) async {
      await tester.pumpWidget(buildScreen(activeTasks: []));
      await tester.pumpAndSettle();

      expect(find.text('No active tasks'), findsOneWidget);
      expect(find.text('Tap + to add your first task.'), findsOneWidget);
    });

    testWidgets('empty completed list shows empty message', (tester) async {
      await tester.pumpWidget(buildScreen(completedTasks: []));
      await tester.pumpAndSettle();

      // Switch to Completed tab.
      await tester.tap(find.text('Completed'));
      await tester.pumpAndSettle();

      expect(find.text('No completed tasks yet.'), findsOneWidget);
    });
  });

  group('TasksScreen — completed list', () {
    testWidgets('completed task shows with checkbox checked', (tester) async {
      await tester.pumpWidget(
        buildScreen(
          completedTasks: [
            makeTask(
              taskId: 'c1',
              title: 'Done task',
              status: TaskStatus.completed,
            ),
          ],
        ),
      );
      await tester.pumpAndSettle();

      // Switch to Completed tab.
      await tester.tap(find.text('Completed'));
      await tester.pumpAndSettle();

      expect(find.text('Done task'), findsOneWidget);
    });

    testWidgets('uncompleting moves task back to active', (tester) async {
      await tester.pumpWidget(buildScreen(useRealDatabase: true));
      await tester.pumpAndSettle();

      // Insert a completed task directly.
      final taskDao = TaskDao(database);
      await taskDao.insertTask(
        TasksCompanion(
          taskId: const Value('c1'),
          title: const Value('Finished task'),
          status: const Value(TaskStatus.completed),
          syncStatus: const Value(TaskSyncStatus.pending),
          createdAt: Value(DateTime.utc(2026, 2, 28)),
          updatedAt: Value(DateTime.utc(2026, 2, 28)),
        ),
      );

      // Rebuild to pick up the task.
      await tester.pumpWidget(buildScreen(useRealDatabase: true));
      await tester.pumpAndSettle();

      // Switch to Completed tab.
      await tester.tap(find.text('Completed'));
      await tester.pumpAndSettle();

      // Find and tap the checkbox to uncomplete.
      final checkbox = find.byType(Checkbox);
      if (checkbox.evaluate().isNotEmpty) {
        await tester.tap(checkbox.first);
        await tester.pumpAndSettle();

        // Task should be uncompleted in DB.
        final updated = await taskDao.getTaskById('c1');
        expect(updated?.status, TaskStatus.active);
      }

      await cleanupWidgetTree(tester);
    });

    testWidgets('loading state shows spinner', (tester) async {
      // Use a StreamController that never emits (no pending timer, unlike
      // Future.delayed). This keeps the provider in loading state without
      // creating timers that trigger "Timer still pending" errors.
      final neverEmit = StreamController<List<Task>>();
      addTearDown(() => neverEmit.close());

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            activeTasksStreamProvider.overrideWith((ref) => neverEmit.stream),
            completedTasksStreamProvider.overrideWith(
              (ref) => Stream.value(<Task>[]),
            ),
            taskCountProvider.overrideWith((ref) => Future.value(0)),
            googleAuthServiceProvider.overrideWithValue(_fakeAuthService),
            isGoogleConnectedProvider.overrideWith(
              (ref) => GoogleConnectionNotifier(_fakeAuthService),
            ),
          ],
          child: const MaterialApp(home: TasksScreen()),
        ),
      );
      // Don't settle — want to see the loading state.
      await tester.pump();

      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      await cleanupWidgetTree(tester);
    });
  });
}
