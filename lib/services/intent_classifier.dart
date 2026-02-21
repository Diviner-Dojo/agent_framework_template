// ===========================================================================
// file: lib/services/intent_classifier.dart
// purpose: Classifies user messages as journal entries or recall queries.
//
// Uses rule-based pattern matching (not LLM) per ADR-0013 §2.
// Conservative default: messages classify as 'journal' unless the
// classifier has high confidence in query intent. This prevents jarring
// mode switches during active journaling.
//
// Confidence tiers:
//   ≥0.8: High — automatically route to recall
//   0.5–0.8: Ambiguous — show inline confirmation prompt
//   <0.5: Low — continue normal journaling
//
// NOTE: All patterns are English-only. Extend with i18n pattern sets
// before non-English market launch — without patterns, the classifier
// silently defaults to journal for all input (no error, no recall).
//
// See: ADR-0013 (Search + Memory Recall Architecture)
// ===========================================================================

/// The type of intent detected in a user message.
enum IntentType {
  /// Normal journaling conversation.
  journal,

  /// A query about past journal entries (recall request).
  query,
}

/// The result of intent classification.
///
/// Contains the classified intent type, confidence score, and extracted
/// search terms that can be used for the recall query.
class IntentResult {
  /// Whether the message is a journal entry or a recall query.
  final IntentType type;

  /// Confidence in the classification (0.0 to 1.0).
  ///
  /// High (≥0.8): auto-route to recall.
  /// Ambiguous (0.5–0.8): show inline confirmation.
  /// Low (<0.5): continue journaling.
  final double confidence;

  /// Keywords extracted from the message for search.
  ///
  /// Only meaningful when [type] is [IntentType.query].
  /// Used by SearchRepository to find matching sessions.
  final List<String> searchTerms;

  const IntentResult({
    required this.type,
    required this.confidence,
    this.searchTerms = const [],
  });
}

/// Classifies user messages as journal entries or recall queries.
///
/// Uses pattern matching to detect query intent signals:
/// - Question words with past tense ("What did I...", "When was...")
/// - Temporal references ("last week", "yesterday")
/// - Recall verbs ("remember when", "find entries about")
/// - Meta-questions ("How often do I...", "Who did I mention...")
///
/// Conservative default: returns [IntentType.journal] unless multiple
/// signals combine to produce high confidence.
class IntentClassifier {
  /// Classify a user message as journal or query.
  ///
  /// Returns [IntentResult] with type, confidence, and search terms.
  /// Empty or whitespace-only input always returns journal with 0 confidence.
  IntentResult classify(String message) {
    final trimmed = message.trim();

    // Empty/whitespace input is always journal.
    if (trimmed.isEmpty) {
      return const IntentResult(type: IntentType.journal, confidence: 0.0);
    }

    // Very short messages (≤4 words) are almost always conversational.
    // "What?", "Really?", "Why not?", "Tell me more" — all journal.
    final words = trimmed.split(RegExp(r'\s+'));
    if (words.length <= 4 && !_hasStrongQuerySignal(trimmed)) {
      return const IntentResult(type: IntentType.journal, confidence: 0.1);
    }

    // Score the message across multiple signal categories.
    double score = 0.0;
    final searchTerms = <String>[];

    // Category 1: Question words + past tense / recall framing.
    final questionPastMatch = _questionPastPattern.firstMatch(trimmed);
    if (questionPastMatch != null) {
      score += 0.4;
      _extractSearchTerms(trimmed, searchTerms);
    }

    // Category 2: Temporal references.
    if (_temporalPattern.hasMatch(trimmed)) {
      // Only count temporal as query signal when combined with a question
      // structure. "I talked to her last week" is journal, not query.
      if (_isQuestionStructure(trimmed)) {
        score += 0.3;
      } else {
        // Temporal in narrative context — slight signal but not enough alone.
        score += 0.05;
      }
    }

    // Category 3: Explicit recall/search verbs in query context.
    final recallMatch = _recallVerbPattern.firstMatch(trimmed);
    if (recallMatch != null) {
      // "I remember feeling happy" is journal. "Do you remember when I..."
      // or "Find entries about..." is query.
      if (_isRecallAsQuery(trimmed)) {
        score += 0.35;
        _extractSearchTerms(trimmed, searchTerms);
      }
    }

    // Category 4: Meta-questions about patterns.
    if (_metaQuestionPattern.hasMatch(trimmed)) {
      score += 0.45;
      _extractSearchTerms(trimmed, searchTerms);
    }

    // Determine intent type based on score.
    final clampedScore = score.clamp(0.0, 1.0);
    if (clampedScore >= 0.5) {
      // Remove duplicates from search terms.
      final uniqueTerms = searchTerms.toSet().toList();
      return IntentResult(
        type: IntentType.query,
        confidence: clampedScore,
        searchTerms: uniqueTerms.isEmpty ? [trimmed] : uniqueTerms,
      );
    }

    return IntentResult(
      type: IntentType.journal,
      confidence: 1.0 - clampedScore,
    );
  }

