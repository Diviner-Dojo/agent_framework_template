// ===========================================================================
// file: lib/repositories/agent_repository.dart
// purpose: Rule-based conversation engine (Layer A) for Phase 1.
//
// This is the "brain" of the journaling assistant in Phase 1. It uses
// simple keyword detection and predefined question pools to drive a
// multi-turn journaling conversation. No AI, no network calls.
//
// Design Decision: AgentRepository is INTENTIONALLY STATELESS.
//   All conversation state (follow-up count, message history, used questions)
//   is owned by SessionNotifier in the providers layer (Task 8).
//   The repository receives everything it needs as method parameters.
//   This keeps it pure and trivially testable — no setup/teardown needed.
//
// Phase 3 Extension Point:
//   Phase 3 will add: final ClaudeApiService? _claudeService;
//   Phase 3 constructor: AgentRepository({ClaudeApiService? claudeService})
//     : _claudeService = claudeService;
//   The stateless design means Phase 3 can add the service without
//   restructuring the provider layer.
// ===========================================================================

import '../utils/keyword_extractor.dart';

/// The rule-based journaling agent for Phase 1.
///
/// Drives conversations through: greeting → follow-ups → summary → close.
/// All methods are synchronous (no async needed — pure logic, no I/O).
class AgentRepository {
  AgentRepository();

  // =========================================================================
  // Follow-up question pools
  // =========================================================================

  /// Emotional follow-up questions — used when the user expresses feelings.
  static const List<String> _emotionalFollowUps = [
    "That sounds like a lot. What do you think is driving that feeling?",
    "How long have you been feeling this way?",
    "Is there anything that helps when you feel like this?",
    "What would make things feel a little better right now?",
    "Have you noticed any patterns around when this feeling comes up?",
  ];

  /// Social follow-up questions — used when the user mentions people.
  static const List<String> _socialFollowUps = [
    "How did that interaction make you feel?",
    "What's your relationship with them like these days?",
    "Is there something you wish you'd said or done differently?",
    "How important is this person in your day-to-day life?",
    "What do you appreciate most about that relationship?",
  ];

  /// Work follow-up questions — used when the user mentions work topics.
  static const List<String> _workFollowUps = [
    "How do you feel about how that's going?",
    "What's the biggest challenge you're facing with that?",
    "Is there something you're looking forward to at work?",
    "How does this affect your work-life balance?",
    "What would success look like for you in this situation?",
  ];

  /// Generic follow-up questions — used when no keywords match.
  static const List<String> _genericFollowUps = [
    "Tell me more about that.",
    "What else is on your mind?",
    "How does that make you feel?",
    "Is there anything else you'd like to talk about?",
    "What's been the highlight of your day so far?",
  ];

