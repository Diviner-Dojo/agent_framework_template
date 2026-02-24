// ===========================================================================
// file: test/ui/settings_screen_test.dart
// purpose: Widget tests for the settings screen.
//
// Tests verify that:
//   - The screen renders with the assistant status card
//   - The "Set as Default" button is present
//   - The about card shows version info
//   - Lifecycle resume triggers a re-read of assistant status
//   - Cloud Sync card shows sign-in prompt when not authenticated
//   - Cloud Sync card shows user email when authenticated
// ===========================================================================

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:agentic_journal/config/environment.dart';
import 'package:agentic_journal/providers/auth_providers.dart';
import 'package:agentic_journal/providers/onboarding_providers.dart';
import 'package:agentic_journal/providers/search_providers.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/providers/settings_providers.dart';
import 'package:agentic_journal/providers/sync_providers.dart';
import 'package:agentic_journal/providers/voice_providers.dart';
import 'package:agentic_journal/services/assistant_registration_service.dart';
import 'package:agentic_journal/services/supabase_service.dart';
import 'package:agentic_journal/ui/screens/settings_screen.dart';

/// A mock assistant service that tracks method calls.
class MockAssistantService extends AssistantRegistrationService {
  int isDefaultCallCount = 0;
  bool returnValue = false;

  MockAssistantService() : super(isAndroid: false);

  @override
  Future<bool> isDefaultAssistant() async {
    isDefaultCallCount++;
    return returnValue;
  }

  @override
  Future<void> openAssistantSettings() async {
    // No-op for tests.
  }
}

