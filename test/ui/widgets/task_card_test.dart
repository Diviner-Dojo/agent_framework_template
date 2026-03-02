import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/services/task_extraction_service.dart';
import 'package:agentic_journal/ui/widgets/task_card.dart';

void main() {
  // Fixed task for deterministic tests.
  final testTask = ExtractedTask(
    title: 'Buy groceries',
    dueDate: DateTime.utc(2026, 3, 5), // Thursday
    notes: 'Milk, eggs, bread',
  );

  final taskNoDate = ExtractedTask(title: 'Read a book');

  final taskNoNotes = ExtractedTask(
    title: 'Call dentist',
    dueDate: DateTime.utc(2026, 3, 10),
  );

  Widget buildCard({
    ExtractedTask? extractedTask,
    bool isExtracting = false,
    String? extractionError,
    VoidCallback? onConfirm,
    VoidCallback? onDismiss,
  }) {
    return MaterialApp(
      home: Scaffold(
        body: TaskCard(
          extractedTask: extractedTask,
          isExtracting: isExtracting,
          extractionError: extractionError,
          onConfirm: onConfirm ?? () {},
          onDismiss: onDismiss ?? () {},
        ),
      ),
    );
  }

  group('TaskCard', () {
    group('header', () {
      testWidgets('shows "Task" header text', (tester) async {
        await tester.pumpWidget(buildCard(extractedTask: testTask));
        expect(find.text('Task'), findsOneWidget);
      });

      testWidgets('shows task_alt icon', (tester) async {
        await tester.pumpWidget(buildCard(extractedTask: testTask));
        expect(find.byIcon(Icons.task_alt), findsOneWidget);
      });

      testWidgets('has dismiss (X) button in header', (tester) async {
        var dismissed = false;
        await tester.pumpWidget(
          buildCard(extractedTask: testTask, onDismiss: () => dismissed = true),
        );
        final closeButton = find.byIcon(Icons.close);
        expect(closeButton, findsOneWidget);
        await tester.tap(closeButton);
        expect(dismissed, isTrue);
      });
    });

    group('loading state', () {
      testWidgets('shows spinner when extracting', (tester) async {
        await tester.pumpWidget(buildCard(isExtracting: true));
        expect(find.byType(CircularProgressIndicator), findsOneWidget);
      });

      testWidgets('shows "Extracting task details..." text', (tester) async {
        await tester.pumpWidget(buildCard(isExtracting: true));
        expect(find.text('Extracting task details...'), findsOneWidget);
      });

      testWidgets('does not show action buttons when extracting', (
        tester,
      ) async {
        await tester.pumpWidget(buildCard(isExtracting: true));
        expect(find.text('Add to Tasks'), findsNothing);
        expect(find.text('Dismiss'), findsNothing);
      });
    });

    group('error state', () {
      testWidgets('shows error message when extraction fails', (tester) async {
        await tester.pumpWidget(buildCard(extractionError: 'Network timeout'));
        expect(
          find.text('Could not extract task details: Network timeout'),
          findsOneWidget,
        );
      });
    });

    group('task details', () {
      testWidgets('shows task title', (tester) async {
        await tester.pumpWidget(buildCard(extractedTask: testTask));
        expect(find.text('Buy groceries'), findsOneWidget);
      });

      testWidgets('shows due date with calendar icon', (tester) async {
        await tester.pumpWidget(buildCard(extractedTask: testTask));
        expect(find.byIcon(Icons.calendar_today), findsOneWidget);
        // Thursday Mar 5, 2026 (local time).
        expect(find.textContaining('Mar'), findsOneWidget);
        expect(find.textContaining('2026'), findsOneWidget);
      });

      testWidgets('shows notes', (tester) async {
        await tester.pumpWidget(buildCard(extractedTask: testTask));
        expect(find.text('Milk, eggs, bread'), findsOneWidget);
      });

      testWidgets('hides date row when no due date', (tester) async {
        await tester.pumpWidget(buildCard(extractedTask: taskNoDate));
        expect(find.byIcon(Icons.calendar_today), findsNothing);
      });

      testWidgets('hides notes when none provided', (tester) async {
        await tester.pumpWidget(buildCard(extractedTask: taskNoNotes));
        // Only title and date should be visible, not notes text.
        expect(find.text('Call dentist'), findsOneWidget);
      });
    });

    group('action buttons', () {
      testWidgets('shows "Add to Tasks" button with task details', (
        tester,
      ) async {
        await tester.pumpWidget(buildCard(extractedTask: testTask));
        expect(find.text('Add to Tasks'), findsOneWidget);
      });

      testWidgets('shows "Dismiss" text button with task details', (
        tester,
      ) async {
        await tester.pumpWidget(buildCard(extractedTask: testTask));
        // Dismiss button in actions (separate from header X).
        expect(find.text('Dismiss'), findsOneWidget);
      });

      testWidgets('calls onConfirm when "Add to Tasks" tapped', (tester) async {
        var confirmed = false;
        await tester.pumpWidget(
          buildCard(extractedTask: testTask, onConfirm: () => confirmed = true),
        );
        await tester.tap(find.text('Add to Tasks'));
        expect(confirmed, isTrue);
      });

      testWidgets('calls onDismiss when "Dismiss" tapped', (tester) async {
        var dismissed = false;
        await tester.pumpWidget(
          buildCard(extractedTask: testTask, onDismiss: () => dismissed = true),
        );
        await tester.tap(find.text('Dismiss'));
        expect(dismissed, isTrue);
      });

      testWidgets('hides action buttons during extraction', (tester) async {
        await tester.pumpWidget(
          buildCard(isExtracting: true, extractedTask: null),
        );
        expect(find.text('Add to Tasks'), findsNothing);
      });

      testWidgets('shows add_task icon on confirm button', (tester) async {
        await tester.pumpWidget(buildCard(extractedTask: testTask));
        expect(find.byIcon(Icons.add_task), findsOneWidget);
      });
    });
  });
}
