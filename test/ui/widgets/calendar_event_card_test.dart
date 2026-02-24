import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/services/event_extraction_service.dart';
import 'package:agentic_journal/ui/widgets/calendar_event_card.dart';

void main() {
  // Fixed event for deterministic tests.
  final testEvent = ExtractedEvent(
    title: 'Team Standup',
    startTime: DateTime.utc(2026, 3, 2, 14, 0), // Monday 2 PM
    endTime: DateTime.utc(2026, 3, 2, 14, 30),
    isPastTime: false,
  );

  final pastEvent = ExtractedEvent(
    title: 'Morning Review',
    startTime: DateTime.utc(2026, 2, 25, 9, 0),
    isPastTime: true,
  );

  Widget buildCard({
    ExtractedEvent? extractedEvent,
    bool isExtracting = false,
    String? extractionError,
    bool isReminder = false,
    bool isGoogleConnected = false,
    VoidCallback? onConfirm,
    VoidCallback? onDismiss,
    VoidCallback? onConnect,
  }) {
    return MaterialApp(
      home: Scaffold(
        body: CalendarEventCard(
          extractedEvent: extractedEvent,
          isExtracting: isExtracting,
          extractionError: extractionError,
          isReminder: isReminder,
          isGoogleConnected: isGoogleConnected,
          onConfirm: onConfirm ?? () {},
          onDismiss: onDismiss ?? () {},
          onConnect: onConnect,
        ),
      ),
    );
  }

  group('CalendarEventCard', () {
    group('header', () {
      testWidgets('shows "Calendar Event" header for events', (tester) async {
        await tester.pumpWidget(buildCard(extractedEvent: testEvent));
        expect(find.text('Calendar Event'), findsOneWidget);
        expect(find.byIcon(Icons.event), findsOneWidget);
      });

      testWidgets('shows "Reminder" header for reminders', (tester) async {
        await tester.pumpWidget(
          buildCard(extractedEvent: testEvent, isReminder: true),
        );
        expect(find.text('Reminder'), findsOneWidget);
        expect(find.byIcon(Icons.alarm), findsOneWidget);
      });

      testWidgets('has dismiss (X) button in header', (tester) async {
        var dismissed = false;
        await tester.pumpWidget(
          buildCard(
            extractedEvent: testEvent,
            onDismiss: () => dismissed = true,
          ),
        );
        // Find the close icon button.
        final closeButton = find.byIcon(Icons.close);
        expect(closeButton, findsOneWidget);
        await tester.tap(closeButton);
        expect(dismissed, isTrue);
      });
    });

    group('loading state', () {
      testWidgets('shows loading indicator when extracting', (tester) async {
        await tester.pumpWidget(buildCard(isExtracting: true));
        expect(find.byType(CircularProgressIndicator), findsOneWidget);
        expect(find.text('Extracting event details...'), findsOneWidget);
      });

      testWidgets('does not show action buttons when extracting', (
        tester,
      ) async {
        await tester.pumpWidget(buildCard(isExtracting: true));
        expect(find.text('Add to Calendar'), findsNothing);
        expect(find.text('Dismiss'), findsNothing);
      });
    });

    group('error state', () {
      testWidgets('shows error message when extraction fails', (tester) async {
        await tester.pumpWidget(
          buildCard(extractionError: 'Could not extract event title'),
        );
        expect(
          find.textContaining('Could not extract event title'),
          findsOneWidget,
        );
      });
    });

    group('event details', () {
      testWidgets('shows event title', (tester) async {
        await tester.pumpWidget(buildCard(extractedEvent: testEvent));
        expect(find.text('Team Standup'), findsOneWidget);
      });

      testWidgets('shows date', (tester) async {
        await tester.pumpWidget(buildCard(extractedEvent: testEvent));
        // Should contain "Monday" and "Mar" and "2" and "2026".
        expect(find.textContaining('Monday'), findsOneWidget);
        expect(find.textContaining('Mar'), findsOneWidget);
      });

      testWidgets('shows start and end time when endTime is set', (
        tester,
      ) async {
        await tester.pumpWidget(buildCard(extractedEvent: testEvent));
        // Should show a time range with "–".
        expect(find.textContaining('–'), findsOneWidget);
      });

      testWidgets('shows only start time when no endTime', (tester) async {
        final noEndEvent = ExtractedEvent(
          title: 'Quick Task',
          startTime: DateTime.utc(2026, 3, 2, 10, 0),
        );
        await tester.pumpWidget(buildCard(extractedEvent: noEndEvent));
        expect(find.textContaining('–'), findsNothing);
      });

      testWidgets('shows past time warning', (tester) async {
        await tester.pumpWidget(buildCard(extractedEvent: pastEvent));
        expect(find.text('This time is in the past'), findsOneWidget);
        expect(find.byIcon(Icons.warning_amber_rounded), findsOneWidget);
      });

      testWidgets('does not show past time warning for future events', (
        tester,
      ) async {
        await tester.pumpWidget(buildCard(extractedEvent: testEvent));
        expect(find.text('This time is in the past'), findsNothing);
      });
    });

    group('action buttons', () {
      testWidgets('shows "Add to Calendar" when connected', (tester) async {
        await tester.pumpWidget(
          buildCard(extractedEvent: testEvent, isGoogleConnected: true),
        );
        expect(find.text('Add to Calendar'), findsOneWidget);
      });

      testWidgets('shows "Connect Google Calendar" when not connected', (
        tester,
      ) async {
        await tester.pumpWidget(
          buildCard(extractedEvent: testEvent, isGoogleConnected: false),
        );
        expect(find.text('Connect Google Calendar'), findsOneWidget);
        expect(find.text('Add to Calendar'), findsNothing);
      });

      testWidgets('calls onConfirm when "Add to Calendar" tapped', (
        tester,
      ) async {
        var confirmed = false;
        await tester.pumpWidget(
          buildCard(
            extractedEvent: testEvent,
            isGoogleConnected: true,
            onConfirm: () => confirmed = true,
          ),
        );
        await tester.tap(find.text('Add to Calendar'));
        expect(confirmed, isTrue);
      });

      testWidgets('calls onDismiss when "Dismiss" tapped', (tester) async {
        var dismissed = false;
        await tester.pumpWidget(
          buildCard(
            extractedEvent: testEvent,
            onDismiss: () => dismissed = true,
          ),
        );
        await tester.tap(find.text('Dismiss'));
        expect(dismissed, isTrue);
      });

      testWidgets('calls onConnect when "Connect Google Calendar" tapped', (
        tester,
      ) async {
        var connectCalled = false;
        await tester.pumpWidget(
          buildCard(
            extractedEvent: testEvent,
            isGoogleConnected: false,
            onConnect: () => connectCalled = true,
          ),
        );
        await tester.tap(find.text('Connect Google Calendar'));
        expect(connectCalled, isTrue);
      });

      testWidgets('shows alarm icon for reminder confirm button', (
        tester,
      ) async {
        await tester.pumpWidget(
          buildCard(
            extractedEvent: testEvent,
            isReminder: true,
            isGoogleConnected: true,
          ),
        );
        expect(find.byIcon(Icons.alarm_add), findsOneWidget);
      });

      testWidgets('shows event icon for event confirm button', (tester) async {
        await tester.pumpWidget(
          buildCard(extractedEvent: testEvent, isGoogleConnected: true),
        );
        expect(find.byIcon(Icons.event_available), findsOneWidget);
      });
    });
  });

  group('CalendarEventCard formatting', () {
    test('_formatDate formats correctly', () {
      // Monday Mar 2, 2026.
      final result = CalendarEventCard.formatDateForTest(DateTime(2026, 3, 2));
      expect(result, contains('Monday'));
      expect(result, contains('Mar'));
      expect(result, contains('2'));
      expect(result, contains('2026'));
    });

    test('_formatTime formats AM correctly', () {
      final result = CalendarEventCard.formatTimeForTest(
        DateTime(2026, 3, 2, 9, 30),
      );
      expect(result, '9:30 AM');
    });

    test('_formatTime formats PM correctly', () {
      final result = CalendarEventCard.formatTimeForTest(
        DateTime(2026, 3, 2, 14, 0),
      );
      expect(result, '2:00 PM');
    });

    test('_formatTime formats noon correctly', () {
      final result = CalendarEventCard.formatTimeForTest(
        DateTime(2026, 3, 2, 12, 0),
      );
      expect(result, '12:00 PM');
    });

    test('_formatTime formats midnight correctly', () {
      final result = CalendarEventCard.formatTimeForTest(
        DateTime(2026, 3, 2, 0, 0),
      );
      expect(result, '12:00 AM');
    });
  });
}
