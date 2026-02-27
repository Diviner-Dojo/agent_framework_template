// ===========================================================================
// file: lib/layers/conversation_layer.dart
// purpose: Abstract strategy interface for conversation generation layers.
//
// Each conversation layer implements the four core conversation operations:
//   - getGreeting(): open a new session with an appropriate greeting
//   - getFollowUp(): respond to a user message with a follow-up question
//   - generateSummary(): produce a session summary (and optional metadata)
//   - getResumeGreeting(): greet the user when resuming an existing session
//
// Implementations:
//   - RuleBasedLayer: keyword-based, offline, always available (Layer A)
//   - ClaudeApiLayer: Claude API via Edge Function proxy (Layer B remote)
//   - LocalLlmLayer: on-device LLM inference (Layer B local, Phase 8B)
//
// Design Decision: shouldEndSession() is NOT part of this interface.
//   End-session detection is synchronous, layer-independent, and uses
//   the same rules regardless of which layer serves the conversation.
//   It stays on AgentRepository. (ADR-0017)
//
// See: ADR-0017 (Local LLM Layer Architecture)
// ===========================================================================

import '../models/agent_response.dart';

/// Strategy interface for conversation generation.
///
/// Each implementation encapsulates one conversation engine (rule-based,
/// Claude API, local LLM). AgentRepository selects and delegates to the
/// active layer based on availability and user preference.
abstract class ConversationLayer {
  /// Get the opening greeting for a new session.
  ///
  /// [lastSessionDate] — when the user's most recent session started.
  /// [now] — injectable for testing. Defaults to DateTime.now().
  /// [sessionCount] — total number of past sessions (for context).
  /// [sessionSummaries] — recent session summaries for continuity (ADR-0023).
  /// [journalingMode] — optional mode string for guided sessions (ADR-0025).
  /// [isVoiceMode] — when true, responses should be maximally brief.
  Future<AgentResponse> getGreeting({
    DateTime? lastSessionDate,
    DateTime? now,
    int sessionCount = 0,
    List<Map<String, String>>? sessionSummaries,
    String? journalingMode,
    bool? isVoiceMode,
  });

  /// Get a follow-up question based on the user's message.
  ///
  /// Returns null when the conversation should end (max follow-ups reached
  /// or the layer determines the conversation is complete).
  ///
  /// [latestUserMessage] — the message the user just sent.
  /// [conversationHistory] — previous follow-up questions (for dedup).
  /// [followUpCount] — how many follow-ups have been asked so far.
  /// [allMessages] — full conversation as role/content pairs.
  /// [sessionSummaries] — recent session summaries for continuity (ADR-0023).
  /// [journalingMode] — optional mode string for guided sessions (ADR-0025).
  /// [isVoiceMode] — when true, responses should be maximally brief.
  Future<AgentResponse?> getFollowUp({
    required String latestUserMessage,
    required List<String> conversationHistory,
    required int followUpCount,
    List<Map<String, String>>? allMessages,
    List<Map<String, String>>? sessionSummaries,
    String? journalingMode,
    bool? isVoiceMode,
  });

  /// Generate a session summary and optionally extract metadata.
  ///
  /// [userMessages] — only the USER messages (for simple summary).
  /// [allMessages] — full conversation as role/content pairs.
  Future<AgentResponse> generateSummary({
    required List<String> userMessages,
    List<Map<String, String>>? allMessages,
  });

  /// Get a greeting for a resumed session.
  Future<AgentResponse> getResumeGreeting();
}

/// Shared time-of-day string for LLM context prompts.
///
/// Used by [ClaudeApiLayer] and [LocalLlmLayer] to provide temporal
/// context in greetings. Extracted here to avoid duplication.
String getTimeOfDay(DateTime time) {
  final hour = time.hour;
  if (hour >= 5 && hour < 12) return 'morning';
  if (hour >= 12 && hour < 17) return 'afternoon';
  if (hour >= 17 && hour < 22) return 'evening';
  return 'late night';
}

/// Generate a summary by extracting the first sentence of each user message.
///
/// Shared by [RuleBasedLayer] and [ClaudeApiLayer] (as fallback) to avoid
/// duplicating the first-sentence extraction logic.
String generateFirstSentenceSummary(List<String> userMessages) {
  if (userMessages.isEmpty) return '';

  final sentences = <String>[];
  for (final message in userMessages) {
    final trimmed = message.trim();
    if (trimmed.isEmpty) continue;
    final match = RegExp(r'[.!?]').firstMatch(trimmed);
    if (match != null) {
      sentences.add(trimmed.substring(0, match.end).trim());
    } else {
      sentences.add(trimmed);
    }
  }

  if (sentences.isEmpty) return '';
  return sentences.join('. ');
}
