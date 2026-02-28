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
import 'conversation_layer.dart'
    show ConversationLayer, getTimeOfDay, generateFirstSentenceSummary;

/// Claude API conversation layer (Layer B remote).
///
/// Requires a configured [ClaudeApiService] and network connectivity.
/// All methods throw [ClaudeApiException] on failure — the dispatcher
/// catches these and falls back to [RuleBasedLayer].
class ClaudeApiLayer implements ConversationLayer {
  final ClaudeApiService _claudeService;

  /// Custom instructions from the user's personality config.
  ///
  /// Sent to the Edge Function via the context map so the server-side
  /// system prompt includes user-specified behavior (e.g. "respond with
  /// one sentence"). Mutable so personality changes can be applied
  /// without rebuilding the provider chain (mirrors LocalLlmLayer pattern).
  String? _customInstructions;

  /// Creates a ClaudeApiLayer.
  ///
  /// [claudeService] — the Claude API HTTP client (must be configured).
  /// [customInstructions] — optional user custom prompt from personality config.
  ClaudeApiLayer({
    required ClaudeApiService claudeService,
    String? customInstructions,
  }) : _claudeService = claudeService,
       _customInstructions = customInstructions;

  /// Update custom instructions without rebuilding the layer.
  ///
  /// Called by AgentRepository when personality config changes. The
  /// session-locked layer object is preserved, so this updates the
  /// instructions for the current and future requests.
  void updateCustomInstructions(String? instructions) {
    _customInstructions = instructions;
  }

  @override
  Future<AgentResponse> getGreeting({
    DateTime? lastSessionDate,
    DateTime? now,
    int sessionCount = 0,
    List<Map<String, String>>? sessionSummaries,
    String? journalingMode,
    bool? isVoiceMode,
  }) async {
    final currentTime = now ?? DateTime.now();

    final daysSinceLast = lastSessionDate != null
        ? currentTime.difference(lastSessionDate).inDays
        : null;
    final timeOfDay = getTimeOfDay(currentTime);

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
        if (sessionSummaries != null && sessionSummaries.isNotEmpty)
          'session_summaries': sessionSummaries,
        'journaling_mode': journalingMode,
        if (isVoiceMode == true) 'voice_mode': true,
        if (_customInstructions != null && _customInstructions!.isNotEmpty)
          'custom_instructions': _customInstructions,
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
    List<Map<String, String>>? sessionSummaries,
    String? journalingMode,
    bool? isVoiceMode,
  }) async {
    if (allMessages == null || allMessages.isEmpty) return null;

    final response = await _claudeService.chat(
      messages: allMessages,
      context: {
        if (sessionSummaries != null && sessionSummaries.isNotEmpty)
          'session_summaries': sessionSummaries,
        'journaling_mode': journalingMode,
        if (isVoiceMode == true) 'voice_mode': true,
        if (_customInstructions != null && _customInstructions!.isNotEmpty)
          'custom_instructions': _customInstructions,
      },
    );
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

  /// Simple first-sentence summary as fallback when Claude's summary is null.
  String _generateFallbackSummary(List<String> userMessages) {
    return generateFirstSentenceSummary(userMessages);
  }
}
