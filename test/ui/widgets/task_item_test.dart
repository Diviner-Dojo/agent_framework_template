import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/task_dao.dart';
import 'package:agentic_journal/ui/widgets/task_item.dart';

void main() {
  final now = DateTime.now();
  final today = DateTime(now.year, now.month, now.day);

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

  Widget buildItem({
    required Task task,
    ValueChanged<bool>? onToggleComplete,
    VoidCallback? onDelete,
    VoidCallback? onEdit,
  }) {
    return MaterialApp(
      home: Scaffold(
        body: TaskItemWidget(
          task: task,
          onToggleComplete: onToggleComplete ?? (_) {},
          onDelete: onDelete ?? () {},
          onEdit: onEdit,
        ),
      ),
    );
  }

  group('TaskItemWidget', () {
    group('display', () {
      testWidgets('shows task title', (tester) async {
        await tester.pumpWidget(buildItem(task: makeTask(title: 'Buy milk')));
        expect(find.text('Buy milk'), findsOneWidget);
      });

      testWidgets('shows unchecked checkbox for active task', (tester) async {
        await tester.pumpWidget(buildItem(task: makeTask()));
        final checkbox = tester.widget<Checkbox>(find.byType(Checkbox));
        expect(checkbox.value, isFalse);
      });

      testWidgets('shows checked checkbox for completed task', (tester) async {
        await tester.pumpWidget(
          buildItem(task: makeTask(status: TaskStatus.completed)),
        );
        final checkbox = tester.widget<Checkbox>(find.byType(Checkbox));
        expect(checkbox.value, isTrue);
      });

      testWidgets('applies strikethrough to completed task title', (
        tester,
      ) async {
        await tester.pumpWidget(
          buildItem(task: makeTask(status: TaskStatus.completed)),
        );
        final text = tester.widget<Text>(find.text('Test Task'));
        expect(text.style?.decoration, TextDecoration.lineThrough);
      });

      testWidgets('shows notes icon when notes present', (tester) async {
        await tester.pumpWidget(buildItem(task: makeTask(notes: 'Some notes')));
        expect(find.byIcon(Icons.notes), findsOneWidget);
      });

      testWidgets('hides notes icon when no notes', (tester) async {
        await tester.pumpWidget(buildItem(task: makeTask()));
        expect(find.byIcon(Icons.notes), findsNothing);
      });

      testWidgets('hides notes icon when notes is empty string', (
        tester,
      ) async {
        await tester.pumpWidget(buildItem(task: makeTask(notes: '')));
        expect(find.byIcon(Icons.notes), findsNothing);
      });
    });

    group('interactions', () {
      testWidgets('checkbox toggle calls onToggleComplete', (tester) async {
        bool? toggled;
        await tester.pumpWidget(
          buildItem(
            task: makeTask(),
            onToggleComplete: (value) => toggled = value,
          ),
        );
        await tester.tap(find.byType(Checkbox));
        expect(toggled, isNotNull);
      });

      testWidgets('tap calls onEdit', (tester) async {
        var editCalled = false;
        await tester.pumpWidget(
          buildItem(task: makeTask(), onEdit: () => editCalled = true),
        );
        await tester.tap(find.byType(ListTile));
        expect(editCalled, isTrue);
      });

      testWidgets('swipe to delete calls onDelete', (tester) async {
        var deleted = false;
        await tester.pumpWidget(
          buildItem(task: makeTask(), onDelete: () => deleted = true),
        );
        // Swipe the item from right to left.
        await tester.drag(find.byType(Dismissible), const Offset(-500, 0));
        await tester.pumpAndSettle();
        expect(deleted, isTrue);
      });
    });

    group('due date chip', () {
      testWidgets('shows "Overdue" in red for past dates', (tester) async {
        final yesterday = today.subtract(const Duration(days: 2));
        await tester.pumpWidget(buildItem(task: makeTask(dueDate: yesterday)));
        expect(find.textContaining('Overdue'), findsOneWidget);
      });

      testWidgets('shows "Due today" for today', (tester) async {
        await tester.pumpWidget(buildItem(task: makeTask(dueDate: today)));
        expect(find.text('Due today'), findsOneWidget);
      });

      testWidgets('shows "Due tomorrow" for tomorrow', (tester) async {
        final tomorrow = today.add(const Duration(days: 1));
        await tester.pumpWidget(buildItem(task: makeTask(dueDate: tomorrow)));
        expect(find.text('Due tomorrow'), findsOneWidget);
      });

      testWidgets('shows date string for future dates', (tester) async {
        final future = today.add(const Duration(days: 10));
        await tester.pumpWidget(buildItem(task: makeTask(dueDate: future)));
        // Should show month abbreviation and day number, not "Due today/tomorrow".
        expect(find.text('Due today'), findsNothing);
        expect(find.text('Due tomorrow'), findsNothing);
        expect(find.textContaining('Overdue'), findsNothing);
        expect(find.byIcon(Icons.calendar_today), findsOneWidget);
      });

      testWidgets('shows no chip when due date is null', (tester) async {
        await tester.pumpWidget(buildItem(task: makeTask()));
        expect(find.byIcon(Icons.calendar_today), findsNothing);
      });

      testWidgets('completed task shows date without urgency labels', (
        tester,
      ) async {
        await tester.pumpWidget(
          buildItem(
            task: makeTask(dueDate: today, status: TaskStatus.completed),
          ),
        );
        // Completed tasks show the raw date, not "Due today".
        expect(find.text('Due today'), findsNothing);
        expect(find.byIcon(Icons.calendar_today), findsOneWidget);
      });
    });
  });
}
