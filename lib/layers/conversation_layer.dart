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
  Future<AgentResponse> getGreeting({
    DateTime? lastSessionDate,
    DateTime? now,
    int sessionCount = 0,
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
  Future<AgentResponse?> getFollowUp({
    required String latestUserMessage,
    required List<String> conversationHistory,
    required int followUpCount,
    List<Map<String, String>>? allMessages,
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
