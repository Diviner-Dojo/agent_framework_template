// ===========================================================================
// file: lib/models/personality_config.dart
// purpose: Data model for the local LLM personality configuration.
//
// Stores the assistant's name, system prompt, conversation style, and
// optional custom prompt override. Serialized as JSON in SharedPreferences
// (per ADR-0017 §7 — single user-scoped config doesn't warrant a migration).
//
// Custom prompts are sanitized before storage: control characters stripped,
// ChatML role markers removed, length limited to 500 UTF-16 code units.
//
// See: ADR-0017 (Local LLM Layer Architecture)
// ===========================================================================

import 'dart:convert';

/// Conversation style presets for the local LLM personality.
enum ConversationStyle {
  /// Warm, empathetic, supportive tone (default).
  warm,

  /// Neutral, concise, factual tone.
  professional,

  /// Inquisitive, exploratory, open-ended tone.
  curious,
}

/// Configuration for the local LLM assistant personality.
///
/// Immutable data class with JSON serialization for SharedPreferences.
/// The [customPrompt] is sanitized via [sanitizeCustomPrompt] before use.
///
/// Note: SharedPreferences stores this in cleartext. Acceptable for a
/// single-user app with device encryption. If custom prompt content is
/// classified as health data in future, migrate to `flutter_secure_storage`.
class PersonalityConfig {
  /// The assistant's display name.
  final String name;

  /// The base system prompt for the local LLM.
  final String systemPrompt;

  /// The conversation style preset.
  final ConversationStyle conversationStyle;

  /// Optional user-provided custom prompt appended to the system prompt.
  /// Sanitized via [sanitizeCustomPrompt] before injection into the LLM.
  final String? customPrompt;

  /// Creates a personality config.
  const PersonalityConfig({
    required this.name,
    required this.systemPrompt,
    required this.conversationStyle,
    this.customPrompt,
  });

  /// Default personality: "Guy" — warm companion with MI/active listening.
  factory PersonalityConfig.defaults() {
    return const PersonalityConfig(
      name: 'Guy',
      systemPrompt: _defaultSystemPrompt,
      conversationStyle: ConversationStyle.warm,
    );
  }

  /// The effective system prompt: base + custom (if present).
  ///
  /// Custom prompt is appended after the base system prompt, separated by
  /// a newline. This ensures the base therapeutic framework is always present.
  String get effectiveSystemPrompt {
    if (customPrompt == null || customPrompt!.isEmpty) {
      return systemPrompt;
    }
    return '$systemPrompt\n\n$customPrompt';
  }

  // =========================================================================
  // Serialization
  // =========================================================================

  /// Serialize to a JSON-encodable map.
  Map<String, dynamic> toJson() => {
    'name': name,
    'systemPrompt': systemPrompt,
    'conversationStyle': conversationStyle.name,
    'customPrompt': customPrompt,
  };

  /// Deserialize from a JSON map.
  ///
  /// Defensive: unknown keys are ignored, missing fields use defaults.
  factory PersonalityConfig.fromJson(Map<String, dynamic> json) {
    final defaults = PersonalityConfig.defaults();
    return PersonalityConfig(
      name: json['name'] is String ? json['name'] as String : defaults.name,
      systemPrompt: json['systemPrompt'] is String
          ? json['systemPrompt'] as String
          : defaults.systemPrompt,
      conversationStyle: _parseConversationStyle(
        json['conversationStyle'],
        defaults.conversationStyle,
      ),
      customPrompt: json['customPrompt'] is String
          ? json['customPrompt'] as String
          : null,
    );
  }

  /// Parse a JSON string into a PersonalityConfig.
  ///
  /// Returns [PersonalityConfig.defaults()] on any parse error (corrupted
  /// JSON, wrong types, etc.). Never throws.
  static PersonalityConfig fromJsonString(String jsonString) {
    try {
      final decoded = json.decode(jsonString);
      if (decoded is! Map<String, dynamic>) {
        return PersonalityConfig.defaults();
      }
      return PersonalityConfig.fromJson(decoded);
    } on FormatException {
      return PersonalityConfig.defaults();
    }
  }

