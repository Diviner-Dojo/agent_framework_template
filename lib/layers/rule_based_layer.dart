// ===========================================================================
// file: lib/layers/rule_based_layer.dart
// purpose: Layer A — rule-based conversation engine (offline, always available).
//
// Extracted from AgentRepository's private methods. This layer uses:
//   - Time-of-day greetings with gap detection
//   - Keyword-based follow-up question pools (emotional, social, work)
//   - First-sentence extraction for session summaries
//
// This layer requires no external services and cannot fail — it is the
// ultimate fallback for all other layers.
//
// See: ADR-0006 (Three-Layer Agent Design), ADR-0017 (ConversationLayer)
// ===========================================================================

import '../models/agent_response.dart';
import '../utils/keyword_extractor.dart';
import 'conversation_layer.dart';

/// Rule-based conversation layer (Layer A).
///
/// Offline-only, deterministic, always available. Uses keyword detection
/// for follow-ups and first-sentence extraction for summaries.
class RuleBasedLayer implements ConversationLayer {
  // =========================================================================
  // Follow-up question pools
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

  // =========================================================================
  // ConversationLayer implementation
  // =========================================================================

  @override
  Future<AgentResponse> getGreeting({
    DateTime? lastSessionDate,
    DateTime? now,
    int sessionCount = 0,
  }) async {
    final currentTime = now ?? DateTime.now();
    return AgentResponse(
      content: _getLocalGreeting(
        lastSessionDate: lastSessionDate,
        now: currentTime,
      ),
      layer: AgentLayer.ruleBasedLocal,
    );
  }

  @override
  Future<AgentResponse?> getFollowUp({
    required String latestUserMessage,
    required List<String> conversationHistory,
    required int followUpCount,
    List<Map<String, String>>? allMessages,
  }) async {
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

  @override
  Future<AgentResponse> generateSummary({
    required List<String> userMessages,
    List<Map<String, String>>? allMessages,
  }) async {
    return AgentResponse(
      content: generateLocalSummaryText(userMessages),
      layer: AgentLayer.ruleBasedLocal,
    );
  }

  @override
  Future<AgentResponse> getResumeGreeting() async {
    return const AgentResponse(
      content: "Welcome back! Let's continue where you left off.",
      layer: AgentLayer.ruleBasedLocal,
    );
  }

  // =========================================================================
  // Public helper (used by AgentRepository for journal-only mode summary)
  // =========================================================================

  /// Generate a rule-based summary from user messages.
  ///
  /// Exposed as public so AgentRepository can force Layer A summary
  /// in journal-only mode regardless of the active layer.
  String generateLocalSummaryText(List<String> userMessages) {
    return generateFirstSentenceSummary(userMessages);
  }

  // =========================================================================
  // Private methods
  // =========================================================================

  /// Rule-based greeting.
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

  /// Rule-based follow-up.
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
}
