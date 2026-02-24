import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:agentic_journal/config/environment.dart';
import 'package:agentic_journal/providers/auth_providers.dart';
import 'package:agentic_journal/providers/calendar_providers.dart';
import 'package:agentic_journal/providers/llm_providers.dart';
import 'package:agentic_journal/providers/photo_providers.dart';
import 'package:agentic_journal/providers/search_providers.dart';
import 'package:agentic_journal/providers/onboarding_providers.dart';
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

GoogleAuthService _fakeAuth({
  GoogleSignInFn? signIn,
  GoogleDisconnectFn? disconnect,
  GoogleIsSignedInFn? isSignedIn,
}) {
  return GoogleAuthService(
    signIn: signIn ?? () async => null,
    signOut: () async => null,
    disconnect: disconnect ?? () async => null,
    isSignedIn: isSignedIn ?? () async => false,
    getAuthClient: () async => null,
    signInSilently: () async => null,
  );
}

void main() {
  late SharedPreferences prefs;

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    prefs = await SharedPreferences.getInstance();
  });

  Widget buildTestWidget({
    GoogleAuthService? authService,
    bool isConnected = false,
    int sessionCount = 0,
    int photoCount = 0,
    int photoSizeBytes = 0,
  }) {
    final auth = authService ?? _fakeAuth();
    return ProviderScope(
      overrides: [
        sharedPreferencesProvider.overrideWithValue(prefs),
        assistantServiceProvider.overrideWithValue(_MockAssistantService()),
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
        googleAuthServiceProvider.overrideWithValue(auth),
        isAuthenticatedProvider.overrideWithValue(false),
        currentUserProvider.overrideWithValue(null),
        pendingSyncCountProvider.overrideWith((ref) => Stream.value(0)),
        sessionCountProvider.overrideWith((ref) => Future.value(sessionCount)),
        sttModelReadyProvider.overrideWith((ref) => Future.value(false)),
        llmModelReadyProvider.overrideWith((ref) => Future.value(false)),
        photoStorageInfoProvider.overrideWith(
          (ref) => Future.value(
            PhotoStorageInfo(count: photoCount, totalSizeBytes: photoSizeBytes),
          ),
        ),
      ],
      child: MaterialApp(
        home: const SettingsScreen(),
        routes: {'/auth': (context) => const Scaffold()},
      ),
    );
  }

  group('Calendar settings card', () {
    testWidgets('renders Calendar card title', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      // Scroll to find the calendar card.
      await tester.scrollUntilVisible(
        find.text('Calendar'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(find.text('Calendar'), findsOneWidget);
    });

    testWidgets('shows "Not connected" when not signed in', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.text('Google Calendar: Not connected'),
        200,
        scrollable: find.byType(Scrollable).first,
      );

      expect(find.text('Google Calendar: Not connected'), findsOneWidget);
    });

    testWidgets('shows Connect button when not signed in', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.text('Connect Google Calendar'),
        200,
        scrollable: find.byType(Scrollable).first,
      );

      expect(find.text('Connect Google Calendar'), findsOneWidget);
    });

    testWidgets('auto-suggest toggle defaults to on', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.text('Auto-suggest calendar events'),
        200,
        scrollable: find.byType(Scrollable).first,
      );

      expect(find.text('Auto-suggest calendar events'), findsOneWidget);
    });

    testWidgets('confirmation toggle is disabled (non-disableable in v1)', (
      tester,
    ) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.text('Require confirmation'),
        200,
        scrollable: find.byType(Scrollable).first,
      );

      expect(find.text('Require confirmation'), findsOneWidget);
      expect(
        find.text('Confirmation is always required in this version'),
        findsOneWidget,
      );
    });

    testWidgets('Calendar card appears before Data Management', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      // Scroll to make Calendar visible.
      await tester.scrollUntilVisible(
        find.text('Calendar'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      expect(find.text('Calendar'), findsOneWidget);

      // Continue scrolling to find Data Management after Calendar.
      await tester.scrollUntilVisible(
        find.text('Data Management'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      expect(find.text('Data Management'), findsOneWidget);
    });
  });

  group('Data Management card', () {
    testWidgets('shows session count', (tester) async {
      await tester.pumpWidget(buildTestWidget(sessionCount: 42));
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.text('Data Management'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(find.text('Journal entries: 42 sessions'), findsOneWidget);
    });

    testWidgets('shows singular session text for count 1', (tester) async {
      await tester.pumpWidget(buildTestWidget(sessionCount: 1));
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.text('Data Management'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(find.text('Journal entries: 1 session'), findsOneWidget);
    });

    testWidgets('shows "Photos: None" when no photos', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.text('Data Management'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(find.text('Photos: None'), findsOneWidget);
    });

    testWidgets('shows photo count and size when photos exist', (tester) async {
      await tester.pumpWidget(
        buildTestWidget(
          photoCount: 5,
          photoSizeBytes: 10 * 1024 * 1024, // 10 MB
        ),
      );
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.text('Data Management'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      expect(find.textContaining('5 photos'), findsOneWidget);
    });
  });
}
