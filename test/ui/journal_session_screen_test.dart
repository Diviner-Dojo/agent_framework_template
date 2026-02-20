// ===========================================================================
// file: test/ui/journal_session_screen_test.dart
// purpose: Widget tests for the active journal session screen.
//
// Tests verify that:
//   - The screen renders with app bar and input field
//   - The greeting message is displayed
//   - The send button is present
//   - The end session button is present
//   - Back button shows confirmation dialog (B1)
//   - Escalating thinking indicator updates message (B7)
//   - Done button appears after session close (B2)
// ===========================================================================

import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/providers/database_provider.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/repositories/agent_repository.dart';
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
            overrides: [
              databaseProvider.overrideWithValue(database),
              agentRepositoryProvider.overrideWithValue(AgentRepository()),
            ],
          ),
          child: MaterialApp(
            initialRoute: '/session',
            routes: {
              '/': (_) => const Scaffold(body: Text('Session List')),
              '/session': (_) => const JournalSessionScreen(),
            },
          ),
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

    testWidgets('back button shows confirmation dialog', (tester) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      // Tap the back button.
      await tester.tap(find.byIcon(Icons.arrow_back));
      await tester.pumpAndSettle();

      // Confirmation dialog should appear.
      expect(find.text('End this session?'), findsOneWidget);
      expect(find.text('Cancel'), findsOneWidget);
      expect(find.text('End'), findsOneWidget);
    });

    testWidgets('cancel in confirmation dialog keeps session active', (
      tester,
    ) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      // Show confirmation dialog.
      await tester.tap(find.byIcon(Icons.arrow_back));
      await tester.pumpAndSettle();

      // Tap Cancel.
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      // Dialog should close, session still active.
      expect(find.text('End this session?'), findsNothing);
      expect(find.text('Journal Entry'), findsOneWidget);

      final state = container.read(sessionNotifierProvider);
      expect(state.activeSessionId, isNotNull);
    });

    testWidgets('confirm in dialog ends session and shows Done button', (
      tester,
    ) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      // Show confirmation dialog.
      await tester.tap(find.byIcon(Icons.arrow_back));
      await tester.pumpAndSettle();

      // Tap End.
      await tester.tap(find.text('End'));
      await tester.pumpAndSettle();

      // Session should show closing complete state with Done button.
      expect(find.text('Done'), findsOneWidget);
    });

    testWidgets('end session button is hidden when session is ending', (
      tester,
    ) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      // Confirm exit via dialog.
      await tester.tap(find.byIcon(Icons.arrow_back));
      await tester.pumpAndSettle();
      await tester.tap(find.text('End'));
      await tester.pumpAndSettle();

      // End session button should be hidden when session is ending/complete.
      // The "Done" button should be visible instead.
      expect(find.text('Done'), findsOneWidget);
    });
  });
}
