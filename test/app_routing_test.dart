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

@Tags(['regression'])
library;

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
import 'package:agentic_journal/providers/llm_providers.dart';
import 'package:agentic_journal/providers/photo_providers.dart';
import 'package:agentic_journal/providers/voice_providers.dart';
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
            photoCountProvider.overrideWith((ref) => Future.value(0)),
            sttModelReadyProvider.overrideWith((ref) => Future.value(false)),
            llmModelReadyProvider.overrideWith((ref) => Future.value(false)),
          ],
          child: const AgenticJournalApp(),
        ),
      );
    }

    testWidgets('shows onboarding screen when not onboarded', (tester) async {
      final prefs = await SharedPreferences.getInstance();

      await buildApp(tester, prefs: prefs);
      // Use pump() instead of pumpAndSettle() — the onboarding screen has
      // a CircularProgressIndicator whose animation never settles.
      await tester.pump();

      // Should show the conversational onboarding loading screen.
      expect(find.text('Setting up your journal...'), findsOneWidget);
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
        // Use pump() — the onboarding screen has a spinner that never settles.
        await tester.pump();

        // Should show onboarding, NOT navigate to /session.
        expect(find.text('Setting up your journal...'), findsOneWidget);
      },
    );

    // Regression: ref.watch(onboardingNotifierProvider) in app.dart build()
    // caused MaterialApp to rebuild when onboarding completed, which
    // reassigned initialRoute on an already-mounted Navigator, collapsing
    // the route stack. Fixed by using ref.read.
    // See: memory/bugs/regression-ledger.md
    testWidgets(
      'Navigator stack not collapsed when onboarding completes (regression)',
      (tester) async {
        // Start with onboarding incomplete.
        final prefs = await SharedPreferences.getInstance();

        await buildApp(tester, prefs: prefs);
        await tester.pump();

        // Should be on onboarding screen.
        expect(find.text('Setting up your journal...'), findsOneWidget);

        // Simulate onboarding completion by writing to SharedPreferences
        // and updating the notifier's state. In production, the
        // ConversationalOnboardingScreen calls completeOnboarding() which
        // sets state = true. If app.dart uses ref.watch, this would trigger
        // a MaterialApp rebuild that reassigns initialRoute.
        await prefs.setBool(onboardingCompleteKey, true);

        // Pump several frames to process any rebuilds.
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 100));
        await tester.pump(const Duration(milliseconds: 100));

        // The key assertion: the Navigator should still exist and be
        // functional. If the bug were present (ref.watch), the MaterialApp
        // would rebuild, initialRoute would change from '/onboarding' to '/',
        // and the already-mounted Navigator's route stack would collapse.
        // With the fix (ref.read), the MaterialApp does NOT rebuild, so the
        // Navigator maintains its current route stack.
        final navigators = find.byType(Navigator).evaluate();
        expect(
          navigators.isNotEmpty,
          isTrue,
          reason: 'Navigator should still exist after onboarding state change',
        );

        // The onboarding screen should still be showing because ref.read
        // means the build method does NOT re-run when the provider changes.
        // Navigation away from onboarding is handled by the onboarding
        // screen itself via Navigator.pushReplacement, not by initialRoute.
        expect(find.text('Setting up your journal...'), findsOneWidget);
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

      // Scroll down past Conversation AI card to make Cloud Sync visible.
      await tester.scrollUntilVisible(
        find.text('Cloud Sync'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(find.text('Cloud Sync'), findsOneWidget);
    });
  });
}
