// ===========================================================================
// file: lib/providers/llm_providers.dart
// purpose: Riverpod providers for LLM layer preferences and local LLM.
//
// Manages user preferences that control which conversation layer is active:
//   - preferClaudeProvider: prefer Claude API when online
//   - journalOnlyModeProvider: bypass all layers for silent capture
//
// Phase 8B additions — local LLM model lifecycle and layer construction:
//   - llmModelReadyProvider: whether the GGUF model file exists
//   - llmModelPathProvider: path to the GGUF model file
//   - localLlmServiceProvider: singleton LocalLlmService (null when not loaded)
//   - localLlmLayerProvider: LocalLlmLayer (null when model not loaded)
//   - llmModelDownloadServiceProvider: download service singleton
//
// Both preference providers use the SharedPreferences-backed Notifier pattern
// established by VoiceModeNotifier (voice_providers.dart).
//
// See: ADR-0017 (Local LLM Layer Architecture)
// ===========================================================================

import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';

import '../layers/local_llm_layer.dart';
import '../services/llm_model_download_service.dart';
import '../services/local_llm_service.dart';
import 'onboarding_providers.dart';
import 'personality_providers.dart';

/// SharedPreferences key for the "Prefer Claude" toggle.
const preferClaudeKey = 'prefer_claude';

/// SharedPreferences key for the "Journal Only" mode toggle.
const journalOnlyModeKey = 'journal_only_mode';

/// Controls whether Claude API is preferred when online.
///
/// When true and Claude is available: sessions start on ClaudeApiLayer.
/// When false: layer selection follows the default fallback chain
/// (local LLM if available, then Claude if available, then rule-based).
///
/// Persisted in SharedPreferences so the setting survives app restarts.
class PreferClaudeNotifier extends Notifier<bool> {
  @override
  bool build() {
    final prefs = ref.watch(sharedPreferencesProvider);
    return prefs.getBool(preferClaudeKey) ?? false;
  }

  /// Set the "Prefer Claude" preference. Persists to SharedPreferences.
  Future<void> setEnabled(bool enabled) async {
    final prefs = ref.read(sharedPreferencesProvider);
    await prefs.setBool(preferClaudeKey, enabled);
    state = enabled;
  }
}

/// Provider for the "Prefer Claude" toggle.
///
/// Watch for the bool value; call `.notifier.setEnabled(bool)` to change.
final preferClaudeProvider = NotifierProvider<PreferClaudeNotifier, bool>(
  PreferClaudeNotifier.new,
);

/// Controls journal-only mode.
///
/// When true: sessions skip greeting, skip follow-ups, and use Layer A
/// summary only. The session just captures USER messages silently.
/// This is layer-independent — it bypasses all conversation layers.
///
/// Persisted in SharedPreferences.
class JournalOnlyModeNotifier extends Notifier<bool> {
  @override
  bool build() {
    final prefs = ref.watch(sharedPreferencesProvider);
    return prefs.getBool(journalOnlyModeKey) ?? false;
  }

  /// Set journal-only mode. Persists to SharedPreferences.
  Future<void> setEnabled(bool enabled) async {
    final prefs = ref.read(sharedPreferencesProvider);
    await prefs.setBool(journalOnlyModeKey, enabled);
    state = enabled;
  }
}

/// Provider for the journal-only mode toggle.
final journalOnlyModeProvider = NotifierProvider<JournalOnlyModeNotifier, bool>(
  JournalOnlyModeNotifier.new,
);

// =========================================================================
// Local LLM model lifecycle (Phase 8B)
// =========================================================================

/// Whether the LLM GGUF model file has been downloaded and is ready.
///
/// Checks for the model file in `getApplicationSupportDirectory()/llm/`.
/// Returns false if the file is missing or the wrong size.
// coverage:ignore-start
final llmModelReadyProvider = FutureProvider<bool>((ref) async {
  final dir = await getApplicationSupportDirectory();
  final modelDir = Directory('${dir.path}/llm');

  if (!modelDir.existsSync()) return false;

  final fileName = LlmModelDownloadService.modelFileName;
  final file = File('${modelDir.path}/$fileName');
  return file.existsSync() &&
      file.lengthSync() == LlmModelDownloadService.modelFile.expectedSize;
});
// coverage:ignore-end

/// The path to the downloaded LLM model file.
///
/// Used by [localLlmServiceProvider] to locate the GGUF file for loading.
// coverage:ignore-start
final llmModelPathProvider = FutureProvider<String>((ref) async {
  final dir = await getApplicationSupportDirectory();
  final fileName = LlmModelDownloadService.modelFileName;
  return '${dir.path}/llm/$fileName';
});
// coverage:ignore-end

/// Singleton LLM model download service.
///
/// Manages download, verification, and cancellation of the GGUF file.
// coverage:ignore-start
final llmModelDownloadServiceProvider = Provider<LlmModelDownloadService>((
  ref,
) {
  final service = LlmModelDownloadService();
  ref.onDispose(() => service.dispose());
  return service;
});
// coverage:ignore-end

/// The local LLM service instance (null when no model is loaded).
///
/// This is a StateProvider so the UI can set it after model loading.
/// The real LlamadartLlmService is created and loaded in settings,
/// then injected here. Null when model is not loaded or not downloaded.
final localLlmServiceProvider = StateProvider<LocalLlmService?>((ref) => null);

/// The local LLM conversation layer (null when model not loaded).
///
/// Depends on [localLlmServiceProvider] and [personalityConfigProvider].
/// When the service is non-null and loaded, constructs a [LocalLlmLayer]
/// with the current personality's effective system prompt.
///
/// The system prompt is captured at layer construction time — mid-session
/// personality changes don't affect the active session (session-locked
/// layer policy, ADR-0017 §3).
final localLlmLayerProvider = Provider<LocalLlmLayer?>((ref) {
  final service = ref.watch(localLlmServiceProvider);
  if (service == null || !service.isModelLoaded) return null;

  final personality = ref.watch(personalityConfigProvider);
  return LocalLlmLayer(
    llmService: service,
    systemPrompt: personality.effectiveSystemPrompt,
  );
});
