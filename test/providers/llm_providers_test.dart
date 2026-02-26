import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:agentic_journal/layers/local_llm_layer.dart';
import 'package:agentic_journal/models/personality_config.dart';
import 'package:agentic_journal/providers/llm_providers.dart';
import 'package:agentic_journal/providers/onboarding_providers.dart';
import 'package:agentic_journal/providers/personality_providers.dart';
import 'package:agentic_journal/services/local_llm_service.dart';

/// A mock LocalLlmService for testing.
class _MockLocalLlmService extends LocalLlmService {
  final bool _loaded;

  _MockLocalLlmService({bool loaded = false}) : _loaded = loaded;

  @override
  bool get isModelLoaded => _loaded;

  @override
  Future<void> loadModel(String modelPath) async {}

  @override
  Future<void> unloadModel() async {}

  @override
  Future<String> generate({
    required List<Map<String, String>> messages,
    String? systemPrompt,
  }) async {
    return 'Mock response';
  }

  @override
  void dispose() {}
}

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

    test('defaults to true when key not set', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      expect(container.read(preferClaudeProvider), isTrue);
    });

    test('setEnabled persists to SharedPreferences', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      expect(container.read(preferClaudeProvider), isTrue);

      await container.read(preferClaudeProvider.notifier).setEnabled(false);

      expect(container.read(preferClaudeProvider), isFalse);
      expect(prefs.getBool(preferClaudeKey), isFalse);
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

  group('localLlmServiceProvider', () {
    test('defaults to null', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      expect(container.read(localLlmServiceProvider), isNull);
    });

    test('can be set to a service instance', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      final mockService = _MockLocalLlmService(loaded: true);

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      container.read(localLlmServiceProvider.notifier).state = mockService;
      expect(container.read(localLlmServiceProvider), mockService);
    });
  });

  group('localLlmLayerProvider', () {
    test('returns null when service is null', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      expect(container.read(localLlmLayerProvider), isNull);
    });

    test('returns null when service is not loaded', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      final mockService = _MockLocalLlmService(loaded: false);

      final container = ProviderContainer(
        overrides: [
          sharedPreferencesProvider.overrideWithValue(prefs),
          localLlmServiceProvider.overrideWith((ref) => mockService),
        ],
      );
      addTearDown(container.dispose);

      expect(container.read(localLlmLayerProvider), isNull);
    });

    test('returns LocalLlmLayer when service is loaded', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      final mockService = _MockLocalLlmService(loaded: true);

      final container = ProviderContainer(
        overrides: [
          sharedPreferencesProvider.overrideWithValue(prefs),
          localLlmServiceProvider.overrideWith((ref) => mockService),
          personalityConfigProvider.overrideWith(
            () => _FakePersonalityNotifier(),
          ),
        ],
      );
      addTearDown(container.dispose);

      final layer = container.read(localLlmLayerProvider);
      expect(layer, isNotNull);
      expect(layer, isA<LocalLlmLayer>());
    });
  });
}

/// A simple personality notifier that returns default config.
class _FakePersonalityNotifier extends PersonalityNotifier {
  @override
  PersonalityConfig build() => PersonalityConfig.defaults();
}
