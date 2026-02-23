// ===========================================================================
// file: test/app_routing_test.dart
// purpose: Tests for the AgenticJournalApp routing logic.
//
// Tests verify that:
//   - Initial route is '/onboarding' when onboarding is not complete
//   - Initial route is '/' (session list) when onboarding is complete
//   - The assistant-launch detection calls wasLaunchedAsAssistant() once
//   - The settings route is accessible from the session list
//
// Strategy:
//   Override providers to avoid database dependencies. The key providers are:
//     - sharedPreferencesProvider (onboarding state)
//     - assistantServiceProvider (assistant launch detection)
//     - allSessionsProvider (session list data — stubbed with empty stream)
//     - databaseProvider chain (overridden indirectly via allSessionsProvider)
// ===========================================================================

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:agentic_journal/app.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/providers/onboarding_providers.dart';
import 'package:agentic_journal/providers/search_providers.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/providers/settings_providers.dart';
import 'package:agentic_journal/services/assistant_registration_service.dart';

/// Mock assistant service that tracks method calls.
class MockAssistantService extends AssistantRegistrationService {
  int wasLaunchedCallCount = 0;
  bool wasLaunchedReturnValue = false;

  MockAssistantService() : super(isAndroid: false);

  @override
  Future<bool> wasLaunchedAsAssistant() async {
    wasLaunchedCallCount++;
    return wasLaunchedReturnValue;
  }

  @override
  Future<bool> isDefaultAssistant() async => false;

  @override
  Future<void> openAssistantSettings() async {}
}

void main() {
  group('AgenticJournalApp routing', () {
    late MockAssistantService mockService;

    setUp(() {
      SharedPreferences.setMockInitialValues({});
      mockService = MockAssistantService();
    });

    /// Build the app with overrides that eliminate database dependencies.
    Future<void> buildApp(
      WidgetTester tester, {
      required SharedPreferences prefs,
    }) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            sharedPreferencesProvider.overrideWithValue(prefs),
            assistantServiceProvider.overrideWithValue(mockService),
            // Override session providers to avoid database dependency.
            allSessionsProvider.overrideWith(
              (ref) => Stream.value(<JournalSession>[]),
            ),
            paginatedSessionsProvider.overrideWith(
              (ref) => Stream.value(<JournalSession>[]),
            ),
            sessionCountProvider.overrideWith((ref) => Future.value(0)),
          ],
          child: const AgenticJournalApp(),
        ),
      );
    }

    testWidgets('shows onboarding screen when not onboarded', (tester) async {
      final prefs = await SharedPreferences.getInstance();

      await buildApp(tester, prefs: prefs);
      await tester.pumpAndSettle();

      // Should show onboarding content (page 1).
      expect(find.text('Welcome to Agentic Journal'), findsOneWidget);
    });

    testWidgets('shows session list when onboarding is complete', (
      tester,
    ) async {
      SharedPreferences.setMockInitialValues({onboardingCompleteKey: true});
      final prefs = await SharedPreferences.getInstance();

      await buildApp(tester, prefs: prefs);
      await tester.pumpAndSettle();

      // Should show the session list screen.
      expect(find.text('Agentic Journal'), findsOneWidget);
      expect(find.text('No journal sessions yet'), findsOneWidget);
    });

    testWidgets('calls wasLaunchedAsAssistant exactly once', (tester) async {
      SharedPreferences.setMockInitialValues({onboardingCompleteKey: true});
      final prefs = await SharedPreferences.getInstance();

      await buildApp(tester, prefs: prefs);
      await tester.pumpAndSettle();

      expect(mockService.wasLaunchedCallCount, 1);
    });

    testWidgets('does not auto-navigate when assistant launch returns false', (
      tester,
    ) async {
      SharedPreferences.setMockInitialValues({onboardingCompleteKey: true});
      final prefs = await SharedPreferences.getInstance();

      mockService.wasLaunchedReturnValue = false;
      await buildApp(tester, prefs: prefs);
      await tester.pumpAndSettle();

      // Should stay on session list, not navigate to /session.
      expect(find.text('No journal sessions yet'), findsOneWidget);
    });

    testWidgets(
      'does not auto-navigate on assistant launch if onboarding incomplete',
      (tester) async {
        final prefs = await SharedPreferences.getInstance();

        // Assistant gesture fires, but onboarding is not complete.
        mockService.wasLaunchedReturnValue = true;
        await buildApp(tester, prefs: prefs);
        await tester.pumpAndSettle();

        // Should show onboarding, NOT navigate to /session.
        expect(find.text('Welcome to Agentic Journal'), findsOneWidget);
      },
    );

    testWidgets('settings route is accessible via icon button', (tester) async {
      SharedPreferences.setMockInitialValues({onboardingCompleteKey: true});
      final prefs = await SharedPreferences.getInstance();

      await buildApp(tester, prefs: prefs);
      await tester.pumpAndSettle();

      // Tap the settings icon in the app bar.
      await tester.tap(find.byIcon(Icons.settings));
      await tester.pumpAndSettle();

      // Should navigate to settings screen.
      expect(find.text('Digital Assistant'), findsOneWidget);
      expect(find.text('Cloud Sync'), findsOneWidget);
    });
  });
}
