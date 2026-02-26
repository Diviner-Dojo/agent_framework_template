import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:agentic_journal/config/environment.dart';
import 'package:agentic_journal/providers/auth_providers.dart';
import 'package:agentic_journal/providers/llm_providers.dart';
import 'package:agentic_journal/providers/onboarding_providers.dart';
import 'package:agentic_journal/providers/search_providers.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/providers/settings_providers.dart';
import 'package:agentic_journal/providers/sync_providers.dart';
import 'package:agentic_journal/providers/voice_providers.dart';
import 'package:agentic_journal/services/assistant_registration_service.dart';
import 'package:agentic_journal/services/supabase_service.dart';
import 'package:agentic_journal/ui/screens/settings_screen.dart';

/// A mock assistant service for testing.
class _MockAssistantService extends AssistantRegistrationService {
  _MockAssistantService() : super(isAndroid: false);

  @override
  Future<bool> isDefaultAssistant() async => false;

  @override
  Future<void> openAssistantSettings() async {}
}

void main() {
  group('Settings Conversation AI card', () {
    late SharedPreferences prefs;
    late _MockAssistantService mockService;

    setUp(() async {
      mockService = _MockAssistantService();
      SharedPreferences.setMockInitialValues({});
      prefs = await SharedPreferences.getInstance();
    });

    Widget buildSettingsScreen({Map<String, Object>? initialPrefs}) {
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
          isAuthenticatedProvider.overrideWithValue(false),
          currentUserProvider.overrideWithValue(null),
          pendingSyncCountProvider.overrideWith((ref) => Stream.value(0)),
          sessionCountProvider.overrideWith((ref) => Future.value(0)),
          sttModelReadyProvider.overrideWith((ref) => Future.value(false)),
          llmModelReadyProvider.overrideWith((ref) => Future.value(false)),
        ],
        child: MaterialApp(
          home: const SettingsScreen(),
          routes: {'/auth': (context) => const Scaffold()},
        ),
      );
    }

    testWidgets('renders Conversation AI card with both toggles', (
      WidgetTester tester,
    ) async {
      await tester.pumpWidget(buildSettingsScreen());
      await tester.pumpAndSettle();

      // Card title
      expect(find.text('Conversation AI'), findsOneWidget);

      // Both toggles visible
      expect(find.text('Prefer Claude when online'), findsOneWidget);
      expect(find.text('Journal only mode'), findsOneWidget);

      // Model status and personality section
      expect(find.text('Local AI: Not downloaded'), findsOneWidget);
      expect(find.text('Personality'), findsOneWidget);
      expect(find.text('Download'), findsOneWidget);
    });

    testWidgets('Prefer Claude toggle defaults to on', (
      WidgetTester tester,
    ) async {
      await tester.pumpWidget(buildSettingsScreen());
      await tester.pumpAndSettle();

      final switchFinder = find.widgetWithText(
        SwitchListTile,
        'Prefer Claude when online',
      );
      expect(switchFinder, findsOneWidget);

      final switchTile = tester.widget<SwitchListTile>(switchFinder);
      expect(switchTile.value, isTrue);
    });

    testWidgets('Journal only toggle defaults to off', (
      WidgetTester tester,
    ) async {
      await tester.pumpWidget(buildSettingsScreen());
      await tester.pumpAndSettle();

      final switchFinder = find.widgetWithText(
        SwitchListTile,
        'Journal only mode',
      );
      expect(switchFinder, findsOneWidget);

      final switchTile = tester.widget<SwitchListTile>(switchFinder);
      expect(switchTile.value, isFalse);
    });

    testWidgets('toggling Prefer Claude persists value', (
      WidgetTester tester,
    ) async {
      await tester.pumpWidget(buildSettingsScreen());
      await tester.pumpAndSettle();

      // Tap the Prefer Claude switch (defaults to on, so toggling turns it off).
      final switchFinder = find.widgetWithText(
        SwitchListTile,
        'Prefer Claude when online',
      );
      await tester.tap(switchFinder);
      await tester.pumpAndSettle();

      expect(prefs.getBool(preferClaudeKey), isFalse);
    });

    testWidgets('toggling Journal only persists value', (
      WidgetTester tester,
    ) async {
      await tester.pumpWidget(buildSettingsScreen());
      await tester.pumpAndSettle();

      // Scroll down to make the Journal only toggle visible.
      await tester.scrollUntilVisible(
        find.text('Journal only mode'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      final switchFinder = find.widgetWithText(
        SwitchListTile,
        'Journal only mode',
      );
      await tester.tap(switchFinder);
      await tester.pumpAndSettle();

      expect(prefs.getBool(journalOnlyModeKey), isTrue);
    });

    testWidgets('Prefer Claude is disabled when journal-only is on', (
      WidgetTester tester,
    ) async {
      // Set journal-only mode to true initially.
      SharedPreferences.setMockInitialValues({journalOnlyModeKey: true});
      prefs = await SharedPreferences.getInstance();

      await tester.pumpWidget(buildSettingsScreen());
      await tester.pumpAndSettle();

      final switchFinder = find.widgetWithText(
        SwitchListTile,
        'Prefer Claude when online',
      );
      final switchTile = tester.widget<SwitchListTile>(switchFinder);
      // The onChanged should be null (disabled).
      expect(switchTile.onChanged, isNull);
    });
  });
}
