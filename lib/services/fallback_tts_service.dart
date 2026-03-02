// ===========================================================================
// file: lib/services/fallback_tts_service.dart
// purpose: FallbackTtsService — wraps a primary TTS with an automatic fallback.
//
// When ElevenLabs (or any primary TTS) throws on speak() or initialize(),
// this decorator switches permanently to the fallback for the remainder of
// the session and fires an optional onFallbackActivated callback so the UI
// can notify the user.
//
// See: Bug fix sprint — graceful TTS degradation
// ===========================================================================

import 'text_to_speech_service.dart';

/// Wraps a primary [TextToSpeechService] with an automatic fallback.
///
/// On any [Exception] from [primary].speak(), switches permanently to
/// [fallback] for the remainder of the session and fires [onFallbackActivated].
/// Both services are initialized eagerly so the fallback is ready before it
/// is needed.
class FallbackTtsService implements TextToSpeechService {
  final TextToSpeechService _primary;
  final TextToSpeechService _fallback;

  /// Called once when the fallback is first activated (primary failed).
  final void Function()? onFallbackActivated;

  bool _usingFallback = false;

  /// Create a [FallbackTtsService].
  FallbackTtsService({
    required TextToSpeechService primary,
    required TextToSpeechService fallback,
    this.onFallbackActivated,
  }) : _primary = primary,
       _fallback = fallback;

  /// Whether the service is currently using the fallback.
  bool get usingFallback => _usingFallback;

  @override
  Future<void> initialize() async {
    // Always initialize fallback so it is ready if primary fails.
    await _fallback.initialize();
    try {
      await _primary.initialize();
    } on Exception {
      _activateFallback();
    }
  }

  @override
  Future<void> speak(String text) async {
    if (_usingFallback) {
      return _fallback.speak(text);
    }
    try {
      await _primary.speak(text);
    } on Exception {
      _activateFallback();
      await _fallback.speak(text);
    }
  }

  @override
  Future<void> stop() async {
    try {
      await _primary.stop();
    } on Exception {
      // Primary may be in a broken state — ensure fallback stop still runs.
    }
    await _fallback.stop();
  }

  @override
  bool get isSpeaking =>
      _usingFallback ? _fallback.isSpeaking : _primary.isSpeaking;

  @override
  Future<void> setSpeechRate(double rate) async {
    await _primary.setSpeechRate(rate);
    await _fallback.setSpeechRate(rate);
  }

  @override
  void dispose() {
    _primary.dispose();
    _fallback.dispose();
  }

  void _activateFallback() {
    if (!_usingFallback) {
      _usingFallback = true;
      onFallbackActivated?.call();
    }
  }
}
