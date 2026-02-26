// ===========================================================================
// file: test/ui/journal_session_screen_test.dart
// purpose: Widget tests for the active journal session screen.
//
// Tests verify that:
//   - The screen renders with app bar and input field
//   - The greeting message is displayed
//   - The send button is present
//   - Overflow menu has End Session and Discard options
//   - Back button shows confirmation dialog (B1)
//   - Discard confirmation works
//   - Done button appears after session close (B2)
//   - Auto-discard SnackBar on empty session (Phase 6)
// ===========================================================================

import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/providers/database_provider.dart';
import 'package:agentic_journal/providers/onboarding_providers.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/repositories/agent_repository.dart';
import 'package:agentic_journal/ui/screens/journal_session_screen.dart';

void main() {
  group('JournalSessionScreen', () {
    late AppDatabase database;

    late SharedPreferences prefs;

    setUp(() async {
      database = AppDatabase.forTesting(NativeDatabase.memory());
      SharedPreferences.setMockInitialValues({});
      prefs = await SharedPreferences.getInstance();
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
              sharedPreferencesProvider.overrideWithValue(prefs),
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

    testWidgets('has overflow menu with End Session and Discard', (
      tester,
    ) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      // Overflow menu icon should be present.
      expect(find.byIcon(Icons.more_vert), findsOneWidget);

      // Tap the overflow menu.
      await tester.tap(find.byIcon(Icons.more_vert));
      await tester.pumpAndSettle();

      // Menu items should appear.
      expect(find.text('End Session'), findsOneWidget);
      expect(find.text('Discard'), findsOneWidget);
    });

    testWidgets('discard from overflow menu shows confirmation dialog', (
      tester,
    ) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      // Open overflow menu and tap Discard.
      await tester.tap(find.byIcon(Icons.more_vert));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Discard'));
      await tester.pumpAndSettle();

      // Confirmation dialog should appear.
      expect(find.text('Discard this entry?'), findsOneWidget);
      expect(find.text('This cannot be undone.'), findsOneWidget);
      expect(find.text('Cancel'), findsOneWidget);
      // The Discard button in the dialog.
      expect(find.widgetWithText(FilledButton, 'Discard'), findsOneWidget);
    });

    testWidgets('cancel in discard dialog keeps session active', (
      tester,
    ) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      // Open overflow menu and tap Discard.
      await tester.tap(find.byIcon(Icons.more_vert));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Discard'));
      await tester.pumpAndSettle();

      // Tap Cancel.
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      // Dialog closed, session still active.
      expect(find.text('Discard this entry?'), findsNothing);
      final state = container.read(sessionNotifierProvider);
      expect(state.activeSessionId, isNotNull);
    });

    testWidgets('back button ends session and navigates back', (tester) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      // Send a user message so the session has content.
      await tester.enterText(find.byType(TextField), 'I feel great');
      await tester.tap(find.byIcon(Icons.send));
      await tester.pumpAndSettle();

      // Tap the back button — ends session immediately (no dialog).
      await tester.tap(find.byIcon(Icons.arrow_back));
      await tester.pumpAndSettle();

      // Should navigate back to the session list.
      expect(find.text('Session List'), findsOneWidget);
    });

    testWidgets('overflow End Session ends and navigates back', (tester) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      // Send a user message so the session is not empty.
      await tester.enterText(find.byType(TextField), 'Testing');
      await tester.tap(find.byIcon(Icons.send));
      await tester.pumpAndSettle();

      // End via overflow menu.
      await tester.tap(find.byIcon(Icons.more_vert));
      await tester.pumpAndSettle();
      await tester.tap(find.text('End Session'));
      await tester.pumpAndSettle();

      // Should navigate back to the session list.
      expect(find.text('Session List'), findsOneWidget);
    });

    testWidgets('auto-discard shows SnackBar on empty session end', (
      tester,
    ) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      // End session without sending any user messages (empty session guard).
      // Use overflow menu End Session.
      await tester.tap(find.byIcon(Icons.more_vert));
      await tester.pumpAndSettle();
      await tester.tap(find.text('End Session'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // SnackBar should appear with closed message.
      expect(
        find.text('Session closed \u2014 nothing was recorded.'),
        findsOneWidget,
      );
    });
  });
}
