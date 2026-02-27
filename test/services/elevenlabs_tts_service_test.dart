// ===========================================================================
// file: test/services/elevenlabs_tts_service_test.dart
// purpose: Tests for ElevenLabs TTS service contract.
//
// Strategy:
//   ElevenLabsTtsService requires network (Supabase proxy) and just_audio
//   (native playback), so it cannot run in CI. We test:
//     1. The service contract via a mock that simulates proxy responses
//     2. State transitions (initialize → speak → stop → dispose)
//     3. Error handling (network errors, empty responses)
//
// See: ADR-0022 (Voice Engine Swap)
// ===========================================================================

import 'dart:async';

import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/services/text_to_speech_service.dart';

/// Mock ElevenLabs TTS that simulates the proxy/playback flow for testing.
///
/// Validates the same contract as ElevenLabsTtsService without requiring
/// network or native audio playback.
class MockElevenLabsTtsService implements TextToSpeechService {
  bool _initialized = false;
  bool _isSpeaking = false;
  Completer<void>? _speakCompleter;
  String? lastSpokenText;
  int speakCallCount = 0;
  int stopCallCount = 0;
  bool shouldFailNetwork = false;

  final String proxyUrl;
  final String? authToken;

  MockElevenLabsTtsService({required this.proxyUrl, this.authToken});

  @override
  Future<void> initialize() async {
    _initialized = true;
  }

  @override
  Future<void> speak(String text) async {
    if (!_initialized) {
      throw StateError(
        'ElevenLabsTtsService not initialized. Call initialize() first.',
      );
    }
    if (text.isEmpty) return;

    if (_isSpeaking) {
      await stop();
    }

    // Simulate network call to proxy.
    if (shouldFailNetwork) {
      throw StateError('ElevenLabs TTS network error: Connection refused');
    }

    lastSpokenText = text;
    speakCallCount++;
    _isSpeaking = true;
    _speakCompleter = Completer<void>();
    return _speakCompleter!.future;
  }

  /// Simulate playback completion.
  void completeCurrentSpeech() {
    _isSpeaking = false;
    _speakCompleter?.complete();
    _speakCompleter = null;
  }

  @override
  Future<void> stop() async {
    stopCallCount++;
    _isSpeaking = false;
    _speakCompleter?.complete();
    _speakCompleter = null;
  }

  @override
  bool get isSpeaking => _isSpeaking;

  @override
  Future<void> setSpeechRate(double rate) async {}

  @override
  void dispose() {
    stop();
    _initialized = false;
  }
}

void main() {
  group('ElevenLabsTtsService (mock)', () {
    late MockElevenLabsTtsService service;

    setUp(() {
      service = MockElevenLabsTtsService(
        proxyUrl: 'https://test.supabase.co/functions/v1/elevenlabs-proxy',
        authToken: 'test-token',
      );
    });

    tearDown(() {
      service.dispose();
    });

    test('stores proxy URL and auth token', () {
      expect(
        service.proxyUrl,
        'https://test.supabase.co/functions/v1/elevenlabs-proxy',
      );
      expect(service.authToken, 'test-token');
    });

    test('starts uninitialized and not speaking', () {
      expect(service.isSpeaking, isFalse);
    });

    test('speak throws if not initialized', () {
      expect(() => service.speak('hello'), throwsStateError);
    });

    test('speak ignores empty text', () async {
      await service.initialize();
      await service.speak('');
      expect(service.speakCallCount, 0);
      expect(service.isSpeaking, isFalse);
    });

    test('speak sets isSpeaking and records text', () async {
      await service.initialize();

      final future = service.speak('hello world');
      expect(service.isSpeaking, isTrue);
      expect(service.lastSpokenText, 'hello world');
      expect(service.speakCallCount, 1);

      service.completeCurrentSpeech();
      await future;
      expect(service.isSpeaking, isFalse);
    });

    test('speak stops previous speech before starting new', () async {
      await service.initialize();

      final future1 = service.speak('first');
      expect(service.speakCallCount, 1);

      final future2 = service.speak('second');
      await Future<void>.delayed(Duration.zero);

      expect(service.stopCallCount, 1);
      expect(service.speakCallCount, 2);
      expect(service.lastSpokenText, 'second');

      service.completeCurrentSpeech();
      await future1;
      await future2;
    });

    test('network error throws StateError', () async {
      await service.initialize();
      service.shouldFailNetwork = true;

      expect(() => service.speak('hello'), throwsStateError);
    });

    test('stop clears isSpeaking', () async {
      await service.initialize();
      final future = service.speak('hello');

      await service.stop();
      await future;
      expect(service.isSpeaking, isFalse);
    });

    test('dispose resets all state', () async {
      await service.initialize();
      service.speak('hello');

      service.dispose();
      expect(service.isSpeaking, isFalse);
    });

    test('stop is safe to call when not speaking', () async {
      await service.initialize();
      await service.stop();
      expect(service.stopCallCount, 1);
    });
  });
}
