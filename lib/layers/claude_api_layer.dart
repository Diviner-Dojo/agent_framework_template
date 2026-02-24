// ===========================================================================
// file: lib/layers/claude_api_layer.dart
// purpose: Layer B (remote) — Claude API conversation engine via Edge Function.
//
// Extracted from AgentRepository's LLM-enhanced paths. This layer uses
// the Claude API (proxied through Supabase Edge Functions) for:
//   - Context-aware greetings
//   - Natural language follow-up questions
//   - AI-generated summaries with structured metadata
//
// This layer throws ClaudeApiException on failure. The caller
// (AgentRepository) catches these and falls back to RuleBasedLayer.
//
// See: ADR-0005 (API Key Proxy), ADR-0017 (ConversationLayer)
// ===========================================================================

import '../models/agent_response.dart';
import '../services/claude_api_service.dart';
import 'conversation_layer.dart';

/// Claude API conversation layer (Layer B remote).
///
/// Requires a configured [ClaudeApiService] and network connectivity.
/// All methods throw [ClaudeApiException] on failure — the dispatcher
/// catches these and falls back to [RuleBasedLayer].
class ClaudeApiLayer implements ConversationLayer {
  final ClaudeApiService _claudeService;

  /// Creates a ClaudeApiLayer.
  ///
  /// [claudeService] — the Claude API HTTP client (must be configured).
  ClaudeApiLayer({required ClaudeApiService claudeService})
    : _claudeService = claudeService;

  @override
  Future<AgentResponse> getGreeting({
    DateTime? lastSessionDate,
    DateTime? now,
    int sessionCount = 0,
  }) async {
    final currentTime = now ?? DateTime.now();

    final daysSinceLast = lastSessionDate != null
        ? currentTime.difference(lastSessionDate).inDays
        : null;
    final timeOfDay = _getTimeOfDay(currentTime);

    final response = await _claudeService.chat(
      messages: [
        {
          'role': 'user',
          'content': 'Start a new journal session. Greet me appropriately.',
        },
      ],
      context: {
        'time_of_day': timeOfDay,
        'days_since_last': ?daysSinceLast,
        'session_count': sessionCount,
      },
    );

    return AgentResponse(content: response, layer: AgentLayer.llmRemote);
  }

  @override
  Future<AgentResponse?> getFollowUp({
    required String latestUserMessage,
    required List<String> conversationHistory,
    required int followUpCount,
    List<Map<String, String>>? allMessages,
  }) async {
    if (allMessages == null || allMessages.isEmpty) return null;

    final response = await _claudeService.chat(messages: allMessages);
    return AgentResponse(content: response, layer: AgentLayer.llmRemote);
  }

  @override
  Future<AgentResponse> generateSummary({
    required List<String> userMessages,
    List<Map<String, String>>? allMessages,
  }) async {
    if (allMessages == null || allMessages.isEmpty) {
      return AgentResponse(
        content: _generateFallbackSummary(userMessages),
        layer: AgentLayer.llmRemote,
      );
    }

    final metadata = await _claudeService.extractMetadata(
      messages: allMessages,
    );

    final summary = metadata.summary ?? _generateFallbackSummary(userMessages);

    return AgentResponse(
      content: summary,
      layer: AgentLayer.llmRemote,
      metadata: metadata,
    );
  }

  @override
  Future<AgentResponse> getResumeGreeting() async {
    // Layer B could personalize this based on session context in a future
    // phase. For now, use the same fixed greeting as Layer A.
    return const AgentResponse(
      content: "Welcome back! Let's continue where you left off.",
      layer: AgentLayer.llmRemote,
    );
  }

  // =========================================================================
  // Private helpers
  // =========================================================================

  /// Get a time-of-day string for Claude context.
  String _getTimeOfDay(DateTime time) {
    final hour = time.hour;
    if (hour >= 5 && hour < 12) return 'morning';
    if (hour >= 12 && hour < 17) return 'afternoon';
    if (hour >= 17 && hour < 22) return 'evening';
    return 'late_night';
  }

  /// Simple first-sentence summary as fallback when Claude's summary is null.
  String _generateFallbackSummary(List<String> userMessages) {
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
}
