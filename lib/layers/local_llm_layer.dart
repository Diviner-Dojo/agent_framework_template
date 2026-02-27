// ===========================================================================
// file: lib/layers/local_llm_layer.dart
// purpose: Layer B (local) — on-device LLM conversation engine.
//
// Uses the local LLM (via LocalLlmService) for contextual greetings,
// empathetic follow-ups, and AI-generated summaries. The personality
// system prompt is captured at construction time and immutable for the
// layer instance's lifetime — mid-session personality changes don't
// affect the active session (session-locked layer policy, ADR-0017 §3).
//
// Throws LocalLlmException on any failure — AgentRepository catches
// via the existing `on Exception` handler and falls back to RuleBasedLayer.
//
// See: ADR-0017 (Local LLM Layer Architecture)
// ===========================================================================

import '../models/agent_response.dart';
import '../models/journaling_mode.dart';
import '../services/local_llm_service.dart';
import 'conversation_layer.dart' show ConversationLayer, getTimeOfDay;

/// On-device LLM conversation layer (Layer B local).
///
/// Requires a loaded [LocalLlmService] and a personality system prompt.
/// The system prompt is captured at construction time — immutable for the
/// layer instance's lifetime, ensuring mid-session personality changes
/// don't affect the active session.
class LocalLlmLayer implements ConversationLayer {
  final LocalLlmService _llmService;

  /// The personality system prompt, captured at construction.
  final String _systemPrompt;

  /// Creates a local LLM layer.
  ///
  /// [llmService] — the local LLM inference service (must have model loaded).
  /// [systemPrompt] — the personality system prompt (from PersonalityConfig).
  LocalLlmLayer({
    required LocalLlmService llmService,
    required String systemPrompt,
  }) : _llmService = llmService,
       _systemPrompt = systemPrompt;

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
    final timeOfDay = getTimeOfDay(currentTime);
    final daysSinceLast = lastSessionDate != null
        ? currentTime.difference(lastSessionDate).inDays
        : null;

    var contextHint = 'Time of day: $timeOfDay.';
    if (daysSinceLast != null && daysSinceLast >= 2) {
      contextHint +=
          " It's been $daysSinceLast days since the user's last session.";
    }
    if (sessionCount == 0) {
      contextHint += ' This is the user\'s first session ever.';
    }

    // Compose mode-specific prompt with personality prompt (ADR-0025).
    final effectivePrompt = _composePromptWithMode(
      _systemPrompt,
      journalingMode,
    );

    final response = await _llmService.generate(
      messages: [
        {
          'role': 'user',
          'content':
              'Start a new journal session. Greet me appropriately. $contextHint',
        },
      ],
      systemPrompt: effectivePrompt,
    );

    return AgentResponse(content: response, layer: AgentLayer.llmLocal);
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

    // Compose mode-specific prompt with personality prompt (ADR-0025).
    final effectivePrompt = _composePromptWithMode(
      _systemPrompt,
      journalingMode,
    );

    final response = await _llmService.generate(
      messages: allMessages,
      systemPrompt: effectivePrompt,
    );

    return AgentResponse(content: response, layer: AgentLayer.llmLocal);
  }

  @override
  Future<AgentResponse> generateSummary({
    required List<String> userMessages,
    List<Map<String, String>>? allMessages,
  }) async {
    if (allMessages == null || allMessages.isEmpty) {
      // Fall back to simple concatenation if no conversation history.
      return AgentResponse(
        content: userMessages.join('. '),
        layer: AgentLayer.llmLocal,
      );
    }

    final summaryMessages = List<Map<String, String>>.from(allMessages);
    summaryMessages.add({
      'role': 'user',
      'content':
          'Please provide a brief summary of this conversation in 1-3 sentences. '
          'Focus on the key themes, emotions, and events discussed.',
    });

    final response = await _llmService.generate(
      messages: summaryMessages,
      systemPrompt: _systemPrompt,
    );

    return AgentResponse(content: response, layer: AgentLayer.llmLocal);
  }

  @override
  Future<AgentResponse> getResumeGreeting() async {
    final response = await _llmService.generate(
      messages: [
        {
          'role': 'user',
          'content':
              'I\'m resuming a previous journal session. '
              'Welcome me back briefly.',
        },
      ],
      systemPrompt: _systemPrompt,
    );

    return AgentResponse(content: response, layer: AgentLayer.llmLocal);
  }

  // =========================================================================
  // Private helpers
  // =========================================================================

  /// Compose the personality prompt with a mode-specific prompt fragment.
  ///
  /// Returns the base prompt unmodified for free mode or null mode.
  /// For other modes, appends the mode's system prompt fragment.
  static String _composePromptWithMode(String basePrompt, String? modeStr) {
    final mode = JournalingMode.fromDbString(modeStr);
    if (mode == null || mode == JournalingMode.free) return basePrompt;
    return basePrompt + mode.systemPromptFragment;
  }
}