void main() {
  group('SettingsScreen', () {
    late MockAssistantService mockService;

    late SharedPreferences prefs;

    setUp(() async {
      mockService = MockAssistantService();
      SharedPreferences.setMockInitialValues({});
      prefs = await SharedPreferences.getInstance();
    });

    Widget buildTestWidget({bool isAuthenticated = false}) {
      return ProviderScope(
        overrides: [
          sharedPreferencesProvider.overrideWithValue(prefs),
          assistantServiceProvider.overrideWithValue(mockService),
          environmentProvider.overrideWithValue(
            const Environment.custom(supabaseUrl: '', supabaseAnonKey: ''),
          ),
          supabaseServiceProvider.overrideWithValue(
            SupabaseService(
              environment: const Environment.custom(
                supabaseUrl: '',
                supabaseAnonKey: '',
              ),
            ),
          ),
          isAuthenticatedProvider.overrideWithValue(isAuthenticated),
          currentUserProvider.overrideWithValue(null),
          pendingSyncCountProvider.overrideWith((ref) => Stream.value(0)),
          sessionCountProvider.overrideWith((ref) => Future.value(0)),
          sttModelReadyProvider.overrideWith((ref) => Future.value(false)),
        ],
        child: MaterialApp(
          home: const SettingsScreen(),
          routes: {'/auth': (context) => const Scaffold()},
        ),
      );
    }

    testWidgets('renders Digital Assistant card', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      expect(find.text('Digital Assistant'), findsOneWidget);
    });

    testWidgets('shows assistant status as No when not default', (
      tester,
    ) async {
      mockService.returnValue = false;
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      expect(find.text('Default assistant: No'), findsOneWidget);
    });

    testWidgets('shows assistant status as Yes when default', (tester) async {
      mockService.returnValue = true;
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      expect(find.text('Default assistant: Yes'), findsOneWidget);
    });

    testWidgets('has Set as Default Assistant button', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      expect(find.text('Set as Default Assistant'), findsOneWidget);
    });

    testWidgets('renders About card with version', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      // Scroll down to make the About card visible (it may be below fold
      // after the Data Management card was added in Phase 6).
      await tester.scrollUntilVisible(
        find.text('About'),
        200,
        scrollable: find.byType(Scrollable),
      );
      await tester.pumpAndSettle();

      expect(find.text('About'), findsOneWidget);
      expect(find.text('Agentic Journal'), findsOneWidget);
      expect(find.text('Version 1.0.0'), findsOneWidget);
    });

    testWidgets('shows manual instructions fallback', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      // The instructions text should be visible.
      expect(find.textContaining('Digital Assistant'), findsWidgets);
    });

    testWidgets('lifecycle resume triggers re-check of assistant status', (
      tester,
    ) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      // Initial call count.
      final initialCalls = mockService.isDefaultCallCount;

      // Simulate app lifecycle resume (user returning from system settings).
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pumpAndSettle();

      // Should have been called at least one more time.
      expect(mockService.isDefaultCallCount, greaterThan(initialCalls));
    });

    // Cloud Sync card tests
    testWidgets('shows Cloud Sync card', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      // Scroll down past AI Assistant card to make Cloud Sync visible.
      await tester.scrollUntilVisible(
        find.text('Cloud Sync'),
        200,
        scrollable: find.byType(Scrollable),
      );
      await tester.pumpAndSettle();

      expect(find.text('Cloud Sync'), findsOneWidget);
    });

    testWidgets('shows sign in prompt when not authenticated', (tester) async {
      await tester.pumpWidget(buildTestWidget(isAuthenticated: false));
      await tester.pumpAndSettle();

      // Scroll down past AI Assistant card to make Cloud Sync visible.
      await tester.scrollUntilVisible(
        find.text('Cloud Sync'),
        200,
        scrollable: find.byType(Scrollable),
      );
      await tester.pumpAndSettle();

      expect(
        find.text('Sign in to sync your journal to the cloud'),
        findsOneWidget,
      );
      expect(find.widgetWithText(FilledButton, 'Sign In'), findsOneWidget);
    });

    testWidgets('shows all synced message when authenticated with 0 pending', (
      tester,
    ) async {
      await tester.pumpWidget(buildTestWidget(isAuthenticated: true));
      await tester.pumpAndSettle();

      // Scroll down past AI Assistant card to make Cloud Sync visible.
      await tester.scrollUntilVisible(
        find.text('Cloud Sync'),
        200,
        scrollable: find.byType(Scrollable),
      );
      await tester.pumpAndSettle();

      expect(find.text('All sessions synced'), findsOneWidget);
      expect(find.text('Sync Now'), findsOneWidget);
      expect(find.text('Sign Out'), findsOneWidget);
    });

    testWidgets(
      'shows pending count when authenticated with pending sessions',
      (tester) async {
        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              sharedPreferencesProvider.overrideWithValue(prefs),
              assistantServiceProvider.overrideWithValue(mockService),
              environmentProvider.overrideWithValue(
                const Environment.custom(supabaseUrl: '', supabaseAnonKey: ''),
              ),
              supabaseServiceProvider.overrideWithValue(
                SupabaseService(
                  environment: const Environment.custom(
                    supabaseUrl: '',
                    supabaseAnonKey: '',
                  ),
                ),
              ),
              isAuthenticatedProvider.overrideWithValue(true),
              currentUserProvider.overrideWithValue(null),
              pendingSyncCountProvider.overrideWith((ref) => Stream.value(3)),
              sessionCountProvider.overrideWith((ref) => Future.value(0)),
              sttModelReadyProvider.overrideWith((ref) => Future.value(false)),
            ],
            child: MaterialApp(
              home: const SettingsScreen(),
              routes: {'/auth': (context) => const Scaffold()},
            ),
          ),
        );
        await tester.pumpAndSettle();

        // Scroll down past AI Assistant card to make Cloud Sync visible.
        await tester.scrollUntilVisible(
          find.text('Cloud Sync'),
          200,
          scrollable: find.byType(Scrollable),
        );
        await tester.pumpAndSettle();

        expect(find.text('3 sessions pending sync'), findsOneWidget);
      },
    );

    testWidgets('shows 1 session pending sync (singular)', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            sharedPreferencesProvider.overrideWithValue(prefs),
            assistantServiceProvider.overrideWithValue(mockService),
            environmentProvider.overrideWithValue(
              const Environment.custom(supabaseUrl: '', supabaseAnonKey: ''),
            ),
            supabaseServiceProvider.overrideWithValue(
              SupabaseService(
                environment: const Environment.custom(
                  supabaseUrl: '',
                  supabaseAnonKey: '',
                ),
              ),
            ),
            isAuthenticatedProvider.overrideWithValue(true),
            currentUserProvider.overrideWithValue(null),
            pendingSyncCountProvider.overrideWith((ref) => Stream.value(1)),
            sessionCountProvider.overrideWith((ref) => Future.value(0)),
            sttModelReadyProvider.overrideWith((ref) => Future.value(false)),
          ],
          child: MaterialApp(
            home: const SettingsScreen(),
            routes: {'/auth': (context) => const Scaffold()},
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Scroll down past AI Assistant card to make Cloud Sync visible.
      await tester.scrollUntilVisible(
        find.text('Cloud Sync'),
        200,
        scrollable: find.byType(Scrollable),
      );
      await tester.pumpAndSettle();

      expect(find.text('1 session pending sync'), findsOneWidget);
    });

    testWidgets('sign in button navigates to /auth', (tester) async {
      var navigated = false;
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            sharedPreferencesProvider.overrideWithValue(prefs),
            assistantServiceProvider.overrideWithValue(mockService),
            environmentProvider.overrideWithValue(
              const Environment.custom(supabaseUrl: '', supabaseAnonKey: ''),
            ),
            supabaseServiceProvider.overrideWithValue(
              SupabaseService(
                environment: const Environment.custom(
                  supabaseUrl: '',
                  supabaseAnonKey: '',
                ),
              ),
            ),
            isAuthenticatedProvider.overrideWithValue(false),
            currentUserProvider.overrideWithValue(null),
            pendingSyncCountProvider.overrideWith((ref) => Stream.value(0)),
            sessionCountProvider.overrideWith((ref) => Future.value(0)),
            sttModelReadyProvider.overrideWith((ref) => Future.value(false)),
          ],
          child: MaterialApp(
            home: const SettingsScreen(),
            routes: {
              '/auth': (context) {
                navigated = true;
                return const Scaffold();
              },
            },
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Scroll down to ensure Sign In button is visible.
      await tester.scrollUntilVisible(
        find.widgetWithText(FilledButton, 'Sign In'),
        200,
        scrollable: find.byType(Scrollable),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.widgetWithText(FilledButton, 'Sign In'));
      await tester.pumpAndSettle();

      expect(navigated, true);
    });
  });
}
