// ===========================================================================
// file: lib/repositories/agent_repository.dart
// purpose: Conversation engine with Layer A (rule-based) and Layer B (LLM).
//
// This is the "brain" of the journaling assistant. It orchestrates between:
//   - Layer A: Rule-based keyword detection (offline, always available)
//   - Layer B: Claude API via Supabase Edge Function (online, enhanced)
//
// Design Decision: AgentRepository is INTENTIONALLY STATELESS.
//   All conversation state (follow-up count, message history, used questions)
//   is owned by SessionNotifier in the providers layer.
//   The repository receives everything it needs as method parameters.
//
// Design Decision: No ConversationAgent Interface (SPEC-20260220-064221)
//   Phase 2 stretch goal proposed extracting a ConversationAgent abstract
//   interface. Decision: NOT extracting for Phase 3. Switching logic lives
//   directly in this class, consistent with ADR-0006 Consequences.
//   Phase 5 re-evaluation: when Layer C (intent classification) is added,
//   evaluate whether layer dispatch should be extracted into a strategy class.
//
// Fallback Chain:
//   1. Check: is ClaudeApiService configured AND online?
//   2. If yes → call Claude API → return Layer B response
//   3. If Claude call fails (timeout, network, parse) → fall back to Layer A
//   4. If no → use Layer A directly (no network call attempted)
//
// See: ADR-0005 (API key proxy), ADR-0006 (Three-Layer Agent Design)
// ===========================================================================

import '../models/agent_response.dart';
import '../services/claude_api_service.dart';
import '../services/connectivity_service.dart';
import '../utils/keyword_extractor.dart';

/// Conversation engine with online/offline layer switching.
///
/// Drives conversations through: greeting → follow-ups → summary → close.
/// Methods are async to support the Claude API call path. When offline or
/// when Claude is unavailable, falls back to rule-based logic synchronously.
class AgentRepository {
  final ClaudeApiService? _claudeService;
  final ConnectivityService? _connectivityService;

  /// Creates an AgentRepository.
  ///
  /// [claudeService] — optional Claude API client. When null, Layer A only.
  /// [connectivityService] — optional connectivity checker. When null, Layer A only.
  AgentRepository({
    ClaudeApiService? claudeService,
    ConnectivityService? connectivityService,
  }) : _claudeService = claudeService,
       _connectivityService = connectivityService;

  // =========================================================================
  // Follow-up question pools (Layer A)
  // =========================================================================

  static const List<String> _emotionalFollowUps = [
    "That sounds like a lot. What do you think is driving that feeling?",
    "How long have you been feeling this way?",
    "Is there anything that helps when you feel like this?",
    "What would make things feel a little better right now?",
    "Have you noticed any patterns around when this feeling comes up?",
  ];

  static const List<String> _socialFollowUps = [
    "How did that interaction make you feel?",
    "What's your relationship with them like these days?",
    "Is there something you wish you'd said or done differently?",
    "How important is this person in your day-to-day life?",
    "What do you appreciate most about that relationship?",
  ];

  static const List<String> _workFollowUps = [
    "How do you feel about how that's going?",
    "What's the biggest challenge you're facing with that?",
    "Is there something you're looking forward to at work?",
    "How does this affect your work-life balance?",
    "What would success look like for you in this situation?",
  ];

  static const List<String> _genericFollowUps = [
    "Tell me more about that.",
    "What else is on your mind?",
    "How does that make you feel?",
    "Is there anything else you'd like to talk about?",
    "What's been the highlight of your day so far?",
  ];

  static const List<String> _doneSignals = [
    'no',
    'nope',
    "that's it",
    'nothing',
    "i'm done",
    "that's all",
    'goodbye',
    'bye',
    'no thanks',
    'not really',
    'done',
    'all good',
    "that's everything",
  ];

  // =========================================================================
  // Public API (async — supports both Layer A and Layer B)
  // =========================================================================

  /// Whether the LLM layer is available (configured + online).
  bool get _isLlmAvailable =>
      _claudeService != null &&
      _claudeService.isConfigured &&
      (_connectivityService?.isOnline ?? false);

