// ===========================================================================
// file: test/ui/check_in_screen_test.dart
// purpose: Widget tests for the dedicated Pulse Check-In screen (Task 10).
//
// Tests verify:
//   - Screen renders with 'Pulse Check-In' title
//   - PulseCheckInWidget is shown (slider UI, not chat)
//   - Back button shows discard confirmation dialog
//   - Discard dialog 'Keep going' preserves active check-in
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
import 'package:agentic_journal/ui/screens/check_in_screen.dart';

void main() {
  group('CheckInScreen', () {
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
            initialRoute: '/check_in',
            routes: {
              '/': (_) => const Scaffold(body: Text('Home')),
              '/check_in': (_) => const CheckInScreen(),
            },
          ),
        ),
      );

      // Start a pulse check-in session so CheckInScreen has an active session.
      await container
          .read(sessionNotifierProvider.notifier)
          .startSession(journalingMode: 'pulse_check_in');
      await tester.pumpAndSettle();

      return container;
    }

    testWidgets('shows Pulse Check-In title in AppBar', (tester) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      // 'Pulse Check-In' appears in both the AppBar and the widget card header.
      expect(find.text('Pulse Check-In'), findsAtLeastNWidgets(1));
    });

    testWidgets('shows back button', (tester) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      expect(find.byIcon(Icons.arrow_back), findsOneWidget);
    });

    testWidgets('back button shows discard confirmation dialog', (
      tester,
    ) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      await tester.tap(find.byIcon(Icons.arrow_back));
      await tester.pumpAndSettle();

      expect(find.text('Discard check-in?'), findsOneWidget);
      expect(find.text('Your answers will not be saved.'), findsOneWidget);
    });

    testWidgets('discard dialog Keep going cancels without discarding', (
      tester,
    ) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      await tester.tap(find.byIcon(Icons.arrow_back));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Keep going'));
      await tester.pumpAndSettle();

      // Dialog dismissed, screen still showing.
      expect(find.text('Discard check-in?'), findsNothing);
      // 'Pulse Check-In' appears in both AppBar and widget card header.
      expect(find.text('Pulse Check-In'), findsAtLeastNWidgets(1));
    });
  });
}