  // =========================================================================
  // Pattern definitions
  // =========================================================================

  /// Question words followed by past tense or recall framing.
  /// Matches: "What did I...", "When was the last time...",
  /// "Have I ever...", "Where did I go...", "Who did I..."
  /// No ^ anchor — allows conversational preambles ("Oh, what did I...").
  static final _questionPastPattern = RegExp(
    r'\b(what|when|where|who|how|why|did|have|has)\b.*(did i|have i|was the|were the|i (did|was|went|said|felt|talked|mentioned|wrote))',
    caseSensitive: false,
  );

  /// Temporal references: days, weeks, months, specific dates.
  static final _temporalPattern = RegExp(
    r'\b(yesterday|last (week|month|year|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|(\d+ )?(days?|weeks?|months?) ago|in (january|february|march|april|may|june|july|august|september|october|november|december)|this (week|month|year)|the other day|recently)\b',
    caseSensitive: false,
  );

  /// Recall/search verbs.
  static final _recallVerbPattern = RegExp(
    r'\b(remember|recall|find|search|look up|look for|tell me about)\b',
    caseSensitive: false,
  );

  /// Meta-questions about patterns and frequency.
  /// Matches: "How often do I...", "Who do I mention...",
  /// "What topics come up...", "Do I ever talk about..."
  static final _metaQuestionPattern = RegExp(
    r'\b(how often|how many times|who do i (mention|talk about)|what (topics?|things?|patterns?) (do i|come up)|do i (ever|always|usually|often))\b',
    caseSensitive: false,
  );

  // =========================================================================
  // Helper methods
  // =========================================================================

  /// Check if a short message contains a strong enough signal to override
  /// the short-message journal default.
  ///
  /// Only a few short patterns are strong enough:
  /// "Find X", "Search X", "What did I X?"
  static bool _hasStrongQuerySignal(String text) {
    return RegExp(
      r'^(find|search|look up|look for)\b',
      caseSensitive: false,
    ).hasMatch(text);
  }

  /// Check if the message has question structure (starts with question word
  /// or ends with ?).
  static bool _isQuestionStructure(String text) {
    if (text.endsWith('?')) return true;
    return RegExp(
      r'^(what|when|where|who|how|why|did|have|has|do|does|can|could|is|was|were)\b',
      caseSensitive: false,
    ).hasMatch(text);
  }

  /// Distinguish "I remember feeling happy" (journal) from
  /// "Do you remember when I..." (query).
  ///
  /// Recall verbs as query: preceded by question structure, or followed by
  /// "when", "about", "if", or question mark.
  /// Recall verbs as journal: preceded by "I" in narrative context.
  static bool _isRecallAsQuery(String text) {
    // "Find entries about...", "Search for..." — always query.
    if (RegExp(
      r'^(find|search|look up|look for)\b',
      caseSensitive: false,
    ).hasMatch(text)) {
      return true;
    }
    // "Do you remember...", "Can you recall..." — query.
    if (RegExp(
      r'^(do you|can you|could you)\b',
      caseSensitive: false,
    ).hasMatch(text)) {
      return true;
    }
    // "remember when", "recall when/what/who" — query.
    if (RegExp(
      r'\b(remember|recall)\s+(when|what|who|where|how|if|that time)\b',
      caseSensitive: false,
    ).hasMatch(text)) {
      return true;
    }
    // "I remember feeling..." or "I recall being..." — journal.
    if (RegExp(
      r'\bi (remember|recall)\s+(feeling|being|having|thinking|wanting|seeing|hearing)\b',
      caseSensitive: false,
    ).hasMatch(text)) {
      return false;
    }
    // Question mark at end suggests query.
    if (text.endsWith('?')) return true;
    return false;
  }

  /// Extract meaningful search terms from a query message.
  ///
  /// Strips question words, stop words, and recall verbs to isolate
  /// the actual search content.
  static void _extractSearchTerms(String text, List<String> terms) {
    // Remove question scaffolding and recall verbs.
    var cleaned = text
        .replaceAll(
          RegExp(
            r'\b(what|when|where|who|how|why|did|have|has|do|does|can|could|is|was|were|i|you|the|a|an|my|about|ever|last|time|remember|recall|find|search|look up|look for|tell me|entries?)\b',
            caseSensitive: false,
          ),
          '',
        )
        .replaceAll(RegExp(r'[?.,!]'), '')
        .trim();

    // Split into words and filter out empty/single-char tokens.
    final words = cleaned
        .split(RegExp(r'\s+'))
        .where((w) => w.length > 1)
        .toList();

    if (words.isNotEmpty) {
      terms.addAll(words);
    }
  }
}
