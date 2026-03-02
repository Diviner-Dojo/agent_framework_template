// ===========================================================================
// file: test/ui/settings_screen_expanded_test.dart
// purpose: Expanded widget tests for settings screen cards added in later
//          phases: Voice card, Conversation AI card, Calendar & Tasks card,
//          Data Management card.
// ===========================================================================

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:agentic_journal/config/environment.dart';
import 'package:agentic_journal/providers/auth_providers.dart';
import 'package:agentic_journal/providers/calendar_providers.dart';
import 'package:agentic_journal/providers/llm_providers.dart';
import 'package:agentic_journal/providers/onboarding_providers.dart';
import 'package:agentic_journal/providers/photo_providers.dart';
import 'package:agentic_journal/providers/search_providers.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/providers/settings_providers.dart';
import 'package:agentic_journal/providers/sync_providers.dart';
import 'package:agentic_journal/providers/voice_providers.dart';
import 'package:agentic_journal/services/assistant_registration_service.dart';
import 'package:agentic_journal/services/google_auth_service.dart';
import 'package:agentic_journal/services/supabase_service.dart';
import 'package:agentic_journal/ui/screens/settings_screen.dart';

class _MockAssistantService extends AssistantRegistrationService {
  _MockAssistantService() : super(isAndroid: false);

  @override
  Future<bool> isDefaultAssistant() async => false;

  @override
  Future<void> openAssistantSettings() async {}
}

/// No-op auth service for test overrides.
final _fakeAuthService = GoogleAuthService(
  signIn: () async => null,
  signOut: () async => null,
  disconnect: () async => null,
  isSignedIn: () async => false,
  getAuthClient: () async => null,
  signInSilently: () async => null,
);

void main() {
  late SharedPreferences prefs;
  late _MockAssistantService mockService;

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    prefs = await SharedPreferences.getInstance();
    mockService = _MockAssistantService();
  });

  Widget buildScreen({
    bool isAuthenticated = false,
    bool isGoogleConnected = false,
  }) {
    return ProviderScope(
      overrides: [
        sharedPreferencesProvider.overrideWithValue(prefs),
        assistantServiceProvider.overrideWithValue(mockService),
        appVersionProvider.overrideWith((ref) => Future.value('0.15.0')),
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
        sessionCountProvider.overrideWith((ref) => Future.value(5)),
        sttModelReadyProvider.overrideWith((ref) => Future.value(false)),
        llmModelReadyProvider.overrideWith((ref) => Future.value(false)),
        photoStorageInfoProvider.overrideWith(
          (ref) => Future.value(
            const PhotoStorageInfo(count: 3, totalSizeBytes: 1024 * 1024),
          ),
        ),
        googleAuthServiceProvider.overrideWithValue(_fakeAuthService),
        isGoogleConnectedProvider.overrideWith(
          (ref) => GoogleConnectionNotifier(_fakeAuthService),
        ),
      ],
      child: MaterialApp(
        home: const SettingsScreen(),
        routes: {'/auth': (context) => const Scaffold()},
      ),
    );
  }

  group('Voice card', () {
    testWidgets('shows Voice card with voice mode toggle', (tester) async {
      await tester.pumpWidget(buildScreen());
      await tester.pumpAndSettle();

      expect(find.text('Voice'), findsOneWidget);
      expect(find.text('Enable voice mode'), findsOneWidget);
    });

    testWidgets('voice toggle defaults to off', (tester) async {
      await tester.pumpWidget(buildScreen());
      await tester.pumpAndSettle();

      final switchFinder = find.ancestor(
        of: find.text('Enable voice mode'),
        matching: find.byType(SwitchListTile),
      );
      final switchTile = tester.widget<SwitchListTile>(switchFinder);
      expect(switchTile.value, isFalse);
    });
  });

  group('Conversation AI card', () {
    testWidgets('shows Conversation AI card', (tester) async {
      await tester.pumpWidget(buildScreen());
      await tester.pumpAndSettle();

      // Scroll to Conversation AI card.
      await tester.scrollUntilVisible(
        find.text('Conversation AI'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(find.text('Conversation AI'), findsOneWidget);
      expect(find.text('Prefer Claude when online'), findsOneWidget);
    });

    testWidgets('shows Journal only mode toggle', (tester) async {
      await tester.pumpWidget(buildScreen());
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.text('Journal only mode'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(find.text('Journal only mode'), findsOneWidget);
    });

    testWidgets('shows Local AI status', (tester) async {
      await tester.pumpWidget(buildScreen());
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.text('Local AI: Not downloaded'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(find.text('Local AI: Not downloaded'), findsOneWidget);
      expect(find.text('Download'), findsOneWidget);
    });

    testWidgets('shows Personality section', (tester) async {
      await tester.pumpWidget(buildScreen());
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.text('Personality'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(find.text('Personality'), findsOneWidget);
      expect(find.text('Assistant name'), findsOneWidget);
      expect(find.text('Conversation style'), findsOneWidget);
    });
  });

  group('Calendar & Tasks card', () {
    testWidgets('shows Calendar & Tasks card', (tester) async {
      await tester.pumpWidget(buildScreen());
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.text('Calendar & Tasks'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(find.text('Calendar & Tasks'), findsOneWidget);
    });

    testWidgets('shows not connected status and Connect button', (
      tester,
    ) async {
      await tester.pumpWidget(buildScreen());
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.text('Calendar & Tasks'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(
        find.text('Google Calendar & Tasks: Not connected'),
        findsOneWidget,
      );
      expect(find.text('Connect Google'), findsOneWidget);
    });

    testWidgets('shows auto-suggest toggles', (tester) async {
      await tester.pumpWidget(buildScreen());
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.text('Auto-suggest calendar events'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(find.text('Auto-suggest calendar events'), findsOneWidget);
      expect(find.text('Auto-suggest tasks'), findsOneWidget);
    });

    testWidgets('shows require confirmation toggle (non-disableable)', (
      tester,
    ) async {
      await tester.pumpWidget(buildScreen());
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.text('Require confirmation'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(find.text('Require confirmation'), findsOneWidget);
      expect(
        find.text('Confirmation is always required in this version'),
        findsOneWidget,
      );
    });
  });

  group('Data Management card', () {
    testWidgets('shows Data Management card with session count', (
      tester,
    ) async {
      await tester.pumpWidget(buildScreen());
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.text('Data Management'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(find.text('Data Management'), findsOneWidget);
      expect(find.text('Journal entries: 5 sessions'), findsOneWidget);
    });

    testWidgets('shows photo storage info', (tester) async {
      await tester.pumpWidget(buildScreen());
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.text('Data Management'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(find.textContaining('Photos: 3 photos'), findsOneWidget);
    });

    testWidgets('shows Clear All Entries button', (tester) async {
      await tester.pumpWidget(buildScreen());
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.text('Clear All Entries'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(find.text('Clear All Entries'), findsOneWidget);
    });
  });
}