  /// Get the opening greeting.
  ///
  /// When online: Claude generates a context-aware greeting.
  /// When offline: Rule-based time-of-day greeting (Layer A).
  ///
  /// [lastSessionDate] — when the user's most recent session started.
  /// [now] — injectable for testing. Defaults to DateTime.now().
  /// [sessionCount] — total number of past sessions (for Claude context).
  /// [conversationMessages] — not used for greeting, but included for
  ///   API consistency.
  Future<AgentResponse> getGreeting({
    DateTime? lastSessionDate,
    DateTime? now,
    int sessionCount = 0,
  }) async {
    final currentTime = now ?? DateTime.now();

    if (_isLlmAvailable) {
      try {
        // Build context for Claude's greeting
        final daysSinceLast = lastSessionDate != null
            ? currentTime.difference(lastSessionDate).inDays
            : null;
        final timeOfDay = _getTimeOfDay(currentTime);

        final response = await _claudeService!.chat(
          messages: [
            {
              'role': 'user',
              'content': 'Start a new journal session. Greet me appropriately.',
            },
          ],
          context: {
            'time_of_day': timeOfDay,
            if (daysSinceLast != null) 'days_since_last': daysSinceLast,
            'session_count': sessionCount,
          },
        );

        return AgentResponse(content: response, layer: AgentLayer.llmRemote);
      } on ClaudeApiException {
        // Fall through to Layer A
      }
    }

    // Layer A fallback
    return AgentResponse(
      content: _getLocalGreeting(
        lastSessionDate: lastSessionDate,
        now: currentTime,
      ),
      layer: AgentLayer.ruleBasedLocal,
    );
  }

  /// Get a follow-up question based on the user's message.
  ///
  /// When online: Claude generates a natural conversational follow-up.
  /// When offline: Rule-based keyword detection (Layer A).
  ///
  /// Returns null (wrapped in AgentResponse) when the conversation should end.
  ///
  /// [latestUserMessage] — the message the user just sent.
  /// [conversationHistory] — previous follow-up questions (Layer A dedup).
  /// [followUpCount] — how many follow-ups have been asked so far.
  /// [allMessages] — full conversation as role/content pairs (for Claude).
  Future<AgentResponse?> getFollowUp({
    required String latestUserMessage,
    required List<String> conversationHistory,
    required int followUpCount,
    List<Map<String, String>>? allMessages,
  }) async {
    // Check if session should end (works for both layers)
    if (shouldEndSession(
      followUpCount: followUpCount,
      latestUserMessage: latestUserMessage,
    )) {
      return null;
    }

    if (_isLlmAvailable && allMessages != null && allMessages.isNotEmpty) {
      try {
        final response = await _claudeService!.chat(messages: allMessages);
        return AgentResponse(content: response, layer: AgentLayer.llmRemote);
      } on ClaudeApiException {
        // Fall through to Layer A
      }
    }

    // Layer A fallback
    final localFollowUp = _getLocalFollowUp(
      latestUserMessage: latestUserMessage,
      conversationHistory: conversationHistory,
      followUpCount: followUpCount,
    );

    if (localFollowUp == null) return null;

    return AgentResponse(
      content: localFollowUp,
      layer: AgentLayer.ruleBasedLocal,
    );
  }

  /// Generate a session summary and extract metadata.
  ///
  /// When online: Claude generates a natural summary + structured metadata
  ///   (mood tags, people, topics).
  /// When offline: Rule-based first-sentence extraction (Layer A), no metadata.
  ///
  /// [userMessages] — only the USER messages (for Layer A summary).
  /// [allMessages] — full conversation as role/content pairs (for Claude).
  Future<AgentResponse> generateSummary({
    required List<String> userMessages,
    List<Map<String, String>>? allMessages,
  }) async {
    if (_isLlmAvailable && allMessages != null && allMessages.isNotEmpty) {
      try {
        // First get the metadata (summary, mood, people, topics)
        final metadata = await _claudeService!.extractMetadata(
          messages: allMessages,
        );

        // Use the Claude-generated summary, or fall back to local
        final summary =
            metadata.summary ?? _generateLocalSummaryText(userMessages);

        return AgentResponse(
          content: summary,
          layer: AgentLayer.llmRemote,
          metadata: metadata,
        );
      } on ClaudeApiException {
        // Fall through to Layer A
      }
    }

    // Layer A fallback — no metadata
    return AgentResponse(
      content: _generateLocalSummaryText(userMessages),
      layer: AgentLayer.ruleBasedLocal,
    );
  }

