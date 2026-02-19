import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/ui/screens/session_list_screen.dart';

void main() {
  group('SessionListScreen', () {
    testWidgets('shows empty state placeholder text', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            // Override with an empty stream.
            allSessionsProvider.overrideWith(
              (ref) => Stream.value(<JournalSession>[]),
            ),
          ],
          child: const MaterialApp(home: SessionListScreen()),
        ),
      );

      // Wait for the stream to emit.
      await tester.pumpAndSettle();

      expect(find.text('No journal sessions yet'), findsOneWidget);
    });

    testWidgets('has a floating action button', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            allSessionsProvider.overrideWith(
              (ref) => Stream.value(<JournalSession>[]),
            ),
          ],
          child: const MaterialApp(home: SessionListScreen()),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.byType(FloatingActionButton), findsOneWidget);
    });

    testWidgets('renders session cards when sessions exist', (tester) async {
      final now = DateTime.utc(2026, 2, 19, 10, 0);
      final sessions = [
        JournalSession(
          sessionId: 's1',
          startTime: now,
          timezone: 'UTC',
          syncStatus: 'PENDING',
          createdAt: now,
          updatedAt: now,
        ),
        JournalSession(
          sessionId: 's2',
          startTime: now.subtract(const Duration(days: 1)),
          timezone: 'UTC',
          syncStatus: 'PENDING',
          createdAt: now,
          updatedAt: now,
          summary: 'Had a good day',
        ),
      ];

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            allSessionsProvider.overrideWith((ref) => Stream.value(sessions)),
          ],
          child: const MaterialApp(home: SessionListScreen()),
        ),
      );

      await tester.pumpAndSettle();

      // Should not show empty state.
      expect(find.text('No journal sessions yet'), findsNothing);

      // Should show session data. The summary text should appear.
      expect(find.text('Had a good day'), findsOneWidget);
    });
  });
}
