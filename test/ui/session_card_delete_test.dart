import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/ui/widgets/session_card.dart';

/// Create a test JournalSession with the given properties.
JournalSession _makeSession({
  String sessionId = 'test-session',
  DateTime? startTime,
  DateTime? endTime,
  String? summary,
  String syncStatus = 'PENDING',
}) {
  return JournalSession(
    sessionId: sessionId,
    startTime: startTime ?? DateTime.utc(2026, 2, 23, 10, 0),
    endTime: endTime ?? DateTime.utc(2026, 2, 23, 10, 30),
    timezone: 'UTC',
    summary: summary ?? 'Test session summary',
    moodTags: null,
    people: null,
    topicTags: null,
    syncStatus: syncStatus,
    lastSyncAttempt: null,
    createdAt: DateTime.utc(2026, 2, 23, 10, 0),
    updatedAt: DateTime.utc(2026, 2, 23, 10, 0),
    isResumed: false,
    resumeCount: 0,
  );
}

void main() {
  group('SessionCard delete', () {
    testWidgets('shows overflow menu when onDelete is provided', (
      tester,
    ) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SessionCard(
              session: _makeSession(),
              messageCount: 5,
              onDelete: () {},
            ),
          ),
        ),
      );

      // Overflow menu icon should be present.
      expect(find.byIcon(Icons.more_vert), findsOneWidget);
    });

    testWidgets('hides overflow menu when onDelete is null', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SessionCard(session: _makeSession(), messageCount: 5),
          ),
        ),
      );

      // No overflow menu.
      expect(find.byIcon(Icons.more_vert), findsNothing);
    });

    testWidgets('overflow menu shows Delete option', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SessionCard(
              session: _makeSession(),
              messageCount: 5,
              onDelete: () {},
            ),
          ),
        ),
      );

      // Tap overflow menu.
      await tester.tap(find.byIcon(Icons.more_vert));
      await tester.pumpAndSettle();

      expect(find.text('Delete'), findsOneWidget);
    });

    testWidgets('Delete shows confirmation dialog with session info', (
      tester,
    ) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SessionCard(
              session: _makeSession(summary: 'My great day'),
              messageCount: 5,
              onDelete: () {},
            ),
          ),
        ),
      );

      // Open menu and tap Delete.
      await tester.tap(find.byIcon(Icons.more_vert));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Delete'));
      await tester.pumpAndSettle();

      // Confirmation dialog should show.
      expect(find.text('Delete this entry?'), findsOneWidget);
      expect(find.text('Cancel'), findsOneWidget);
      // The dialog content contains both the summary and the warning.
      expect(find.textContaining('This cannot be undone.'), findsOneWidget);
    });

    testWidgets('cancel in delete dialog does not call onDelete', (
      tester,
    ) async {
      bool deleteCalled = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SessionCard(
              session: _makeSession(),
              messageCount: 5,
              onDelete: () => deleteCalled = true,
            ),
          ),
        ),
      );

      // Open menu → Delete → Cancel.
      await tester.tap(find.byIcon(Icons.more_vert));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Delete'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      expect(deleteCalled, false);
    });

    testWidgets('confirm delete calls onDelete', (tester) async {
      bool deleteCalled = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SessionCard(
              session: _makeSession(),
              messageCount: 5,
              onDelete: () => deleteCalled = true,
            ),
          ),
        ),
      );

      // Open menu → Delete → confirm Delete.
      await tester.tap(find.byIcon(Icons.more_vert));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Delete'));
      await tester.pumpAndSettle();
      // Tap the Delete button in the confirmation dialog.
      await tester.tap(find.widgetWithText(FilledButton, 'Delete'));
      await tester.pumpAndSettle();

      expect(deleteCalled, true);
    });
  });
}
