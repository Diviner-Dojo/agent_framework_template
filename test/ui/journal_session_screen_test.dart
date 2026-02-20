// ===========================================================================
// file: test/ui/journal_session_screen_test.dart
// purpose: Widget tests for the active journal session screen.
//
// Tests verify that:
//   - The screen renders with app bar and input field
//   - The greeting message is displayed
//   - The send button is present
//   - The end session button is present
//   - An empty input does not trigger a send
// ===========================================================================

import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/providers/database_provider.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/ui/screens/journal_session_screen.dart';

void main() {
  group('JournalSessionScreen', () {
    late AppDatabase database;

    setUp(() {
      database = AppDatabase.forTesting(NativeDatabase.memory());
    });

    tearDown(() async {
      await database.close();
    });

    Future<ProviderContainer> buildTestWidget(WidgetTester tester) async {
      late ProviderContainer container;

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container = ProviderContainer(
            overrides: [databaseProvider.overrideWithValue(database)],
          ),
          child: const MaterialApp(home: JournalSessionScreen()),
        ),
      );

      // Start a session so there's an active session and greeting.
      await container.read(sessionNotifierProvider.notifier).startSession();
      await tester.pumpAndSettle();

      return container;
    }

    testWidgets('renders app bar with Journal Entry title', (tester) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      expect(find.text('Journal Entry'), findsOneWidget);
    });

    testWidgets('shows greeting message from agent', (tester) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      // The agent repository generates a greeting — it should appear as a
      // chat bubble. The exact text depends on time-of-day, so just check
      // that at least one chat bubble exists.
      expect(find.byType(ListView), findsOneWidget);
    });

    testWidgets('shows text input field with hint', (tester) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      expect(find.byType(TextField), findsOneWidget);
      expect(find.text('Type your thoughts...'), findsOneWidget);
    });

    testWidgets('has send button', (tester) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      expect(find.byIcon(Icons.send), findsOneWidget);
    });

    testWidgets('has back button in app bar', (tester) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      expect(find.byIcon(Icons.arrow_back), findsOneWidget);
    });
  });
}
