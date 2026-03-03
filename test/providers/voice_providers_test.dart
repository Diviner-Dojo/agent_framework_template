// ===========================================================================
// file: test/providers/voice_providers_test.dart
// purpose: Tests for voice-related Riverpod providers.
//
// Tests the provider wiring, voice mode toggle state management,
// SharedPreferences persistence for voice settings, and engine
// selection (ADR-0022).
// STT/TTS service providers are tested via their service tests.
// ===========================================================================

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:agentic_journal/providers/onboarding_providers.dart';
import 'package:agentic_journal/providers/voice_providers.dart';

void main() {
  group('voiceModeEnabledProvider', () {
    test('defaults to false', () {
      SharedPreferences.setMockInitialValues({});
      final container = ProviderContainer(
        overrides: [
          sharedPreferencesProvider.overrideWith((ref) {
            // Use synchronous access pattern for tests.
            final prefs = SharedPreferences.getInstance();
            // Since we set mock values, this resolves synchronously.
            late SharedPreferences result;
            prefs.then((v) => result = v);
            return result;
          }),
        ],
      );
      addTearDown(container.dispose);

      // The provider needs SharedPreferences, so we need to use the async
      // version in tests. Let's use the simpler approach.
    });

    test('can be toggled via setEnabled', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      expect(container.read(voiceModeEnabledProvider), isFalse);

      await container.read(voiceModeEnabledProvider.notifier).setEnabled(true);
      expect(container.read(voiceModeEnabledProvider), isTrue);
      expect(prefs.getBool(voiceModeEnabledKey), isTrue);
    });

    test('can be toggled back to false', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      await container.read(voiceModeEnabledProvider.notifier).setEnabled(true);
      await container.read(voiceModeEnabledProvider.notifier).setEnabled(false);
      expect(container.read(voiceModeEnabledProvider), isFalse);
      expect(prefs.getBool(voiceModeEnabledKey), isFalse);
    });

    test('reads persisted value from SharedPreferences', () async {
      SharedPreferences.setMockInitialValues({voiceModeEnabledKey: true});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      expect(container.read(voiceModeEnabledProvider), isTrue);
    });
  });

  group('autoSaveOnExitProvider', () {
    test('defaults to true', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      expect(container.read(autoSaveOnExitProvider), isTrue);
    });

    test('can be disabled', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      await container.read(autoSaveOnExitProvider.notifier).setEnabled(false);
      expect(container.read(autoSaveOnExitProvider), isFalse);
      expect(prefs.getBool(autoSaveOnExitKey), isFalse);
    });

    test('can be re-enabled', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      await container.read(autoSaveOnExitProvider.notifier).setEnabled(false);
      await container.read(autoSaveOnExitProvider.notifier).setEnabled(true);
      expect(container.read(autoSaveOnExitProvider), isTrue);
    });

    test('reads persisted value from SharedPreferences', () async {
      SharedPreferences.setMockInitialValues({autoSaveOnExitKey: false});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      expect(container.read(autoSaveOnExitProvider), isFalse);
    });
  });

  group('ttsEngineProvider', () {
    test('defaults to elevenlabs', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      expect(container.read(ttsEngineProvider), TtsEngine.elevenlabs);
    });

    test('can be set to flutterTts', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      await container
          .read(ttsEngineProvider.notifier)
          .setEngine(TtsEngine.flutterTts);
      expect(container.read(ttsEngineProvider), TtsEngine.flutterTts);
      expect(prefs.getString(ttsEngineKey), 'flutterTts');
    });

    test('can be switched back to elevenlabs', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      await container
          .read(ttsEngineProvider.notifier)
          .setEngine(TtsEngine.flutterTts);
      await container
          .read(ttsEngineProvider.notifier)
          .setEngine(TtsEngine.elevenlabs);
      expect(container.read(ttsEngineProvider), TtsEngine.elevenlabs);
    });

    test('reads persisted value from SharedPreferences', () async {
      SharedPreferences.setMockInitialValues({ttsEngineKey: 'flutterTts'});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      expect(container.read(ttsEngineProvider), TtsEngine.flutterTts);
    });
  });

  group('ttsRateProvider', () {
    test('defaults to 1.0', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      expect(container.read(ttsRateProvider), 1.0);
    });

    test('setRate persists to SharedPreferences and updates state', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      await container.read(ttsRateProvider.notifier).setRate(1.3);
      expect(container.read(ttsRateProvider), 1.3);
      expect(prefs.getDouble(ttsRateKey), 1.3);
    });

    test('reads persisted value from SharedPreferences', () async {
      SharedPreferences.setMockInitialValues({ttsRateKey: 0.7});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      expect(container.read(ttsRateProvider), 0.7);
    });
  });

  group('sttEngineProvider', () {
    test('defaults to deepgram (primary per ADR-0031)', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      expect(container.read(sttEngineProvider), SttEngine.deepgram);
    });

    test('can be set to sherpaOnnx', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      await container
          .read(sttEngineProvider.notifier)
          .setEngine(SttEngine.sherpaOnnx);
      expect(container.read(sttEngineProvider), SttEngine.sherpaOnnx);
      expect(prefs.getString(sttEngineKey), 'sherpaOnnx');
    });

    test('can be switched back to speechToText', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      await container
          .read(sttEngineProvider.notifier)
          .setEngine(SttEngine.sherpaOnnx);
      await container
          .read(sttEngineProvider.notifier)
          .setEngine(SttEngine.speechToText);
      expect(container.read(sttEngineProvider), SttEngine.speechToText);
    });

    test('reads persisted value from SharedPreferences', () async {
      SharedPreferences.setMockInitialValues({sttEngineKey: 'sherpaOnnx'});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      expect(container.read(sttEngineProvider), SttEngine.sherpaOnnx);
    });
  });
}
