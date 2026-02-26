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

import 'speech_recognition_service.dart';

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
  Stream<SpeechResult> startListening() {
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

    _resultController!.add(
      SpeechResult(text: result.recognizedWords, isFinal: result.finalResult),
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
    final isRecoverable =
        errorMsg.contains('error_no_match') ||
        errorMsg.contains('error_speech_timeout');

    if (isRecoverable && _shouldContinueListening && _isListening) {
      Future.delayed(const Duration(milliseconds: 300), () {
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
