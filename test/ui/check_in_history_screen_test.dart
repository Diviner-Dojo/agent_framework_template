// ===========================================================================
// file: test/ui/check_in_history_screen_test.dart
// purpose: Widget tests for the Check-In History screen (Phase 3E).
//
// Tests verify:
//   - Empty state is shown when no check-ins exist
//   - Screen title is 'Check-In History'
//   - History entries appear after check-ins are completed
// ===========================================================================

import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/providers/database_provider.dart';
import 'package:agentic_journal/providers/onboarding_providers.dart';
import 'package:agentic_journal/providers/questionnaire_providers.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/repositories/agent_repository.dart';
import 'package:agentic_journal/ui/screens/check_in_history_screen.dart';

void main() {
  group('CheckInHistoryScreen', () {
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
          child: const MaterialApp(home: CheckInHistoryScreen()),
        ),
      );
      await tester.pumpAndSettle();

      return container;
    }

    testWidgets('shows Check-In History title', (tester) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      expect(find.text('Check-In History'), findsOneWidget);
    });

    testWidgets('shows empty state when no check-ins exist', (tester) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      expect(find.text('No check-ins yet'), findsOneWidget);
    });

    testWidgets('shows history entry after a check-in is saved', (
      tester,
    ) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      // Complete a check-in: start session, seed the default template,
      // and save a response directly via the notifier.
      final sessionNotifier = container.read(sessionNotifierProvider.notifier);
      await sessionNotifier.startSession(journalingMode: 'pulse_check_in');
      final sessionId = container
          .read(sessionNotifierProvider)
          .activeSessionId!;

      // Use CheckInNotifier to start and answer questions.
      final checkInNotifier = container.read(checkInProvider.notifier);
      await checkInNotifier.startCheckIn();
      final items = container.read(checkInProvider).items;

      // Answer all items to trigger the save.
      for (var i = 0; i < items.length; i++) {
        await checkInNotifier.recordAnswer(sessionId: sessionId, value: 7);
      }

      // Pump to allow the stream to emit.
      await tester.pumpAndSettle();

      // The score chip should be present (score/100 format).
      expect(find.textContaining('/ 100'), findsOneWidget);
    });
  });
}
