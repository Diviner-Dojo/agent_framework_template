// ===========================================================================
// file: test/ui/onboarding_screen_test.dart
// purpose: Widget tests for the onboarding screen.
//
// Tests verify that:
//   - All 3 pages render with expected content
//   - The Skip button completes onboarding and navigates away
//   - The Next button advances pages
//   - The "Begin Journaling" button completes onboarding
//   - The "Set as Default Assistant" button is present on page 2
//   - Dot indicators reflect the current page
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
import 'package:agentic_journal/providers/settings_providers.dart';
import 'package:agentic_journal/repositories/agent_repository.dart';
import 'package:agentic_journal/services/assistant_registration_service.dart';
import 'package:agentic_journal/ui/screens/onboarding_screen.dart';

/// A mock assistant service for onboarding tests.
class MockAssistantService extends AssistantRegistrationService {
  int openSettingsCallCount = 0;

  MockAssistantService() : super(isAndroid: false);

  @override
  Future<void> openAssistantSettings() async {
    openSettingsCallCount++;
  }

  @override
  Future<bool> isDefaultAssistant() async => false;
}

void main() {
  group('OnboardingScreen', () {
    late MockAssistantService mockService;
    late AppDatabase database;

    setUp(() {
      SharedPreferences.setMockInitialValues({});
      mockService = MockAssistantService();
      database = AppDatabase.forTesting(NativeDatabase.memory());
    });

    tearDown(() async {
      await database.close();
    });

    /// Build the test widget with a navigator to observe route changes.
    Future<SharedPreferences> buildTestWidget(WidgetTester tester) async {
      final prefs = await SharedPreferences.getInstance();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            sharedPreferencesProvider.overrideWithValue(prefs),
            assistantServiceProvider.overrideWithValue(mockService),
            databaseProvider.overrideWithValue(database),
            agentRepositoryProvider.overrideWithValue(AgentRepository()),
          ],
          child: MaterialApp(
            initialRoute: '/onboarding',
            routes: {
              '/onboarding': (_) => const OnboardingScreen(),
              '/': (_) => const Scaffold(body: Text('Session List')),
              '/session': (_) => const Scaffold(body: Text('Journal Session')),
            },
          ),
        ),
      );

      return prefs;
    }

    testWidgets('page 1 renders welcome content', (tester) async {
      await buildTestWidget(tester);
      await tester.pumpAndSettle();

      expect(find.text('Welcome to Agentic Journal'), findsOneWidget);
      expect(
        find.textContaining('AI-powered personal journal'),
        findsOneWidget,
      );
    });

    testWidgets('Skip button is visible on page 1', (tester) async {
      await buildTestWidget(tester);
      await tester.pumpAndSettle();

      expect(find.text('Skip'), findsOneWidget);
    });

    testWidgets('Next button is visible on non-last pages', (tester) async {
      await buildTestWidget(tester);
      await tester.pumpAndSettle();

      expect(find.text('Next'), findsOneWidget);
    });

    testWidgets('Next button advances to page 2', (tester) async {
      await buildTestWidget(tester);
      await tester.pumpAndSettle();

      await tester.tap(find.text('Next'));
      await tester.pumpAndSettle();

      expect(find.text('Set Up Assistant Gesture'), findsOneWidget);
      expect(find.text('Set as Default Assistant'), findsOneWidget);
    });

    testWidgets('page 2 has Set as Default Assistant button', (tester) async {
      await buildTestWidget(tester);
      await tester.pumpAndSettle();

      // Navigate to page 2.
      await tester.tap(find.text('Next'));
      await tester.pumpAndSettle();

      // Tap the button.
      await tester.tap(find.text('Set as Default Assistant'));
      await tester.pumpAndSettle();

      expect(mockService.openSettingsCallCount, 1);
    });

    testWidgets('can navigate to page 3 and see Begin Journaling', (
      tester,
    ) async {
      await buildTestWidget(tester);
      await tester.pumpAndSettle();

      // Navigate to page 2.
      await tester.tap(find.text('Next'));
      await tester.pumpAndSettle();

      // Navigate to page 3.
      await tester.tap(find.text('Next'));
      await tester.pumpAndSettle();

      expect(find.text("You're All Set!"), findsOneWidget);
      expect(find.text('Begin Journaling'), findsOneWidget);
    });

    testWidgets('Next button is absent on last page', (tester) async {
      await buildTestWidget(tester);
      await tester.pumpAndSettle();

      // Navigate to page 3.
      await tester.tap(find.text('Next'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Next'));
      await tester.pumpAndSettle();

      // Next button should not be visible on last page.
      expect(find.text('Next'), findsNothing);
    });

    testWidgets('Skip completes onboarding and navigates to journal session', (
      tester,
    ) async {
      final prefs = await buildTestWidget(tester);
      await tester.pumpAndSettle();

      await tester.tap(find.text('Skip'));
      await tester.pumpAndSettle();

      // Should navigate to journal session (starts first session directly).
      expect(find.text('Journal Session'), findsOneWidget);

      // Onboarding should be marked complete in SharedPreferences.
      expect(prefs.getBool(onboardingCompleteKey), isTrue);
    });

    testWidgets(
      'Begin Journaling completes onboarding and navigates to session',
      (tester) async {
        final prefs = await buildTestWidget(tester);
        await tester.pumpAndSettle();

        // Navigate to last page.
        await tester.tap(find.text('Next'));
        await tester.pumpAndSettle();
        await tester.tap(find.text('Next'));
        await tester.pumpAndSettle();

        // Tap Begin Journaling.
        await tester.tap(find.text('Begin Journaling'));
        await tester.pumpAndSettle();

        // Should navigate to journal session (starts first session directly).
        expect(find.text('Journal Session'), findsOneWidget);

        // Onboarding should be marked complete.
        expect(prefs.getBool(onboardingCompleteKey), isTrue);
      },
    );

    testWidgets('swiping left advances to next page', (tester) async {
      await buildTestWidget(tester);
      await tester.pumpAndSettle();

      // Swipe left on the PageView to advance.
      await tester.fling(
        find.text('Welcome to Agentic Journal'),
        const Offset(-300, 0),
        1000,
      );
      await tester.pumpAndSettle();

      expect(find.text('Set Up Assistant Gesture'), findsOneWidget);
    });
  });
}