  /// Determine if the session should end based on conversation state.
  ///
  /// This is synchronous and layer-independent — the same rules apply
  /// regardless of which layer is serving the conversation.
  bool shouldEndSession({
    required int followUpCount,
    required String latestUserMessage,
  }) {
    if (followUpCount > 3) return true;
    final trimmed = latestUserMessage.trim().toLowerCase().replaceAll(
      RegExp(r'[.!?,;:]+$'),
      '',
    );
    return _doneSignals.contains(trimmed);
  }

  // =========================================================================
  // Layer A (rule-based) — private methods
  // =========================================================================

  /// Get a time-of-day string for Claude context.
  String _getTimeOfDay(DateTime time) {
    final hour = time.hour;
    if (hour >= 5 && hour < 12) return 'morning';
    if (hour >= 12 && hour < 17) return 'afternoon';
    if (hour >= 17 && hour < 22) return 'evening';
    return 'late_night';
  }

  /// Rule-based greeting (Layer A).
  String _getLocalGreeting({DateTime? lastSessionDate, DateTime? now}) {
    final currentTime = now ?? DateTime.now();

    if (lastSessionDate != null) {
      final daysSinceLastSession = currentTime
          .difference(lastSessionDate)
          .inDays;
      if (daysSinceLastSession >= 2) {
        return "It's been a few days — want to catch up?";
      }
    }

    final hour = currentTime.hour;
    if (hour >= 5 && hour < 12) {
      return "Good morning! Any plans or thoughts for today?";
    } else if (hour >= 12 && hour < 17) {
      return "How's your afternoon going?";
    } else if (hour >= 17 && hour < 22) {
      return "How was your day?";
    } else {
      return "Still up? What's on your mind?";
    }
  }

  /// Rule-based follow-up (Layer A).
  String? _getLocalFollowUp({
    required String latestUserMessage,
    required List<String> conversationHistory,
    required int followUpCount,
  }) {
    if (followUpCount > 3) return null;

    if (followUpCount == 3) {
      return "Thanks for sharing. Is there anything else you'd like to add "
          "before we wrap up?";
    }

    final category = extractCategory(latestUserMessage);
    final pool = _getPoolForCategory(category);

    for (final question in pool) {
      if (!conversationHistory.contains(question)) {
        return question;
      }
    }

    for (final question in _genericFollowUps) {
      if (!conversationHistory.contains(question)) {
        return question;
      }
    }

    return "Thanks for sharing. Is there anything else you'd like to add "
        "before we wrap up?";
  }

  /// Rule-based summary (Layer A).
  String _generateLocalSummaryText(List<String> userMessages) {
    if (userMessages.isEmpty) return '';

    final sentences = <String>[];
    for (final message in userMessages) {
      final firstSentence = _extractFirstSentence(message);
      if (firstSentence.isNotEmpty) {
        sentences.add(firstSentence);
      }
    }

    if (sentences.isEmpty) return '';
    return sentences.join('. ');
  }

  List<String> _getPoolForCategory(KeywordCategory category) {
    switch (category) {
      case KeywordCategory.emotional:
        return _emotionalFollowUps;
      case KeywordCategory.social:
        return _socialFollowUps;
      case KeywordCategory.work:
        return _workFollowUps;
      case KeywordCategory.none:
        return _genericFollowUps;
    }
  }

  String _extractFirstSentence(String message) {
    final trimmed = message.trim();
    if (trimmed.isEmpty) return '';

    final match = RegExp(r'[.!?]').firstMatch(trimmed);
    if (match != null) {
      return trimmed.substring(0, match.end).trim();
    }

    return trimmed;
  }
}