  /// Serialize to a JSON string for SharedPreferences storage.
  String toJsonString() => json.encode(toJson());

  // =========================================================================
  // Custom prompt sanitization
  // =========================================================================

  /// Sanitize a user-provided custom prompt.
  ///
  /// Rules:
  /// 1. Trim leading/trailing whitespace
  /// 2. Strip control characters (U+0000–U+001F) except newlines (U+000A)
  /// 3. Strip ChatML role markers that could confuse the chat template
  /// 4. Enforce 500 UTF-16 code unit limit (truncate, don't reject)
  ///
  /// Returns empty string if the result is only whitespace after sanitization.
  static String sanitizeCustomPrompt(String input) {
    // Step 1: trim
    var result = input.trim();

    // Step 2: strip control characters except newlines
    result = result.replaceAll(RegExp(r'[\x00-\x09\x0B-\x1F]'), '');

    // Step 3: strip ChatML role markers
    result = result.replaceAll(RegExp(r'<\|im_start\|>'), '');
    result = result.replaceAll(RegExp(r'<\|im_end\|>'), '');
    result = result.replaceAll(RegExp(r'^Human:\s*', multiLine: true), '');
    result = result.replaceAll(RegExp(r'^Assistant:\s*', multiLine: true), '');
    result = result.replaceAll(RegExp(r'^### System\s*', multiLine: true), '');

    // Step 4: trim again after stripping (markers may leave whitespace)
    result = result.trim();

    // Step 5: enforce 500 UTF-16 code unit limit
    if (result.length > 500) {
      result = result.substring(0, 500);
    }

    return result;
  }

  // =========================================================================
  // Equality
  // =========================================================================

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is PersonalityConfig &&
          runtimeType == other.runtimeType &&
          name == other.name &&
          systemPrompt == other.systemPrompt &&
          conversationStyle == other.conversationStyle &&
          customPrompt == other.customPrompt;

  @override
  int get hashCode =>
      Object.hash(name, systemPrompt, conversationStyle, customPrompt);

  /// Create a copy with optional field overrides.
  PersonalityConfig copyWith({
    String? name,
    String? systemPrompt,
    ConversationStyle? conversationStyle,
    String? customPrompt,
    bool clearCustomPrompt = false,
  }) {
    return PersonalityConfig(
      name: name ?? this.name,
      systemPrompt: systemPrompt ?? this.systemPrompt,
      conversationStyle: conversationStyle ?? this.conversationStyle,
      customPrompt: clearCustomPrompt
          ? null
          : (customPrompt ?? this.customPrompt),
    );
  }

  // =========================================================================
  // Private helpers
  // =========================================================================

  /// Parse a ConversationStyle from a JSON value, with fallback.
  static ConversationStyle _parseConversationStyle(
    dynamic value,
    ConversationStyle fallback,
  ) {
    if (value is! String) return fallback;
    for (final style in ConversationStyle.values) {
      if (style.name == value) return style;
    }
    return fallback;
  }

  // =========================================================================
  // Default system prompt
  // =========================================================================

  /// Default "Guy" personality system prompt.
  ///
  /// Informed by motivational interviewing (MI) and active listening
  /// principles. Warm, non-judgmental, reflective.
  static const _defaultSystemPrompt =
      '''You are Guy, a warm and thoughtful journaling companion. Your role is to help the user reflect on their day, thoughts, and feelings through gentle conversation.

Guidelines:
- Be warm, empathetic, and non-judgmental in all responses
- Use active listening: reflect back what you hear before asking questions
- Ask open-ended questions that encourage deeper reflection
- Keep responses concise (2-3 sentences max) — this is a conversation, not a lecture
- Never diagnose, prescribe, or give medical/psychological advice
- If the user shares something difficult, acknowledge their feelings before moving on
- Match the user's energy: if they're brief, be brief; if they're detailed, engage more
- Use the user's own words when reflecting back to show you're listening
- End conversations gracefully — don't push for more when the user is done''';
}
