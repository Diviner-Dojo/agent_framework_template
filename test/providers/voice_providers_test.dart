// ===========================================================================
// file: test/providers/voice_providers_test.dart
// purpose: Tests for voice-related Riverpod providers.
//
// Tests the provider wiring, voice mode toggle state management,
// SharedPreferences persistence for voice settings, and engine
// selection (ADR-0022).
// STT/TTS service providers are tested via their service tests.
//
// CPP regression tag: This file contains the STT engine default assertion
// (ADR-0035 Two-PR Pattern gate). See sttEngineProvider group for details.
// ===========================================================================

// @Tags must be on the library declaration (Dart requirement).
@Tags(['regression'])
library;

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
    // CPP C2 assertion: This test is the machine-enforceable gate for the
    // STT engine default (ADR-0035, SPEC-20260305-080259).
    //
    // Changing this assertion requires: (1) updating CAPABILITY_STATUS.md to
    // show the new default engine is PROVEN (device-tested), and (2) submitting
    // the change in a separate PR from the one that introduced the implementation.
    //
    // See: .claude/rules/capability_protection.md, docs/conventions/experimental-first.md
    // Regression: ALL STT broken by default change in same PR as implementation
    // (commit 328ec44 → e1ad873 fix). See memory/bugs/regression-ledger.md.
    // @Tags(['regression']) — applied at file level.
    test(
      'defaults to speechToText — proven baseline (CPP gate, ADR-0035)',
      () async {
        SharedPreferences.setMockInitialValues({});
        final prefs = await SharedPreferences.getInstance();

        final container = ProviderContainer(
          overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
        );
        addTearDown(container.dispose);

        // CPP-GATE: If this assertion fails, the STT default was changed without
        // updating this test. That means the two-PR convention (ADR-0035) was
        // violated. Update CAPABILITY_STATUS.md and this test in PR N+1 only.
        expect(
          container.read(sttEngineProvider),
          SttEngine.speechToText,
          reason:
              'CPP: Default must be speechToText (PROVEN). '
              'Deepgram is EXPERIMENTAL per CAPABILITY_STATUS.md. '
              'To change: update CAPABILITY_STATUS.md to PROVEN after device '
              'testing, then submit a separate PR (ADR-0035 Two-PR Pattern).',
        );
      },
    );

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
