// ===========================================================================
// file: lib/providers/llm_providers.dart
// purpose: Riverpod providers for LLM layer preferences.
//
// Manages user preferences that control which conversation layer is active:
//   - preferClaudeProvider: prefer Claude API when online
//   - journalOnlyModeProvider: bypass all layers for silent capture
//
// Both use the SharedPreferences-backed Notifier pattern established
// by VoiceModeNotifier (voice_providers.dart).
//
// See: ADR-0017 (Local LLM Layer Architecture)
// ===========================================================================

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'onboarding_providers.dart';

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
