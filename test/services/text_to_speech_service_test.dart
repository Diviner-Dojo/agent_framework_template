// ===========================================================================
// file: test/services/text_to_speech_service_test.dart
// purpose: Tests for TextToSpeechService contract via mock implementation.
//
// Strategy:
//   FlutterTextToSpeechService wraps flutter_tts which requires a device.
//   We test the abstract contract via a mock that validates state transitions
//   and speak/stop/completion flow.
// ===========================================================================

import 'dart:async';

import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/services/text_to_speech_service.dart';

/// Mock implementation of TextToSpeechService for testing.
class MockTextToSpeechService implements TextToSpeechService {
  bool _initialized = false;
  bool _isSpeaking = false;
  Completer<void>? _speakCompleter;
  String? lastSpokenText;
  int speakCallCount = 0;
  int stopCallCount = 0;

  @override
  Future<void> initialize() async {
    _initialized = true;
  }

  @override
  Future<void> speak(String text) async {
    if (!_initialized) {
      throw StateError('Not initialized');
    }
    if (text.isEmpty) return;

    if (_isSpeaking) {
      await stop();
    }

    lastSpokenText = text;
    speakCallCount++;
    _isSpeaking = true;
    _speakCompleter = Completer<void>();
    return _speakCompleter!.future;
  }

  /// Simulate speech completion (for testing).
  void completeCurrentSpeech() {
    _isSpeaking = false;
    _speakCompleter?.complete();
    _speakCompleter = null;
  }

  /// Simulate speech error (for testing).
  void failCurrentSpeech(Object error) {
    _isSpeaking = false;
    _speakCompleter?.completeError(error);
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
  group('TextToSpeechService (mock)', () {
    late MockTextToSpeechService service;

    setUp(() {
      service = MockTextToSpeechService();
    });

    tearDown(() {
      service.dispose();
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

      // Start speaking in background (don't await — it completes on callback).
      final future = service.speak('hello world');
      expect(service.isSpeaking, isTrue);
      expect(service.lastSpokenText, 'hello world');
      expect(service.speakCallCount, 1);

      // Complete the speech.
      service.completeCurrentSpeech();
      await future;
      expect(service.isSpeaking, isFalse);
    });

    test('speak stops previous speech before starting new', () async {
      await service.initialize();

      // Start first speech (don't await — it completes on callback).
      final future1 = service.speak('first');
      expect(service.isSpeaking, isTrue);
      expect(service.speakCallCount, 1);

      // Start second speech — this internally awaits stop() then starts new.
      // We need to allow the microtask to run.
      final future2 = service.speak('second');
      await Future<void>.delayed(Duration.zero);

      // First speech was stopped, second is now active.
      expect(service.stopCallCount, 1);
      expect(service.speakCallCount, 2);
      expect(service.lastSpokenText, 'second');
      expect(service.isSpeaking, isTrue);

      // Complete second speech.
      service.completeCurrentSpeech();
      await future1; // First was completed by stop.
      await future2;
    });

    test('stop clears isSpeaking', () async {
      await service.initialize();
      final future = service.speak('hello');

      await service.stop();
      await future;
      expect(service.isSpeaking, isFalse);
    });

    test('speech error propagates', () async {
      await service.initialize();
      final future = service.speak('hello');

      service.failCurrentSpeech(StateError('TTS error'));
      expect(future, throwsStateError);
    });

    test('dispose resets all state', () async {
      await service.initialize();
      service.speak('hello');

      service.dispose();
      expect(service.isSpeaking, isFalse);
    });

    test('stop is safe to call when not speaking', () async {
      await service.initialize();
      await service.stop(); // Should not throw.
      expect(service.stopCallCount, 1);
    });
  });
}
