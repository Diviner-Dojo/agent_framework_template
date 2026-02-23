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
// Phase 7B additions:
//   - audioFocusServiceProvider: singleton for Android audio focus
//   - voiceModeEnabledProvider: now persisted via SharedPreferences
//   - autoSaveOnExitProvider: persisted toggle for auto-save on backgrounding
//   - voiceOrchestratorProvider: continuous voice loop state machine
//
// See: ADR-0015 (Voice Mode Architecture)
// ===========================================================================

import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';

import '../services/audio_focus_service.dart';
import '../services/speech_recognition_service.dart';
import '../services/text_to_speech_service.dart';
import '../services/voice_session_orchestrator.dart';
import 'onboarding_providers.dart';

/// SharedPreferences key for the voice mode toggle.
const voiceModeEnabledKey = 'voice_mode_enabled';

/// SharedPreferences key for the auto-save on exit toggle.
const autoSaveOnExitKey = 'auto_save_on_exit';

/// Controls whether voice mode is enabled for sessions.
///
/// When true, the journal session screen shows a mic button and TTS
/// speaks assistant responses aloud. Persisted in SharedPreferences
/// so the setting survives app restarts.
///
/// Uses the same Notifier pattern as [OnboardingNotifier].
class VoiceModeNotifier extends Notifier<bool> {
  @override
  bool build() {
    final prefs = ref.watch(sharedPreferencesProvider);
    return prefs.getBool(voiceModeEnabledKey) ?? false;
  }

  /// Toggle voice mode on or off. Persists to SharedPreferences.
  Future<void> setEnabled(bool enabled) async {
    final prefs = ref.read(sharedPreferencesProvider);
    await prefs.setBool(voiceModeEnabledKey, enabled);
    state = enabled;
  }
}

/// Provider for the voice mode enabled notifier.
///
/// Watch for the bool value; call `.notifier.setEnabled(bool)` to change.
final voiceModeEnabledProvider = NotifierProvider<VoiceModeNotifier, bool>(
  VoiceModeNotifier.new,
);

/// Controls whether the session auto-saves when the app is backgrounded.
///
/// Defaults to true. Persisted in SharedPreferences.
class AutoSaveOnExitNotifier extends Notifier<bool> {
  @override
  bool build() {
    final prefs = ref.watch(sharedPreferencesProvider);
    return prefs.getBool(autoSaveOnExitKey) ?? true;
  }

  /// Set auto-save behavior. Persists to SharedPreferences.
  Future<void> setEnabled(bool enabled) async {
    final prefs = ref.read(sharedPreferencesProvider);
    await prefs.setBool(autoSaveOnExitKey, enabled);
    state = enabled;
  }
}

/// Provider for the auto-save on exit notifier.
final autoSaveOnExitProvider = NotifierProvider<AutoSaveOnExitNotifier, bool>(
  AutoSaveOnExitNotifier.new,
);

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

/// Provides the audio focus service singleton.
///
/// Manages Android audio focus for STT/TTS coordination with other
/// apps (music, phone calls, navigation). Disposed on provider cleanup.
final audioFocusServiceProvider = Provider<AudioFocusService>((ref) {
  final service = AndroidAudioFocusService();
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

/// Provides the voice session orchestrator.
///
/// The orchestrator manages the continuous listen→process→speak→listen
/// loop. It coordinates STT, TTS, and audio focus services.
/// Disposed when the provider container is disposed.
final voiceOrchestratorProvider = Provider<VoiceSessionOrchestrator>((ref) {
  final stt = ref.watch(speechRecognitionServiceProvider);
  final tts = ref.watch(textToSpeechServiceProvider);
  final audioFocus = ref.watch(audioFocusServiceProvider);

  final orchestrator = VoiceSessionOrchestrator(
    sttService: stt,
    ttsService: tts,
    audioFocusService: audioFocus,
  );

  ref.onDispose(() => orchestrator.dispose());
  return orchestrator;
});
// coverage:ignore-end
