// ===========================================================================
// file: test/services/fallback_tts_service_test.dart
// purpose: Tests for FallbackTtsService decorator.
//
// Covers:
//   - Falls back when primary throws on speak()
//   - onFallbackActivated called exactly once
//   - Stays on fallback after activation
//   - stop() calls both services
//   - setSpeechRate() applies to both services
// ===========================================================================

import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/services/fallback_tts_service.dart';
import 'package:agentic_journal/services/text_to_speech_service.dart';

// ===========================================================================
// Mock TTS services
// ===========================================================================

class _MockTtsService implements TextToSpeechService {
  bool _initialized = false;
  bool _isSpeaking = false;
  int speakCallCount = 0;
  int stopCallCount = 0;
  int setSpeechRateCallCount = 0;
  int disposeCallCount = 0;
  final bool throwOnSpeak;
  final bool throwOnInitialize;
  final bool throwOnStop;

  _MockTtsService({
    this.throwOnSpeak = false,
    this.throwOnInitialize = false,
    this.throwOnStop = false,
  });

  @override
  Future<void> initialize() async {
    if (throwOnInitialize) {
      throw Exception('initialize failed');
    }
    _initialized = true;
  }

  @override
  Future<void> speak(String text) async {
    speakCallCount++;
    if (throwOnSpeak) {
      throw Exception('speak failed');
    }
    _isSpeaking = true;
    _isSpeaking = false;
  }

  @override
  Future<void> stop() async {
    stopCallCount++;
    if (throwOnStop) {
      throw Exception('stop failed');
    }
    _isSpeaking = false;
  }

  @override
  bool get isSpeaking => _isSpeaking;

  @override
  Future<void> setSpeechRate(double rate) async {
    setSpeechRateCallCount++;
  }

  @override
  void dispose() {
    disposeCallCount++;
  }

  bool get isInitialized => _initialized;
}

// ===========================================================================
// Tests
// ===========================================================================

void main() {
  group('FallbackTtsService', () {
    test('falls back when primary throws on speak()', () async {
      final primary = _MockTtsService(throwOnSpeak: true);
      final fallback = _MockTtsService();

      final service = FallbackTtsService(primary: primary, fallback: fallback);

      await service.initialize();
      await service.speak('Hello');

      // Primary threw, fallback should have been called once.
      expect(primary.speakCallCount, 1);
      expect(fallback.speakCallCount, 1);
      expect(service.usingFallback, isTrue);
    });

    test('onFallbackActivated called exactly once', () async {
      final primary = _MockTtsService(throwOnSpeak: true);
      final fallback = _MockTtsService();
      int activationCount = 0;

      final service = FallbackTtsService(
        primary: primary,
        fallback: fallback,
        onFallbackActivated: () => activationCount++,
      );

      await service.initialize();

      // Call speak three times — each time primary will throw.
      await service.speak('First');
      await service.speak('Second');
      await service.speak('Third');

      // onFallbackActivated must fire only once.
      expect(activationCount, 1);
    });

    test('stays on fallback after activation', () async {
      final primary = _MockTtsService(throwOnSpeak: true);
      final fallback = _MockTtsService();

      final service = FallbackTtsService(primary: primary, fallback: fallback);

      await service.initialize();
      await service.speak('Hello'); // Activates fallback.
      await service.speak('World'); // Already on fallback.

      // Primary only called once (the first speak that threw).
      expect(primary.speakCallCount, 1);
      // Fallback called for both speak calls.
      expect(fallback.speakCallCount, 2);
    });

    test('stop() calls both services', () async {
      final primary = _MockTtsService();
      final fallback = _MockTtsService();

      final service = FallbackTtsService(primary: primary, fallback: fallback);

      await service.initialize();
      await service.stop();

      expect(primary.stopCallCount, 1);
      expect(fallback.stopCallCount, 1);
    });

    test(
      'stop() calls fallback even when primary throws (regression)',
      () async {
        // Regression: if primary.stop() throws (broken state), fallback.stop()
        // must still run so fallback audio is released.
        final primary = _MockTtsService(throwOnStop: true);
        final fallback = _MockTtsService();

        final service = FallbackTtsService(
          primary: primary,
          fallback: fallback,
        );

        await service.initialize();
        // Should not throw even though primary.stop() throws.
        await service.stop();

        expect(primary.stopCallCount, 1);
        expect(fallback.stopCallCount, 1);
      },
    );

    test('setSpeechRate() applies to both services', () async {
      final primary = _MockTtsService();
      final fallback = _MockTtsService();

      final service = FallbackTtsService(primary: primary, fallback: fallback);

      await service.initialize();
      await service.setSpeechRate(1.5);

      expect(primary.setSpeechRateCallCount, 1);
      expect(fallback.setSpeechRateCallCount, 1);
    });

    test('initialize() activates fallback when primary throws', () async {
      final primary = _MockTtsService(throwOnInitialize: true);
      final fallback = _MockTtsService();
      bool activated = false;

      final service = FallbackTtsService(
        primary: primary,
        fallback: fallback,
        onFallbackActivated: () => activated = true,
      );

      await service.initialize();

      expect(service.usingFallback, isTrue);
      expect(activated, isTrue);
      // Fallback is ready even though primary failed to initialize.
      expect(fallback.isInitialized, isTrue);
    });

    test('isSpeaking reflects primary when not fallen back', () async {
      final primary = _MockTtsService();
      final fallback = _MockTtsService();

      final service = FallbackTtsService(primary: primary, fallback: fallback);

      await service.initialize();
      // Neither is speaking.
      expect(service.isSpeaking, isFalse);
    });

    test('dispose() calls both services', () async {
      final primary = _MockTtsService();
      final fallback = _MockTtsService();

      final service = FallbackTtsService(primary: primary, fallback: fallback);

      service.dispose();

      expect(primary.disposeCallCount, 1);
      expect(fallback.disposeCallCount, 1);
    });

    test('uses primary when no failure occurs', () async {
      final primary = _MockTtsService();
      final fallback = _MockTtsService();

      final service = FallbackTtsService(primary: primary, fallback: fallback);

      await service.initialize();
      await service.speak('Normal speech');

      expect(primary.speakCallCount, 1);
      expect(fallback.speakCallCount, 0);
      expect(service.usingFallback, isFalse);
    });
  });
}
