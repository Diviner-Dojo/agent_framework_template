import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:agentic_journal/providers/llm_providers.dart';
import 'package:agentic_journal/providers/onboarding_providers.dart';

void main() {
  group('PreferClaudeNotifier', () {
    test('reads initial value from SharedPreferences', () async {
      SharedPreferences.setMockInitialValues({preferClaudeKey: true});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      expect(container.read(preferClaudeProvider), isTrue);
    });

    test('defaults to false when key not set', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      expect(container.read(preferClaudeProvider), isFalse);
    });

    test('setEnabled persists to SharedPreferences', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      expect(container.read(preferClaudeProvider), isFalse);

      await container.read(preferClaudeProvider.notifier).setEnabled(true);

      expect(container.read(preferClaudeProvider), isTrue);
      expect(prefs.getBool(preferClaudeKey), isTrue);
    });
  });

  group('JournalOnlyModeNotifier', () {
    test('defaults to false when key not set', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      expect(container.read(journalOnlyModeProvider), isFalse);
    });

    test('reads initial value from SharedPreferences', () async {
      SharedPreferences.setMockInitialValues({journalOnlyModeKey: true});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      expect(container.read(journalOnlyModeProvider), isTrue);
    });

    test('setEnabled persists to SharedPreferences', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      expect(container.read(journalOnlyModeProvider), isFalse);

      await container.read(journalOnlyModeProvider.notifier).setEnabled(true);

      expect(container.read(journalOnlyModeProvider), isTrue);
      expect(prefs.getBool(journalOnlyModeKey), isTrue);
    });

    test('toggle off persists correctly', () async {
      SharedPreferences.setMockInitialValues({journalOnlyModeKey: true});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      expect(container.read(journalOnlyModeProvider), isTrue);

      await container.read(journalOnlyModeProvider.notifier).setEnabled(false);

      expect(container.read(journalOnlyModeProvider), isFalse);
      expect(prefs.getBool(journalOnlyModeKey), isFalse);
    });
  });
}
