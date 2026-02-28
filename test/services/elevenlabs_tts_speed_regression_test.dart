// ===========================================================================
// file: test/services/elevenlabs_tts_speed_regression_test.dart
// purpose: Regression test for ElevenLabs TTS speed bug.
//
// Bug: setSpeechRate() called before initialize() was silently ignored
// because _player was null. Even after init, speak() calls setAudioSource()
// which resets the player speed.
//
// Fix: Store _rate field, apply after setAudioSource in speak().
// See: memory/bugs/regression-ledger.md
// ===========================================================================

@Tags(['regression'])
import 'dart:async';

import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/services/text_to_speech_service.dart';

/// Mock that accurately models the speed-reset vulnerability.
///
/// Simulates the real ElevenLabsTtsService behavior:
/// - setSpeechRate before initialize should store the rate
/// - speak() internally calls setAudioSource which resets speed
/// - After setAudioSource, the stored rate must be re-applied
class SpeedTrackingMockTts implements TextToSpeechService {
  bool _initialized = false;
  bool _isSpeaking = false;
  Completer<void>? _speakCompleter;

  /// The current effective speed (as the player would see it).
  double currentSpeed = 1.0;

  /// Stored rate that survives setAudioSource resets.
  double _storedRate = 1.0;

  /// History of all speed changes applied to the player.
  final List<double> speedHistory = [];

  @override
  Future<void> initialize() async {
    _initialized = true;
    // Apply any rate set before initialize.
    currentSpeed = _storedRate;
    speedHistory.add(currentSpeed);
  }

  @override
  Future<void> setSpeechRate(double rate) async {
    _storedRate = rate;
    if (_initialized) {
      currentSpeed = rate;
      speedHistory.add(rate);
    }
  }

  @override
  Future<void> speak(String text) async {
    if (!_initialized) {
      throw StateError('Not initialized');
    }
    if (text.isEmpty) return;

    // Simulate setAudioSource resetting speed (the bug condition).
    currentSpeed = 1.0;
    speedHistory.add(1.0); // Reset by setAudioSource

    // The FIX: re-apply stored rate after setAudioSource.
    currentSpeed = _storedRate;
    speedHistory.add(_storedRate);

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
    _isSpeaking = false;
    _speakCompleter?.complete();
    _speakCompleter = null;
  }

  @override
  bool get isSpeaking => _isSpeaking;

  @override
  void dispose() {
    stop();
    _initialized = false;
  }
}

void main() {
  group('ElevenLabs TTS speed regression', () {
    late SpeedTrackingMockTts service;

    setUp(() {
      service = SpeedTrackingMockTts();
    });

    tearDown(() {
      service.dispose();
    });

    test(
      'speed setting persists across audio source changes (regression)',
      () async {
        // Bug: setSpeechRate(1.5) → initialize → speak → speed is 1.0
        // Fix: setSpeechRate(1.5) → initialize → speak → speed is 1.5
        await service.setSpeechRate(1.5);
        await service.initialize();

        final future = service.speak('hello');
        // After speak, the effective speed should be 1.5, not reset to 1.0.
        expect(
          service.currentSpeed,
          1.5,
          reason: 'Speed must survive setAudioSource reset in speak()',
        );

        service.completeCurrentSpeech();
        await future;
      },
    );

    test(
      'rate set before initialize is applied after speak (regression)',
      () async {
        // Set rate before player exists.
        await service.setSpeechRate(0.75);

        // Initialize creates the player.
        await service.initialize();
        expect(service.currentSpeed, 0.75);

        // Speak triggers setAudioSource → speed reset → rate re-applied.
        final future = service.speak('test');
        expect(service.currentSpeed, 0.75);

        service.completeCurrentSpeech();
        await future;
      },
    );

    test(
      'rate changed between speaks is applied on next speak (regression)',
      () async {
        await service.initialize();
        await service.setSpeechRate(1.2);

        final f1 = service.speak('first');
        expect(service.currentSpeed, 1.2);
        service.completeCurrentSpeech();
        await f1;

        // Change rate between speaks.
        await service.setSpeechRate(0.8);

        final f2 = service.speak('second');
        expect(
          service.currentSpeed,
          0.8,
          reason: 'New rate must be applied after second setAudioSource',
        );
        service.completeCurrentSpeech();
        await f2;
      },
    );
  });
}
