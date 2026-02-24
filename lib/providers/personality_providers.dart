// ===========================================================================
// file: lib/providers/personality_providers.dart
// purpose: Riverpod providers for the local LLM personality system.
//
// Manages the PersonalityConfig: default "Guy" personality, conversation
// style, and optional custom prompt. Persisted as JSON in SharedPreferences
// (per ADR-0017 §7 — single user-scoped config).
//
// Corrupted JSON on read falls back to PersonalityConfig.defaults() —
// never throws. Custom prompts are sanitized before storage.
//
// See: ADR-0017 (Local LLM Layer Architecture)
// ===========================================================================

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/personality_config.dart';
import 'onboarding_providers.dart';

/// SharedPreferences key for the personality config JSON.
const personalityConfigKey = 'personality_config';

/// Manages the local LLM personality configuration.
///
/// Reads from and writes to SharedPreferences as a JSON string.
/// Falls back to [PersonalityConfig.defaults()] on any read error.
/// Custom prompts are sanitized via [PersonalityConfig.sanitizeCustomPrompt]
/// before storage.
class PersonalityNotifier extends Notifier<PersonalityConfig> {
  @override
  PersonalityConfig build() {
    final prefs = ref.watch(sharedPreferencesProvider);
    final jsonString = prefs.getString(personalityConfigKey);
    if (jsonString == null) {
      return PersonalityConfig.defaults();
    }
    return PersonalityConfig.fromJsonString(jsonString);
  }

  /// Update the personality config. Persists to SharedPreferences.
  ///
  /// If [config] has a non-null [PersonalityConfig.customPrompt], it is
  /// sanitized before storage.
  Future<void> setConfig(PersonalityConfig config) async {
    final sanitized = config.customPrompt != null
        ? config.copyWith(
            customPrompt: PersonalityConfig.sanitizeCustomPrompt(
              config.customPrompt!,
            ),
          )
        : config;

    final prefs = ref.read(sharedPreferencesProvider);
    await prefs.setString(personalityConfigKey, sanitized.toJsonString());
    state = sanitized;
  }

  /// Update only the assistant name. Persists.
  Future<void> setName(String name) async {
    await setConfig(state.copyWith(name: name));
  }

  /// Update only the conversation style. Persists.
  Future<void> setConversationStyle(ConversationStyle style) async {
    await setConfig(state.copyWith(conversationStyle: style));
  }

  /// Update only the custom prompt. Sanitized and persisted.
  Future<void> setCustomPrompt(String? prompt) async {
    if (prompt == null || prompt.trim().isEmpty) {
      await setConfig(state.copyWith(clearCustomPrompt: true));
    } else {
      await setConfig(state.copyWith(customPrompt: prompt));
    }
  }
}

/// Provider for the personality config.
///
/// Watch for the current [PersonalityConfig]; use `.notifier` to modify.
final personalityConfigProvider =
    NotifierProvider<PersonalityNotifier, PersonalityConfig>(
      PersonalityNotifier.new,
    );
