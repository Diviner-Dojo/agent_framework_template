// ===========================================================================
// file: test/providers/voice_providers_test.dart
// purpose: Tests for voice-related Riverpod providers.
//
// Tests the provider wiring and voice mode toggle state management.
// STT/TTS service providers are tested via their service tests.
// ===========================================================================

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/providers/voice_providers.dart';
import 'package:agentic_journal/services/speech_recognition_service.dart';
import 'package:agentic_journal/services/text_to_speech_service.dart';

void main() {
  group('voiceModeEnabledProvider', () {
    test('defaults to false', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      expect(container.read(voiceModeEnabledProvider), isFalse);
    });

    test('can be toggled to true', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      container.read(voiceModeEnabledProvider.notifier).state = true;
      expect(container.read(voiceModeEnabledProvider), isTrue);
    });

    test('can be toggled back to false', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      container.read(voiceModeEnabledProvider.notifier).state = true;
      container.read(voiceModeEnabledProvider.notifier).state = false;
      expect(container.read(voiceModeEnabledProvider), isFalse);
    });
  });

  group('speechRecognitionServiceProvider', () {
    test('provides a SpeechRecognitionService instance', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      final service = container.read(speechRecognitionServiceProvider);
      expect(service, isA<SpeechRecognitionService>());
    });

    test('service starts uninitialized', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      final service = container.read(speechRecognitionServiceProvider);
      expect(service.isInitialized, isFalse);
      expect(service.isListening, isFalse);
    });
  });

  group('textToSpeechServiceProvider', () {
    test('provides a TextToSpeechService instance', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      final service = container.read(textToSpeechServiceProvider);
      expect(service, isA<TextToSpeechService>());
    });
  });
}
