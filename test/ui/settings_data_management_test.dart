import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/providers/auth_providers.dart';
import 'package:agentic_journal/providers/database_provider.dart';
import 'package:agentic_journal/providers/onboarding_providers.dart';
import 'package:agentic_journal/providers/search_providers.dart';
import 'package:agentic_journal/providers/settings_providers.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/providers/sync_providers.dart';
import 'package:agentic_journal/providers/voice_providers.dart';
import 'package:agentic_journal/repositories/agent_repository.dart';
import 'package:agentic_journal/ui/screens/settings_screen.dart';

void main() {
  group('Settings Data Management', () {
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
              // Override assistant status check (platform-dependent).
              isDefaultAssistantProvider.overrideWith(
                (ref) => Future.value(false),
              ),
              // Override auth to not authenticated (avoids Supabase init).
              isAuthenticatedProvider.overrideWithValue(false),
              currentUserProvider.overrideWithValue(null),
              pendingSyncCountProvider.overrideWith((ref) => Stream.value(0)),
              sessionCountProvider.overrideWith((ref) => Future.value(0)),
              sttModelReadyProvider.overrideWith((ref) => Future.value(false)),
            ],
          ),
          child: const MaterialApp(home: SettingsScreen()),
        ),
      );
      await tester.pumpAndSettle();

      // Scroll down to make Data Management card visible (the Voice card
      // added in Phase 7A pushes it below the initial viewport).
      await tester.scrollUntilVisible(
        find.text('Data Management'),
        200,
        scrollable: find.byType(Scrollable),
      );
      await tester.pumpAndSettle();

      return container;
    }

    testWidgets('shows Data Management card with session count', (
      tester,
    ) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      expect(find.text('Data Management'), findsOneWidget);
      expect(find.text('Journal entries: 0 sessions'), findsOneWidget);
    });

    testWidgets('shows Clear All Entries button', (tester) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      expect(find.text('Clear All Entries'), findsOneWidget);
    });

    testWidgets('Clear All button opens confirmation dialog', (tester) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      await tester.tap(find.text('Clear All Entries'));
      await tester.pumpAndSettle();

      expect(find.text('Clear all entries?'), findsOneWidget);
      expect(find.text('Type DELETE to confirm:'), findsOneWidget);
    });

    testWidgets('Clear All button is disabled until DELETE is typed', (
      tester,
    ) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      await tester.tap(find.text('Clear All Entries'));
      await tester.pumpAndSettle();

      // Find the Clear All button — should be disabled.
      final clearAllButton = find.widgetWithText(FilledButton, 'Clear All');
      expect(clearAllButton, findsOneWidget);
      final button = tester.widget<FilledButton>(clearAllButton);
      expect(button.onPressed, isNull);

      // Type "DELETE".
      await tester.enterText(find.byType(TextField), 'DELETE');
      await tester.pump();

      // Button should now be enabled.
      final buttonAfter = tester.widget<FilledButton>(clearAllButton);
      expect(buttonAfter.onPressed, isNotNull);
    });

    testWidgets('cancel in Clear All dialog preserves data', (tester) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      // Create a session first.
      final notifier = container.read(sessionNotifierProvider.notifier);
      await notifier.startSession();
      await notifier.sendMessage('Test message');
      await notifier.endSession();
      notifier.dismissSession();
      await tester.pumpAndSettle();

      // Open Clear All dialog.
      // Need to scroll to see the button first if needed.
      await tester.tap(find.text('Clear All Entries'));
      await tester.pumpAndSettle();

      // Tap Cancel.
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      // Session should still exist.
      final sessionDao = container.read(sessionDaoProvider);
      final sessions = await sessionDao.getAllSessionsByDate();
      expect(sessions.length, 1);
    });

    testWidgets('confirming Clear All deletes all data', (tester) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      // Create a session first.
      final notifier = container.read(sessionNotifierProvider.notifier);
      await notifier.startSession();
      await notifier.sendMessage('Test message');
      await notifier.endSession();
      notifier.dismissSession();
      await tester.pumpAndSettle();

      // Open Clear All dialog.
      await tester.tap(find.text('Clear All Entries'));
      await tester.pumpAndSettle();

      // Type DELETE and confirm.
      await tester.enterText(find.byType(TextField), 'DELETE');
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Clear All'));
      await tester.pumpAndSettle();

      // All data should be cleared.
      final sessionDao = container.read(sessionDaoProvider);
      final sessions = await sessionDao.getAllSessionsByDate();
      expect(sessions, isEmpty);

      // SnackBar should show.
      expect(find.text('All journal entries cleared.'), findsOneWidget);
    });
  });
}