  /// Words/phrases that signal the user wants to end the session.
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
  ];

  // =========================================================================
  // Public API
  // =========================================================================

  /// Get the opening greeting based on time of day and recency of last session.
  ///
  /// [lastSessionDate] — when the user's most recent session started.
  ///   If null, this is the user's first session ever.
  ///   If more than 2 days ago, triggers a "welcome back" greeting.
  ///
  /// [now] — injectable for deterministic testing. Defaults to DateTime.now().
  ///
  /// Time-of-day rules (using local time):
  ///   5:00 AM – 11:59 AM  → "Good morning! ..."
  ///   12:00 PM – 4:59 PM  → "How's your afternoon going?"
  ///   5:00 PM – 9:59 PM   → "How was your day?"
  ///   10:00 PM – 4:59 AM  → "Still up? What's on your mind?"
  String getGreeting({DateTime? lastSessionDate, DateTime? now}) {
    final currentTime = now ?? DateTime.now();

    // Check for gap since last session (> 2 days).
    if (lastSessionDate != null) {
      final daysSinceLastSession = currentTime
          .difference(lastSessionDate)
          .inDays;
      if (daysSinceLastSession >= 2) {
        return "It's been a few days — want to catch up?";
      }
    }

    // Time-of-day greeting based on local hour.
    final hour = currentTime.hour;

    if (hour >= 5 && hour < 12) {
      return "Good morning! Any plans or thoughts for today?";
    } else if (hour >= 12 && hour < 17) {
      return "How's your afternoon going?";
    } else if (hour >= 17 && hour < 22) {
      return "How was your day?";
    } else {
      // 10 PM – 4:59 AM
      return "Still up? What's on your mind?";
    }
  }

  /// Get a follow-up question based on the user's message.
  ///
  /// Returns null when the conversation should end (max follow-ups reached
  /// and user has responded to the closing prompt).
  ///
  /// [latestUserMessage] — the message the user just sent.
  /// [conversationHistory] — all previous follow-up questions asked in this
  ///   session (used to avoid repeating the same question).
  /// [followUpCount] — how many follow-ups have been asked so far.
  ///
  /// The conversation flow:
  ///   0-3 follow-ups: ask contextually relevant questions
  ///   At follow-up 3+: transition to closing with a summary prompt
  ///   After closing: return null to signal session end
  String? getFollowUp({
    required String latestUserMessage,
    required List<String> conversationHistory,
    required int followUpCount,
  }) {
    // After the closing message has been sent and user responded, end session.
    if (followUpCount > 3) {
      return null;
    }

    // At follow-up count 3, transition to closing.
    // The summary will be generated by generateLocalSummary() separately.
    if (followUpCount == 3) {
      return "Thanks for sharing. Is there anything else you'd like to add "
          "before we wrap up?";
    }

    // For follow-ups 0-2, use keyword-based question selection.
    final category = extractCategory(latestUserMessage);
    final pool = _getPoolForCategory(category);

    // Pick a question that hasn't been used yet in this session.
    for (final question in pool) {
      if (!conversationHistory.contains(question)) {
        return question;
      }
    }

    // All questions in this category have been used — fall back to generic.
    for (final question in _genericFollowUps) {
      if (!conversationHistory.contains(question)) {
        return question;
      }
    }

    // Extremely unlikely: all questions exhausted. Transition to closing.
    return "Thanks for sharing. Is there anything else you'd like to add "
        "before we wrap up?";
  }

  /// Generate a local summary from the user's messages.
  ///
  /// Phase 1 approach: extract the first sentence of each user message
  /// and combine them as bullet points.
  ///
  /// Phase 3 will replace this with Claude-generated summaries.
  ///
  /// [userMessages] — only the USER messages (not assistant messages).
  /// Returns an empty string if no messages provided.
  String generateLocalSummary(List<String> userMessages) {
    if (userMessages.isEmpty) return '';

    final sentences = <String>[];
    for (final message in userMessages) {
      final firstSentence = _extractFirstSentence(message);
      if (firstSentence.isNotEmpty) {
        sentences.add(firstSentence);
      }
    }

    if (sentences.isEmpty) return '';

    // Format as a simple list.
    return sentences.join('. ');
  }

  /// Determine if the session should end based on conversation state.
  ///
  /// Returns true when:
  ///   1. The follow-up count exceeds the maximum (4+), OR
  ///   2. The user's latest message is a "done" signal (e.g., "no", "bye")
  ///
  /// [followUpCount] — how many follow-ups have been asked.
  /// [latestUserMessage] — the user's most recent message text.
  bool shouldEndSession({
    required int followUpCount,
    required String latestUserMessage,
  }) {
    // Max follow-ups reached.
    if (followUpCount > 3) return true;

    // Check for explicit done signals.
    // We check if the ENTIRE message (trimmed, lowered) matches a done signal.
    // This avoids false positives like "I'm done with the project" matching
    // because we compare the whole message, not substrings.
    final trimmed = latestUserMessage.trim().toLowerCase();
    return _doneSignals.contains(trimmed);
  }

  // =========================================================================
  // Private helpers
  // =========================================================================

  /// Get the question pool for a keyword category.
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

  /// Extract the first sentence from a message.
  ///
  /// Looks for sentence-ending punctuation (. ! ?).
  /// If none found, returns the entire message (it's one short sentence).
  String _extractFirstSentence(String message) {
    final trimmed = message.trim();
    if (trimmed.isEmpty) return '';

    // Find the first sentence-ending punctuation.
    final match = RegExp(r'[.!?]').firstMatch(trimmed);
    if (match != null) {
      return trimmed.substring(0, match.end).trim();
    }

    // No punctuation found — return the whole message.
    return trimmed;
  }
}
