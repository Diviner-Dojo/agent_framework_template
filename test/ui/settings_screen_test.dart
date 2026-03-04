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
import 'package:geolocator/geolocator.dart';

import 'package:agentic_journal/providers/auth_providers.dart';
import 'package:agentic_journal/providers/llm_providers.dart';
import 'package:agentic_journal/providers/location_providers.dart';
import 'package:agentic_journal/providers/onboarding_providers.dart';
import 'package:agentic_journal/providers/search_providers.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/providers/photo_providers.dart';
import 'package:agentic_journal/providers/settings_providers.dart';
import 'package:agentic_journal/providers/sync_providers.dart';
import 'package:agentic_journal/providers/voice_providers.dart';
import 'package:agentic_journal/services/assistant_registration_service.dart';
import 'package:agentic_journal/services/location_service.dart';
import 'package:agentic_journal/services/supabase_service.dart';
import 'package:agentic_journal/ui/screens/settings_screen.dart';

/// Creates a [LocationService] with faked permission responses for testing.
LocationService _fakeLocationService({
  LocationPermission checkResult = LocationPermission.denied,
  LocationPermission requestResult = LocationPermission.denied,
}) {
  return LocationService(
    checkPermission: () async => checkResult,
    requestPermission: () async => requestResult,
    isLocationServiceEnabled: () async => true,
    getLastKnownPosition: () async => null,
    getCurrentPosition:
        ({desiredAccuracy = LocationAccuracy.low, timeLimit}) async {
          throw Exception('not available');
        },
    reverseGeocode: (lat, lng) async => [],
  );
}

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

    Widget buildTestWidget({
      bool isAuthenticated = false,
      LocationService? locationService,
    }) {
      return ProviderScope(
        overrides: [
          sharedPreferencesProvider.overrideWithValue(prefs),
          assistantServiceProvider.overrideWithValue(mockService),
          appVersionProvider.overrideWith((ref) => Future.value('0.14.0')),
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
          if (locationService != null)
            locationServiceProvider.overrideWithValue(locationService),
          isAuthenticatedProvider.overrideWithValue(isAuthenticated),
          currentUserProvider.overrideWithValue(null),
          pendingSyncCountProvider.overrideWith((ref) => Stream.value(0)),
          sessionCountProvider.overrideWith((ref) => Future.value(0)),
          sttModelReadyProvider.overrideWith((ref) => Future.value(false)),
          llmModelReadyProvider.overrideWith((ref) => Future.value(false)),
          photoStorageInfoProvider.overrideWith(
            (ref) => Future.value(
              const PhotoStorageInfo(count: 0, totalSizeBytes: 0),
            ),
          ),
        ],
        child: MaterialApp(
          home: const SettingsScreen(),
          routes: {'/auth': (context) => const Scaffold()},
        ),
      );
    }

    testWidgets('renders Theme & Appearance card with palette grid', (
      tester,
    ) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      // Theme card is the first card — should be visible without scrolling.
      expect(find.text('Theme & Appearance'), findsOneWidget);

      // All 7 palette names should be rendered.
      expect(find.text('Still Water'), findsOneWidget);
      expect(find.text('Warm Earth'), findsOneWidget);
      expect(find.text('Soft Lavender'), findsOneWidget);
      expect(find.text('Forest Floor'), findsOneWidget);
      expect(find.text('Ember Glow'), findsOneWidget);
      expect(find.text('Midnight Ink'), findsOneWidget);
      expect(find.text('Dawn Light'), findsOneWidget);

      // Mode toggle segments.
      expect(find.text('System'), findsOneWidget);
      expect(find.text('Light'), findsOneWidget);
      expect(find.text('Dark'), findsOneWidget);

      // Advanced section (collapsed by default).
      expect(find.text('Advanced'), findsOneWidget);
    });

    testWidgets('theme card defaults to still_water palette', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      // Default palette is "Still Water" — verify it's displayed.
      expect(find.text('Still Water'), findsOneWidget);
      // Default theme mode is System.
      expect(find.text('System'), findsOneWidget);
    });

    testWidgets('tapping a palette updates selection', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      // Tap "Ember Glow" palette.
      await tester.tap(find.text('Ember Glow'));
      await tester.pumpAndSettle();

      // Verify the preference was persisted.
      expect(prefs.getString('theme_palette_id'), 'ember_glow');
    });

    testWidgets('renders Digital Assistant card', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      // Scroll past the Theme & Appearance card to make Digital Assistant
      // visible (Phase 5A theme card is large and pushes it below fold).
      await tester.scrollUntilVisible(
        find.text('Digital Assistant'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(find.text('Digital Assistant'), findsOneWidget);
    });

    testWidgets('shows assistant status as No when not default', (
      tester,
    ) async {
      mockService.returnValue = false;
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.text('Digital Assistant'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(find.text('Default assistant: No'), findsOneWidget);
    });

    testWidgets('shows assistant status as Yes when default', (tester) async {
      mockService.returnValue = true;
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.text('Digital Assistant'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(find.text('Default assistant: Yes'), findsOneWidget);
    });

    testWidgets('has Set as Default Assistant button', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.text('Set as Default Assistant'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
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
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(find.text('About'), findsOneWidget);
      expect(find.text('Agentic Journal'), findsOneWidget);
      expect(find.text('Version 0.14.0'), findsOneWidget);
    });

    testWidgets('shows manual instructions fallback', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.text('Digital Assistant'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
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

      // Scroll down past Conversation AI card to make Cloud Sync visible.
      await tester.scrollUntilVisible(
        find.text('Cloud Sync'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(find.text('Cloud Sync'), findsOneWidget);
    });

    testWidgets('shows sign in prompt when not authenticated', (tester) async {
      await tester.pumpWidget(buildTestWidget(isAuthenticated: false));
      await tester.pumpAndSettle();

      // Scroll down past Conversation AI card to make Cloud Sync visible.
      await tester.scrollUntilVisible(
        find.text('Cloud Sync'),
        200,
        scrollable: find.byType(Scrollable).first,
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

      // Scroll down past Conversation AI card to make Cloud Sync visible.
      await tester.scrollUntilVisible(
        find.text('Cloud Sync'),
        200,
        scrollable: find.byType(Scrollable).first,
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
              appVersionProvider.overrideWith((ref) => Future.value('0.14.0')),
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
              llmModelReadyProvider.overrideWith((ref) => Future.value(false)),
              photoStorageInfoProvider.overrideWith(
                (ref) => Future.value(
                  const PhotoStorageInfo(count: 0, totalSizeBytes: 0),
                ),
              ),
            ],
            child: MaterialApp(
              home: const SettingsScreen(),
              routes: {'/auth': (context) => const Scaffold()},
            ),
          ),
        );
        await tester.pumpAndSettle();

        // Scroll down past Conversation AI card to make Cloud Sync visible.
        await tester.scrollUntilVisible(
          find.text('Cloud Sync'),
          200,
          scrollable: find.byType(Scrollable).first,
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
            appVersionProvider.overrideWith((ref) => Future.value('0.14.0')),
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
            llmModelReadyProvider.overrideWith((ref) => Future.value(false)),
            photoStorageInfoProvider.overrideWith(
              (ref) => Future.value(
                const PhotoStorageInfo(count: 0, totalSizeBytes: 0),
              ),
            ),
          ],
          child: MaterialApp(
            home: const SettingsScreen(),
            routes: {'/auth': (context) => const Scaffold()},
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Scroll down past Conversation AI card to make Cloud Sync visible.
      await tester.scrollUntilVisible(
        find.text('Cloud Sync'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(find.text('1 session pending sync'), findsOneWidget);
    });

    // Location card tests (Phase 10 — ADR-0019)
    testWidgets('shows Location card with toggle', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      // Scroll to Location card.
      await tester.scrollUntilVisible(
        find.text('Location'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(find.text('Location'), findsOneWidget);
      expect(find.text('Enable location'), findsOneWidget);
      expect(find.text('Record where you journal'), findsOneWidget);
    });

    testWidgets('location toggle defaults to off', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.text('Enable location'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      // Find the SwitchListTile that is an ancestor of the 'Enable location'
      // text, not the last one (which may be a Calendar toggle).
      final switchWidget = tester.widget<SwitchListTile>(
        find.ancestor(
          of: find.text('Enable location'),
          matching: find.byType(SwitchListTile),
        ),
      );
      expect(switchWidget.value, false);
    });

    testWidgets('shows Clear Location Data button', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.text('Clear Location Data'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(find.text('Clear Location Data'), findsOneWidget);
    });

    testWidgets('shows privacy disclosure text', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.text('Location'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(find.textContaining('which may contact Google'), findsOneWidget);
    });

    testWidgets('toggle on requests permission and enables when granted', (
      tester,
    ) async {
      final service = _fakeLocationService(
        checkResult: LocationPermission.denied,
        requestResult: LocationPermission.whileInUse,
      );
      await tester.pumpWidget(buildTestWidget(locationService: service));
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.text('Enable location'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      // Toggle should be off initially.
      final locationSwitchFinder = find.ancestor(
        of: find.text('Enable location'),
        matching: find.byType(SwitchListTile),
      );
      var switchTile = tester.widget<SwitchListTile>(locationSwitchFinder);
      expect(switchTile.value, false);

      // Tap the location toggle to turn it on.
      final locationSwitch = find.descendant(
        of: locationSwitchFinder,
        matching: find.byType(Switch),
      );
      await tester.tap(locationSwitch);
      await tester.pumpAndSettle();

      // Toggle should now be on (permission was granted).
      switchTile = tester.widget<SwitchListTile>(locationSwitchFinder);
      expect(switchTile.value, true);
    });

    testWidgets('toggle on shows SnackBar when permission denied', (
      tester,
    ) async {
      final service = _fakeLocationService(
        checkResult: LocationPermission.denied,
        requestResult: LocationPermission.denied,
      );
      await tester.pumpWidget(buildTestWidget(locationService: service));
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.text('Enable location'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      // Tap the location toggle specifically.
      final locationSwitchFinder = find.ancestor(
        of: find.text('Enable location'),
        matching: find.byType(SwitchListTile),
      );
      final locationSwitch = find.descendant(
        of: locationSwitchFinder,
        matching: find.byType(Switch),
      );
      await tester.tap(locationSwitch);
      await tester.pumpAndSettle();

      // SnackBar should appear.
      expect(
        find.text('Location permission is required to record location.'),
        findsOneWidget,
      );

      // Toggle should remain off.
      final switchTile = tester.widget<SwitchListTile>(locationSwitchFinder);
      expect(switchTile.value, false);
    });

    testWidgets(
      'toggle on shows settings prompt when permission deniedForever',
      (tester) async {
        final service = _fakeLocationService(
          checkResult: LocationPermission.deniedForever,
        );
        await tester.pumpWidget(buildTestWidget(locationService: service));
        await tester.pumpAndSettle();

        await tester.scrollUntilVisible(
          find.text('Enable location'),
          200,
          scrollable: find.byType(Scrollable).first,
        );
        await tester.pumpAndSettle();

        // Tap the location toggle specifically.
        final locationSwitchFinder = find.ancestor(
          of: find.text('Enable location'),
          matching: find.byType(SwitchListTile),
        );
        final locationSwitch = find.descendant(
          of: locationSwitchFinder,
          matching: find.byType(Switch),
        );
        await tester.tap(locationSwitch);
        await tester.pumpAndSettle();

        // SnackBar with settings action should appear.
        expect(find.textContaining('permanently denied'), findsOneWidget);
        expect(find.text('Open Settings'), findsOneWidget);

        // Toggle should remain off.
        final switchTile = tester.widget<SwitchListTile>(locationSwitchFinder);
        expect(switchTile.value, false);
      },
    );

    testWidgets('sign in button navigates to /auth', (tester) async {
      var navigated = false;
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            sharedPreferencesProvider.overrideWithValue(prefs),
            assistantServiceProvider.overrideWithValue(mockService),
            appVersionProvider.overrideWith((ref) => Future.value('0.14.0')),
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
            llmModelReadyProvider.overrideWith((ref) => Future.value(false)),
            photoStorageInfoProvider.overrideWith(
              (ref) => Future.value(
                const PhotoStorageInfo(count: 0, totalSizeBytes: 0),
              ),
            ),
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
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      await tester.tap(find.widgetWithText(FilledButton, 'Sign In'));
      await tester.pumpAndSettle();

      expect(navigated, true);
    });
  });
}
