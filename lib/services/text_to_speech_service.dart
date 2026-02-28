// ===========================================================================
// file: lib/services/text_to_speech_service.dart
// purpose: Abstract TTS interface + flutter_tts implementation.
//
// Architecture (ADR-0015):
//   Uses the Android system TTS engine via flutter_tts — fully offline,
//   no model download needed. The assistant's response is spoken aloud
//   after it arrives, with a Completer-based Future for tracking when
//   speech finishes.
//
// See: ADR-0015 (Voice Mode Architecture)
// ===========================================================================

import 'dart:async';

import 'package:flutter_tts/flutter_tts.dart';

/// Abstract interface for text-to-speech services.
///
/// Implementations wrap a specific TTS engine. The abstract interface
/// enables mock implementations for testing.
abstract class TextToSpeechService {
  /// Initialize the TTS engine with default settings.
  Future<void> initialize();

  /// Speak the given [text]. Returns a Future that completes when
  /// speech finishes or is interrupted.
  Future<void> speak(String text);

  /// Stop any ongoing speech.
  Future<void> stop();

  /// Whether TTS is currently speaking.
  bool get isSpeaking;

  /// Set the speech rate (0.0–1.5 on most platforms, default 1.0).
  Future<void> setSpeechRate(double rate);

  /// Release resources.
  void dispose();
}

/// flutter_tts implementation of [TextToSpeechService].
///
/// Delegates to the Android system TTS engine. Uses a [Completer]
/// to convert the completion callback into a Future, so callers can
/// await speech completion.
// coverage:ignore-start
class FlutterTextToSpeechService implements TextToSpeechService {
  FlutterTts? _tts;
  bool _isSpeaking = false;
  Completer<void>? _speakCompleter;

  @override
  Future<void> initialize() async {
    _tts = FlutterTts();

    await _tts!.setLanguage('en-US');
    await _tts!.setSpeechRate(1.0);
    await _tts!.setVolume(1.0);
    await _tts!.setPitch(1.0);

    _tts!.setStartHandler(() {
      _isSpeaking = true;
    });

    _tts!.setCompletionHandler(() {
      _isSpeaking = false;
      _speakCompleter?.complete();
      _speakCompleter = null;
    });

    _tts!.setCancelHandler(() {
      _isSpeaking = false;
      _speakCompleter?.complete();
      _speakCompleter = null;
    });

    _tts!.setErrorHandler((dynamic message) {
      _isSpeaking = false;
      _speakCompleter?.completeError(StateError('TTS error: $message'));
      _speakCompleter = null;
    });
  }

  @override
  Future<void> setSpeechRate(double rate) async {
    if (_tts == null) return;
    await _tts!.setSpeechRate(rate);
  }

  @override
  Future<void> speak(String text) async {
    if (_tts == null) {
      throw StateError(
        'TextToSpeechService not initialized. Call initialize() first.',
      );
    }
    if (text.isEmpty) return;

    // Cancel any in-progress speech before starting new.
    if (_isSpeaking) {
      await stop();
    }

    _speakCompleter = Completer<void>();
    await _tts!.speak(text);
    return _speakCompleter!.future;
  }

  @override
  Future<void> stop() async {
    if (_tts == null) return;
    await _tts!.stop();
    _isSpeaking = false;
    _speakCompleter?.complete();
    _speakCompleter = null;
  }

  @override
  bool get isSpeaking => _isSpeaking;

  @override
  void dispose() {
    stop();
    _tts?.stop();
    _tts = null;
  }
}

// coverage:ignore-end
