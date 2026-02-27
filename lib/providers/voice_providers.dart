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
// ADR-0022 additions:
//   - TtsEngine/SttEngine enums for engine selection
//   - Engine preference notifiers persisted in SharedPreferences
//   - Service providers select implementation based on engine preference
//   - sttModelReadyProvider returns true for speechToText engine
//
// See: ADR-0015 (Voice Mode Architecture), ADR-0022 (Voice Engine Swap)
// ===========================================================================

import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';

import '../config/environment.dart';
import '../services/audio_focus_service.dart';
import '../services/elevenlabs_tts_service.dart';
import '../services/speech_recognition_service.dart';
import '../services/speech_to_text_stt_service.dart';
import '../services/text_to_speech_service.dart';
import '../services/voice_session_orchestrator.dart';
import 'onboarding_providers.dart';

/// SharedPreferences key for the voice mode toggle.
const voiceModeEnabledKey = 'voice_mode_enabled';

/// SharedPreferences key for the auto-save on exit toggle.
const autoSaveOnExitKey = 'auto_save_on_exit';

/// SharedPreferences key for TTS playback speed.
const ttsRateKey = 'tts_rate';

/// SharedPreferences key for TTS engine preference.
const ttsEngineKey = 'tts_engine';

/// SharedPreferences key for STT engine preference.
const sttEngineKey = 'stt_engine';

// ---------------------------------------------------------------------------
// Engine enums
// ---------------------------------------------------------------------------

/// Available text-to-speech engines.
enum TtsEngine {
  /// ElevenLabs natural voices via Supabase proxy (requires network).
  elevenlabs,

  /// Flutter TTS using Android system engine (offline, robotic).
  flutterTts,
}

/// Available speech-to-text engines.
enum SttEngine {
  /// Google on-device recognizer via speech_to_text (no model download).
  speechToText,

  /// sherpa_onnx Zipformer (offline, requires 71MB model download).
  sherpaOnnx,
}

// ---------------------------------------------------------------------------
// Voice mode toggles
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Engine preference notifiers
// ---------------------------------------------------------------------------

/// Controls which TTS engine is used. Persisted in SharedPreferences.
///
/// Defaults to [TtsEngine.elevenlabs] for natural voices.
class TtsEngineNotifier extends Notifier<TtsEngine> {
  @override
  TtsEngine build() {
    final prefs = ref.watch(sharedPreferencesProvider);
    final stored = prefs.getString(ttsEngineKey);
    if (stored == 'flutterTts') return TtsEngine.flutterTts;
    return TtsEngine.elevenlabs;
  }

  /// Set the TTS engine. Persists to SharedPreferences.
  Future<void> setEngine(TtsEngine engine) async {
    final prefs = ref.read(sharedPreferencesProvider);
    await prefs.setString(ttsEngineKey, engine.name);
    state = engine;
  }
}

/// Provider for the TTS engine preference.
final ttsEngineProvider = NotifierProvider<TtsEngineNotifier, TtsEngine>(
  TtsEngineNotifier.new,
);

/// Controls the TTS playback speed. Persisted in SharedPreferences.
///
/// Range: 0.5–1.5. Default: 0.85 (natural conversational speed).
class TtsRateNotifier extends Notifier<double> {
  @override
  double build() {
    final prefs = ref.watch(sharedPreferencesProvider);
    return prefs.getDouble(ttsRateKey) ?? 0.85;
  }

  /// Set the TTS rate. Persists to SharedPreferences.
  Future<void> setRate(double rate) async {
    final prefs = ref.read(sharedPreferencesProvider);
    await prefs.setDouble(ttsRateKey, rate);
    state = rate;
  }
}

/// Provider for the TTS playback speed.
final ttsRateProvider = NotifierProvider<TtsRateNotifier, double>(
  TtsRateNotifier.new,
);

/// Controls which STT engine is used. Persisted in SharedPreferences.
///
/// Defaults to [SttEngine.speechToText] for zero-download experience.
class SttEngineNotifier extends Notifier<SttEngine> {
  @override
  SttEngine build() {
    final prefs = ref.watch(sharedPreferencesProvider);
    final stored = prefs.getString(sttEngineKey);
    if (stored == 'sherpaOnnx') return SttEngine.sherpaOnnx;
    return SttEngine.speechToText;
  }

  /// Set the STT engine. Persists to SharedPreferences.
  Future<void> setEngine(SttEngine engine) async {
    final prefs = ref.read(sharedPreferencesProvider);
    await prefs.setString(sttEngineKey, engine.name);
    state = engine;
  }
}

/// Provider for the STT engine preference.
final sttEngineProvider = NotifierProvider<SttEngineNotifier, SttEngine>(
  SttEngineNotifier.new,
);

// ---------------------------------------------------------------------------
// Service providers
// ---------------------------------------------------------------------------

// coverage:ignore-start
/// Provides the STT service singleton based on the current engine preference.
///
/// When [SttEngine.speechToText] is selected, returns the Google on-device
/// recognizer. When [SttEngine.sherpaOnnx], returns the offline Zipformer.
/// The service is created but not initialized — call `initialize()` first.
final speechRecognitionServiceProvider = Provider<SpeechRecognitionService>((
  ref,
) {
  final engine = ref.watch(sttEngineProvider);
  final SpeechRecognitionService service;

  switch (engine) {
    case SttEngine.speechToText:
      service = SpeechToTextSttService();
    case SttEngine.sherpaOnnx:
      service = SherpaOnnxSpeechRecognitionService();
  }

  ref.onDispose(() => service.dispose());
  return service;
});

/// Provides the TTS service singleton based on the current engine preference.
///
/// When [TtsEngine.elevenlabs] is selected, returns the ElevenLabs proxy
/// service. When [TtsEngine.flutterTts], returns the Android system TTS.
/// Also watches [ttsRateProvider] and applies rate changes immediately
/// for the flutter_tts engine.
/// Call `initialize()` before first use.
final textToSpeechServiceProvider = Provider<TextToSpeechService>((ref) {
  final engine = ref.watch(ttsEngineProvider);
  final ttsRate = ref.watch(ttsRateProvider);
  final TextToSpeechService service;

  switch (engine) {
    case TtsEngine.elevenlabs:
      const env = Environment();
      service = ElevenLabsTtsService(
        proxyUrl: env.elevenlabsProxyUrl,
        authToken: env.supabaseAnonKey,
      );
    case TtsEngine.flutterTts:
      service = FlutterTextToSpeechService();
  }

  // Apply the current TTS rate. For FlutterTts this sets the Android
  // speech rate; for ElevenLabs it's a no-op (server-controlled).
  service.setSpeechRate(ttsRate);

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
/// When using [SttEngine.speechToText], always returns true (no model
/// download needed). When using [SttEngine.sherpaOnnx], checks for the
/// existence of all four Zipformer model files.
final sttModelReadyProvider = FutureProvider<bool>((ref) async {
  final engine = ref.watch(sttEngineProvider);

  // speech_to_text uses the system recognizer — always ready.
  if (engine == SttEngine.speechToText) return true;

  // sherpa_onnx requires downloaded model files.
  final dir = await getApplicationSupportDirectory();
  final modelDir = Directory('${dir.path}/zipformer');

  if (!modelDir.existsSync()) return false;

  // All four model files must be present.
  final requiredFiles = [
    'encoder-epoch-99-avg-1.int8.onnx',
    'decoder-epoch-99-avg-1.onnx',
    'joiner-epoch-99-avg-1.int8.onnx',
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
