// ===========================================================================
// file: test/ui/journal_session_screen_test.dart
// purpose: Widget tests for the active journal session screen.
//
// Tests verify that:
//   - The screen renders with app bar and input field
//   - The greeting message is displayed
//   - The send button is present
//   - AppBar has Done button and overflow menu has Discard option
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
import 'package:agentic_journal/providers/questionnaire_providers.dart';
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
              deviceTimezoneProvider.overrideWith(
                (ref) async => 'America/New_York',
              ),
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

    testWidgets('has Done button in AppBar and Discard in overflow menu', (
      tester,
    ) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      // Done button should be visible in the AppBar.
      expect(find.text('Done'), findsOneWidget);

      // Overflow menu icon should be present.
      expect(find.byIcon(Icons.more_vert), findsOneWidget);

      // Tap the overflow menu.
      await tester.tap(find.byIcon(Icons.more_vert));
      await tester.pumpAndSettle();

      // Only Discard should be in the overflow menu.
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

    // regression: back button used to immediately pop without showing the
    // closing summary (endSession + dismissSession + pop in finally block).
    // It now matches the "goodbye" UX: shows the closing summary so the
    // user can confirm their entry was saved, then a second back dismisses.
    testWidgets(
      'back button ends session and shows closing summary, second back '
      'dismisses (regression)',
      (tester) async {
        final container = await buildTestWidget(tester);
        addTearDown(container.dispose);

        // Send a user message so the session has content.
        await tester.enterText(find.byType(TextField), 'I feel great');
        await tester.tap(find.byIcon(Icons.send));
        await tester.pumpAndSettle();

        // First back press — ends session, shows closing summary.
        await tester.tap(find.byIcon(Icons.arrow_back));
        await tester.pumpAndSettle();

        // Session must be in closing state (not immediately dismissed).
        final state = container.read(sessionNotifierProvider);
        expect(
          state.isClosingComplete,
          isTrue,
          reason: 'back button must show closing summary, not immediately pop',
        );
        expect(
          find.text('Session List'),
          findsNothing,
          reason: 'screen must stay open while closing summary is visible',
        );

        // Second back press — dismisses the screen.
        await tester.tap(find.byIcon(Icons.arrow_back));
        await tester.pumpAndSettle();

        expect(find.text('Session List'), findsOneWidget);
      },
    );

    testWidgets('Done button ends session and shows closing summary', (
      tester,
    ) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      // Send a user message so the session is not empty.
      await tester.enterText(find.byType(TextField), 'Testing');
      await tester.tap(find.byIcon(Icons.send));
      await tester.pumpAndSettle();

      // Tap Done — ends session and shows closing summary (does not pop).
      await tester.tap(find.text('Done'));
      await tester.pumpAndSettle();

      final state = container.read(sessionNotifierProvider);
      expect(state.isClosingComplete, isTrue);
      // Still on session screen — user dismisses with a back press.
      expect(find.text('Session List'), findsNothing);
    });

    // regression: after completing a pulse_check_in session, checkInProvider
    // (a global StateNotifierProvider) kept isActive=true. When the user then
    // opened a new regular journal entry, _maybeStartCheckIn() did not reset
    // the state — so the check-in complete card was displayed and the text
    // input field was hidden behind it. Fix: call cancelCheckIn() in the
    // else branch of _maybeStartCheckIn() for non-pulse-check-in sessions.
    //
    // NOTE: This test explicitly pre-seeds isActive=true before pumpAndSettle
    // so that removing the else branch would cause the test to fail. A test
    // that only checks the default isActive=false state proves nothing about
    // the regression.
    testWidgets(
      'text input visible and check-in card absent in regular journal session '
      '(regression: check-in state not reset cross-session)',
      (tester) async {
        // Create the container BEFORE pumpWidget so we can seed state.
        // addPostFrameCallback fires during pumpWidget (on the first frame
        // render), not during pumpAndSettle — so the state must be seeded
        // before the widget is built.
        final container = ProviderContainer(
          overrides: [
            sharedPreferencesProvider.overrideWithValue(prefs),
            databaseProvider.overrideWithValue(database),
            agentRepositoryProvider.overrideWithValue(AgentRepository()),
            deviceTimezoneProvider.overrideWith(
              (ref) async => 'America/New_York',
            ),
          ],
        );
        addTearDown(container.dispose);

        // Pre-condition: seed isActive=true to simulate stale check-in state
        // from a previous pulse_check_in session. If the fix (else branch in
        // _maybeStartCheckIn) is reverted, isActive stays true after the frame
        // renders and the assertions below will fail.
        await container.read(checkInProvider.notifier).startCheckIn();
        expect(
          container.read(checkInProvider).isActive,
          isTrue,
          reason:
              'pre-condition: isActive must be seeded true before widget '
              'builds to prove the regression fix is exercised',
        );

        // Start a session so the postFrameCallback's sessionState has a
        // non-null activeSessionId when _maybeStartCheckIn() evaluates it.
        await container.read(sessionNotifierProvider.notifier).startSession();

        // Build the widget. The first frame render fires the postFrameCallback
        // registered in initState, which calls _maybeStartCheckIn(). For a
        // non-pulse-check-in session, the else branch calls cancelCheckIn()
        // and resets isActive to false.
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp(
              initialRoute: '/session',
              routes: {
                '/': (_) => const Scaffold(body: Text('Session List')),
                '/session': (_) => const JournalSessionScreen(),
              },
            ),
          ),
        );
        await tester.pumpAndSettle();

        // Post-condition: cancelCheckIn() must have been called.
        expect(
          container.read(checkInProvider).isActive,
          isFalse,
          reason:
              'cancelCheckIn() must be called for non-pulse-check-in sessions '
              'to prevent lingering state from a previous check-in hiding the input',
        );
        // The text input field must be visible (isActive=true suppresses it).
        expect(
          find.byType(TextField),
          findsOneWidget,
          reason: 'text input must not be hidden by a stale check-in card',
        );
        // No pulse-check-in card should appear.
        expect(find.text('Pulse Check-In'), findsNothing);
      },
    );

    testWidgets('auto-discard shows SnackBar on empty session end', (
      tester,
    ) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      // End session without sending any user messages (empty session guard).
      // Use Done button in AppBar.
      await tester.tap(find.text('Done'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // SnackBar should appear with closed message.
      expect(
        find.text('Session closed \u2014 nothing was recorded.'),
        findsOneWidget,
      );
    });

    // regression: maxLines: null caused the text field to expand unboundedly,
    // pushing the send button off screen when the user typed a long message.
    // Fix: minLines: 1 + maxLines: 4 keeps the field compact on 360dp devices
    // with voice controls active while still preventing overflow (REV-145506-A5).
    // textInputAction: TextInputAction.send wires the keyboard Enter key to
    // submit (REV-145506-A6 — multi-line default would insert newline instead).
    testWidgets(
      'text field has minLines: 1, maxLines: 4 and textInputAction.send (regression)',
      tags: ['regression'],
      (tester) async {
        final container = await buildTestWidget(tester);
        addTearDown(container.dispose);

        final textField = tester.widget<TextField>(find.byType(TextField));
        expect(
          textField.maxLines,
          equals(4),
          reason:
              'maxLines: 4 prevents send button overflow on 360dp devices '
              'with voice controls active (REV-145506-A5)',
        );
        expect(
          textField.minLines,
          equals(1),
          reason: 'minLines: 1 keeps the field compact when empty',
        );
        expect(
          textField.textInputAction,
          equals(TextInputAction.send),
          reason:
              'TextInputAction.send wires keyboard Enter to submit; '
              'without it multi-line mode inserts newline (REV-145506-A6)',
        );
      },
    );
  });
}
