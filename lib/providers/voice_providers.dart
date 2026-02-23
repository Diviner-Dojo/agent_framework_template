// ===========================================================================
// file: lib/providers/voice_providers.dart
// purpose: Riverpod providers for voice mode services and state.
//
// Voice mode is an optional feature — when disabled, all voice-related
// providers still exist but are unused. The voiceModeEnabledProvider
// controls whether the mic button appears in the session screen.
//
// Service lifecycle:
//   STT and TTS services are created lazily and disposed when the provider
//   container is disposed. Initialization is separate from creation —
//   the UI must call initialize() before use (triggered by first voice
//   activation, after model download is confirmed).
//
// See: ADR-0015 (Voice Mode Architecture)
// ===========================================================================

import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';

import '../services/speech_recognition_service.dart';
import '../services/text_to_speech_service.dart';

/// Controls whether voice mode is enabled for sessions.
///
/// When true, the journal session screen shows a mic button and TTS
/// speaks assistant responses aloud. Persisted in SharedPreferences
/// (Phase 7A uses simple state; persistence can be added later).
final voiceModeEnabledProvider = StateProvider<bool>((ref) => false);

// coverage:ignore-start
/// Provides the STT service singleton.
///
/// The service is created immediately but not initialized. Call
/// `initialize(modelPath: ...)` before first use. Disposed when
/// the provider container is disposed.
final speechRecognitionServiceProvider = Provider<SpeechRecognitionService>((
  ref,
) {
  final service = SherpaOnnxSpeechRecognitionService();
  ref.onDispose(() => service.dispose());
  return service;
});

/// Provides the TTS service singleton.
///
/// Call `initialize()` before first use. Disposed when the provider
/// container is disposed.
final textToSpeechServiceProvider = Provider<TextToSpeechService>((ref) {
  final service = FlutterTextToSpeechService();
  ref.onDispose(() => service.dispose());
  return service;
});

/// Whether the STT model has been downloaded and is ready.
///
/// Checks for the existence of all four Zipformer model files in the
/// app support directory. Returns false if any file is missing.
final sttModelReadyProvider = FutureProvider<bool>((ref) async {
  final dir = await getApplicationSupportDirectory();
  final modelDir = Directory('${dir.path}/zipformer');

  if (!modelDir.existsSync()) return false;

  // All four model files must be present.
  final requiredFiles = [
    'encoder-epoch-99-avg-1-chunk-16-left-128.int8.onnx',
    'decoder-epoch-99-avg-1-chunk-16-left-128.onnx',
    'joiner-epoch-99-avg-1-chunk-16-left-128.int8.onnx',
    'tokens.txt',
  ];

  for (final fileName in requiredFiles) {
    final file = File('${modelDir.path}/$fileName');
    if (!file.existsSync()) return false;
  }

  return true;
});

/// The path to the STT model directory.
///
/// Used by the speech recognition service to locate model files.
final sttModelPathProvider = FutureProvider<String>((ref) async {
  final dir = await getApplicationSupportDirectory();
  return '${dir.path}/zipformer';
});
// coverage:ignore-end
