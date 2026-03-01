// ===========================================================================
// file: lib/services/speech_to_text_stt_service.dart
// purpose: speech_to_text package implementation of SpeechRecognitionService.
//
// Uses Google's on-device speech recognizer via the speech_to_text package.
// No model download required — uses the system recognizer built into Android.
//
// Key behavior differences from sherpa_onnx:
//   - No model download needed (uses system recognizer)
//   - initialize() ignores modelPath (interface compatibility)
//   - Auto-restarts listener on Android silence timeout (transparent to
//     the orchestrator, which only sees the result stream)
//   - Uses SpeechToText's onResult callback mapped to SpeechResult
//
// See: ADR-0022 (Voice Engine Swap)
// ===========================================================================

import 'dart:async';

import 'package:speech_to_text/speech_recognition_result.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;

import 'audio_file_service.dart';
import 'speech_recognition_service.dart';

/// Thrown after [SpeechToTextSttService] hits 3 consecutive speech timeouts.
///
/// The orchestrator catches this to speak an escalation message and suggest
/// switching to text input.
class SttTimeoutEscalation implements Exception {
  @override
  String toString() => 'SttTimeoutEscalation: 3 consecutive speech timeouts';
}

/// speech_to_text (Google on-device) implementation of [SpeechRecognitionService].
///
/// Wraps the `speech_to_text` package which uses Android's built-in speech
/// recognizer. No model files needed — the system handles everything.
///
/// Auto-restarts the listener when Android's silence timeout fires
/// (the system stops listening after ~5s of silence), making continuous
/// listening transparent to the orchestrator.
// coverage:ignore-start
class SpeechToTextSttService implements SpeechRecognitionService {
  stt.SpeechToText? _speech;
  StreamController<SpeechResult>? _resultController;
  bool _isListening = false;
  bool _isInitialized = false;
  bool _shouldContinueListening = false;
  final String _currentLocaleId = 'en_US';

  /// Tracks consecutive `error_speech_timeout` errors for escalation.
  /// Reset to 0 on any successful final result.
  int _consecutiveTimeoutCount = 0;

  @override
  Future<void> initialize({required String modelPath}) async {
    if (_isInitialized) return;

    _speech = stt.SpeechToText();
    final available = await _speech!.initialize(
      onError: _onError,
      onStatus: _onStatus,
    );

    if (!available) {
      throw StateError('Speech recognition not available on this device.');
    }

    _isInitialized = true;
  }

  @override
  Stream<SpeechResult> startListening({AudioFileService? audioFileService}) {
    if (!_isInitialized || _speech == null) {
      throw StateError(
        'SpeechToTextSttService not initialized. Call initialize() first.',
      );
    }
    if (_isListening) {
      throw StateError('Already listening. Call stopListening() first.');
    }

    _resultController = StreamController<SpeechResult>.broadcast();
    _isListening = true;
    _shouldContinueListening = true;

    _startListenSession();

    return _resultController!.stream;
  }

  /// Start a single listen session with the system recognizer.
  void _startListenSession() {
    _speech!.listen(
      onResult: _onResult,
      listenFor: const Duration(seconds: 30),
      pauseFor: const Duration(seconds: 5),
      localeId: _currentLocaleId,
      listenOptions: stt.SpeechListenOptions(
        partialResults: true,
        listenMode: stt.ListenMode.dictation,
      ),
    );
  }

  /// Map speech_to_text results to our SpeechResult type.
  void _onResult(SpeechRecognitionResult result) {
    if (_resultController == null || _resultController!.isClosed) return;

    // Reset timeout counter on any successful final result.
    if (result.finalResult) {
      _consecutiveTimeoutCount = 0;
    }

    _resultController!.add(
      SpeechResult(
        text: result.recognizedWords,
        isFinal: result.finalResult,
        confidence: result.confidence,
      ),
    );
  }

  /// Handle status changes from the speech recognizer.
  ///
  /// When Android's silence timeout stops the recognizer ("notListening"),
  /// auto-restart if we're supposed to be in continuous listening mode.
  void _onStatus(String status) {
    if (status == 'notListening' && _shouldContinueListening && _isListening) {
      // Auto-restart after silence timeout.
      Future.delayed(const Duration(milliseconds: 200), () {
        if (_shouldContinueListening && _isListening) {
          _startListenSession();
        }
      });
    }
  }

  /// Handle errors from the speech recognizer.
  void _onError(dynamic error) {
    final errorMsg = error.toString();

    // Recoverable errors — auto-restart instead of propagating:
    //   error_no_match: silence was detected, no speech recognized.
    //   error_speech_timeout: recognizer started but no audio input was
    //     captured (often caused by audio focus contention with just_audio).
    final isSpeechTimeout = errorMsg.contains('error_speech_timeout');
    final isRecoverable =
        errorMsg.contains('error_no_match') || isSpeechTimeout;

    if (isRecoverable && _shouldContinueListening && _isListening) {
      // Track consecutive speech timeouts for escalation.
      if (isSpeechTimeout) {
        _consecutiveTimeoutCount++;
        if (_consecutiveTimeoutCount >= 3) {
          _consecutiveTimeoutCount = 0;
          _resultController?.addError(SttTimeoutEscalation());
          return;
        }
      }

      // Increased delay for speech_timeout (500ms) to reduce audio focus
      // contention; shorter delay (300ms) for other recoverable errors.
      final delay = isSpeechTimeout
          ? const Duration(milliseconds: 500)
          : const Duration(milliseconds: 300);
      Future.delayed(delay, () {
        if (_shouldContinueListening && _isListening) {
          _startListenSession();
        }
      });
      return;
    }

    _resultController?.addError(StateError('STT error: $errorMsg'));
  }

  @override
  Future<void> stopListening() async {
    if (!_isListening) return;

    _shouldContinueListening = false;
    _isListening = false;
    await _speech?.stop();

    await _resultController?.close();
    _resultController = null;
  }

  @override
  bool get isListening => _isListening;

  @override
  bool get isInitialized => _isInitialized;

  @override
  void dispose() {
    if (_isListening) {
      stopListening();
    }
    _speech?.cancel();
    _speech = null;
    _isInitialized = false;
  }
}

// coverage:ignore-end
