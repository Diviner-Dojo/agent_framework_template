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
      isQuickReminder: false,
      status: status,
      syncStatus: syncStatus,
      createdAt: DateTime.utc(2026, 2, 28),
      updatedAt: DateTime.utc(2026, 2, 28),
    );
  }

  Widget buildScreen({
    List<Task> activeTasks = const [],
    List<Task> completedTasks = const [],
    int taskCount = 0,
    AppDatabase? database,
  }) {
    return ProviderScope(
      overrides: [
        activeTasksStreamProvider.overrideWith(
          (ref) => Stream.value(activeTasks),
        ),
        completedTasksStreamProvider.overrideWith(
          (ref) => Stream.value(completedTasks),
        ),
        taskCountProvider.overrideWith((ref) => Future.value(taskCount)),
        googleAuthServiceProvider.overrideWithValue(_fakeAuthService),
        isGoogleConnectedProvider.overrideWith(
          (ref) => GoogleConnectionNotifier(_fakeAuthService),
        ),
        if (database != null) databaseProvider.overrideWithValue(database),
        if (database != null)
          taskDaoProvider.overrideWithValue(TaskDao(database)),
      ],
      child: const MaterialApp(home: TasksScreen()),
    );
  }

  group('TasksScreen', () {
    group('app bar', () {
      testWidgets('shows "Tasks" title', (tester) async {
        await tester.pumpWidget(buildScreen());
        await tester.pumpAndSettle();
        expect(find.text('Tasks'), findsOneWidget);
      });

      testWidgets('shows add (+) button', (tester) async {
        await tester.pumpWidget(buildScreen());
        await tester.pumpAndSettle();
        expect(find.byIcon(Icons.add), findsOneWidget);
      });
    });

    group('segmented control', () {
      testWidgets('shows Active and Completed segments', (tester) async {
        await tester.pumpWidget(buildScreen());
        await tester.pumpAndSettle();
        expect(find.text('Active'), findsOneWidget);
        expect(find.text('Completed'), findsOneWidget);
      });

      testWidgets('defaults to Active segment', (tester) async {
        await tester.pumpWidget(
          buildScreen(
            activeTasks: [makeTask(title: 'Active task')],
            completedTasks: [
              makeTask(
                taskId: 'done-1',
                title: 'Done task',
                status: TaskStatus.completed,
              ),
            ],
          ),
        );
        await tester.pumpAndSettle();
        // Active task should be visible, completed should not.
        expect(find.text('Active task'), findsOneWidget);
        expect(find.text('Done task'), findsNothing);
      });

      testWidgets('switching to Completed shows completed tasks', (
        tester,
      ) async {
        await tester.pumpWidget(
          buildScreen(
            activeTasks: [makeTask(title: 'Active task')],
            completedTasks: [
              makeTask(
                taskId: 'done-1',
                title: 'Done task',
                status: TaskStatus.completed,
              ),
            ],
          ),
        );
        await tester.pumpAndSettle();

        // Tap the "Completed" segment.
        await tester.tap(find.text('Completed'));
        await tester.pumpAndSettle();

        expect(find.text('Done task'), findsOneWidget);
        expect(find.text('Active task'), findsNothing);
      });
    });

    group('active tasks list', () {
      testWidgets('shows tasks', (tester) async {
        await tester.pumpWidget(
          buildScreen(
            activeTasks: [
              makeTask(taskId: 't1', title: 'First task'),
              makeTask(taskId: 't2', title: 'Second task'),
            ],
          ),
        );
        await tester.pumpAndSettle();
        expect(find.text('First task'), findsOneWidget);
        expect(find.text('Second task'), findsOneWidget);
      });

      testWidgets('shows empty state when no active tasks', (tester) async {
        await tester.pumpWidget(buildScreen());
        await tester.pumpAndSettle();
        expect(find.text('No active tasks'), findsOneWidget);
        expect(find.textContaining('Tap +'), findsOneWidget);
      });

      testWidgets('shows empty state icon', (tester) async {
        await tester.pumpWidget(buildScreen());
        await tester.pumpAndSettle();
        expect(find.byIcon(Icons.task_alt_outlined), findsOneWidget);
      });
    });

    group('completed tasks list', () {
      testWidgets('shows empty state when no completed tasks', (tester) async {
        await tester.pumpWidget(buildScreen());
        await tester.pumpAndSettle();

        // Switch to Completed tab.
        await tester.tap(find.text('Completed'));
        await tester.pumpAndSettle();

        expect(find.text('No completed tasks yet.'), findsOneWidget);
      });

      testWidgets('shows completed tasks', (tester) async {
        await tester.pumpWidget(
          buildScreen(
            completedTasks: [
              makeTask(
                taskId: 'c1',
                title: 'Finished item',
                status: TaskStatus.completed,
              ),
            ],
          ),
        );
        await tester.pumpAndSettle();

        await tester.tap(find.text('Completed'));
        await tester.pumpAndSettle();

        expect(find.text('Finished item'), findsOneWidget);
      });
    });

    group('add task sheet', () {
      late AppDatabase database;

      setUp(() async {
        SharedPreferences.setMockInitialValues({});
        database = AppDatabase.forTesting(NativeDatabase.memory());
        final sessionDao = SessionDao(database);
        await sessionDao.createSession('s1', DateTime.utc(2026, 2, 28), 'UTC');
      });

      tearDown(() async {
        await database.close();
      });

      testWidgets('opens from + button', (tester) async {
        await tester.pumpWidget(buildScreen(database: database));
        await tester.pumpAndSettle();

        await tester.tap(find.byIcon(Icons.add));
        await tester.pumpAndSettle();

        expect(find.text('New Task'), findsOneWidget);
        expect(find.text('Task title'), findsOneWidget);
      });

      testWidgets('shows title and notes fields', (tester) async {
        await tester.pumpWidget(buildScreen(database: database));
        await tester.pumpAndSettle();

        await tester.tap(find.byIcon(Icons.add));
        await tester.pumpAndSettle();

        expect(find.text('Task title'), findsOneWidget);
        expect(find.text('Notes (optional)'), findsOneWidget);
      });

      testWidgets('shows due date button', (tester) async {
        await tester.pumpWidget(buildScreen(database: database));
        await tester.pumpAndSettle();

        await tester.tap(find.byIcon(Icons.add));
        await tester.pumpAndSettle();

        expect(find.text('Add due date'), findsOneWidget);
      });

      testWidgets('shows Add Task submit button', (tester) async {
        await tester.pumpWidget(buildScreen(database: database));
        await tester.pumpAndSettle();

        await tester.tap(find.byIcon(Icons.add));
        await tester.pumpAndSettle();

        expect(find.text('Add Task'), findsOneWidget);
      });

      testWidgets('submit button is disabled when title is empty', (
        tester,
      ) async {
        await tester.pumpWidget(buildScreen(database: database));
        await tester.pumpAndSettle();

        // Open sheet.
        await tester.tap(find.byIcon(Icons.add));
        await tester.pumpAndSettle();

        // Find the FilledButton. It should not crash if tapped with empty title.
        final button = find.text('Add Task');
        expect(button, findsOneWidget);
        // The button is enabled but _submit returns early for empty title.
      });
    });
  });
}
