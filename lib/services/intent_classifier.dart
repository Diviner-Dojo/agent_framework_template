// ===========================================================================
// file: lib/services/intent_classifier.dart
// purpose: Classifies user messages into intent categories for routing.
//
// Uses rule-based pattern matching (not LLM) per ADR-0013 §2.
// Conservative default: messages classify as 'journal' unless the
// classifier has high confidence in a specific intent. This prevents
// jarring mode switches during active journaling.
//
// Intent types (ADR-0020 §3):
//   - journal: normal journaling conversation
//   - query: recall about past journal entries
//   - calendarEvent: create/schedule a calendar event
//   - reminder: set a reminder
//
// Multi-intent ranking: classifyMulti() returns a ranked list of
// IntentResult objects. The top-ranked intent drives routing. This allows
// overlapping signals to be resolved by comparing confidence scores
// rather than exclusive if/else branching.
//
// Confidence tiers:
//   ≥0.8: High — automatically route to handler
//   0.5–0.8: Ambiguous — show inline confirmation prompt
//   <0.5: Low — continue normal journaling
//
// Temporal disambiguation (ADR-0020 §3):
//   Temporal references score for recall ONLY when combined with
//   past-tense question structure. Calendar/reminder score when
//   temporal references combine with future-tense imperative/action verbs.
//
// NOTE: All patterns are English-only. Extend with i18n pattern sets
// before non-English market launch — without patterns, the classifier
// silently defaults to journal for all input (no error, no recall).
//
// See: ADR-0013 (Search + Memory Recall Architecture)
// See: ADR-0020 (Google Calendar Integration)
// ===========================================================================

/// The type of intent detected in a user message.
enum IntentType {
  /// Normal journaling conversation.
  journal,

  /// A query about past journal entries (recall request).
  query,

  /// Create or schedule a calendar event.
  calendarEvent,

  /// Set a reminder.
  reminder,

  /// Create a task / to-do item.
  task,

  /// Query about today's/tomorrow's schedule and tasks (day overview).
  dayQuery,
}

/// The result of intent classification.
///
/// Contains the classified intent type, confidence score, and extracted
/// search terms that can be used for the recall query.
class IntentResult {
  /// The detected intent type.
  final IntentType type;

  /// Confidence in the classification (0.0 to 1.0).
  ///
  /// High (≥0.8): auto-route to handler.
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

/// Classifies user messages into intent categories for routing.
///
/// Uses pattern matching to detect intent signals across four categories:
/// - **Query/recall**: question words, past tense, temporal + question,
///   recall verbs, meta-questions about patterns
/// - **Calendar**: scheduling verbs, calendar references, event nouns
///   with future temporal context
/// - **Reminder**: "remind me", "don't forget", "remember to"
/// - **Journal**: conservative default when no other intent scores high
///
/// Temporal disambiguation (ADR-0020 §3): temporal references score for
/// recall ONLY when combined with past-tense question structure. Calendar/
/// reminder score when temporal references combine with future-tense
/// imperative/action verbs.
class IntentClassifier {
  /// Classify a user message (backward-compatible single result).
  ///
  /// Returns the top-ranked [IntentResult] from [classifyMulti].
  /// Empty or whitespace-only input always returns journal with 0 confidence.
  IntentResult classify(String message) {
    return classifyMulti(message).first;
  }

  /// Classify a user message and return ranked intent results.
  ///
  /// Returns a list of [IntentResult] objects sorted by confidence
  /// (highest first). The top-ranked intent drives routing. Intents
  /// with scores below 0.3 are excluded. If no intent reaches the
  /// inclusion threshold, returns a single journal result.
  List<IntentResult> classifyMulti(String message) {
    final trimmed = message.trim();

    // Empty/whitespace input is always journal.
    if (trimmed.isEmpty) {
      return const [IntentResult(type: IntentType.journal, confidence: 0.0)];
    }

    // Very short messages (≤4 words) are almost always conversational.
    // "What?", "Really?", "Why not?", "Tell me more" — all journal.
    final words = trimmed.split(RegExp(r'\s+'));
    if (words.length <= 4 &&
        !_hasStrongQuerySignal(trimmed) &&
        !_hasStrongCalendarSignal(trimmed) &&
        !_hasStrongReminderSignal(trimmed) &&
        !_hasStrongTaskSignal(trimmed) &&
        !_hasStrongDayQuerySignal(trimmed)) {
      return const [IntentResult(type: IntentType.journal, confidence: 0.1)];
    }

    // Score each intent type independently.
    double queryScore = 0.0;
    double calendarScore = 0.0;
    double reminderScore = 0.0;
    final searchTerms = <String>[];

    // === Query signals (existing logic, unchanged) ===

    // Category 1: Question words + past tense / recall framing.
    final questionPastMatch = _questionPastPattern.firstMatch(trimmed);
    if (questionPastMatch != null) {
      queryScore += 0.4;
      _extractSearchTerms(trimmed, searchTerms);
    }

    // Category 3: Explicit recall/search verbs in query context.
    final recallMatch = _recallVerbPattern.firstMatch(trimmed);
    if (recallMatch != null) {
      // "I remember feeling happy" is journal. "Do you remember when I..."
      // or "Find entries about..." is query.
      if (_isRecallAsQuery(trimmed)) {
        queryScore += 0.35;
        _extractSearchTerms(trimmed, searchTerms);
      }
    }

    // Category 4: Meta-questions about patterns.
    if (_metaQuestionPattern.hasMatch(trimmed)) {
      queryScore += 0.45;
      _extractSearchTerms(trimmed, searchTerms);
    }

    // === Calendar signals ===

    if (_calendarIntentPattern.hasMatch(trimmed)) {
      calendarScore += 0.5;
    }

    // Event noun + future temporal → calendar signal.
    // Guarded by: future temporal (not past like "last week") AND
    // not a past-tense question (not "What meeting did I have?").
    if (_eventNounPattern.hasMatch(trimmed) &&
        _futureTemporalPattern.hasMatch(trimmed) &&
        !_questionPastPattern.hasMatch(trimmed)) {
      calendarScore += 0.4;
    }

    // Time specification boosts calendar (guarded by !questionPast).
    if (_timeSpecPattern.hasMatch(trimmed) &&
        !_questionPastPattern.hasMatch(trimmed)) {
      calendarScore += 0.15;
    }

    // === Reminder signals ===

    if (_reminderPattern.hasMatch(trimmed)) {
      reminderScore += 0.5;
    }

    // === Task signals ===
    double taskScore = 0.0;

    if (_taskIntentPattern.hasMatch(trimmed)) {
      taskScore += 0.5;
    }

    // "Add X to my list" without explicit "task" / "to-do" is a moderate signal.
    if (_taskListReferencePattern.hasMatch(trimmed)) {
      taskScore += 0.5;
    }

    // Disambiguation: "remind me" always wins over task.
    if (reminderScore > 0 && taskScore > 0) {
      taskScore = 0.0;
    }

    // Disambiguation: when explicit task keyword is present, task wins.
    // Otherwise calendar takes priority over task.
    if (calendarScore > 0 && taskScore > 0) {
      if (_taskIntentPattern.hasMatch(trimmed)) {
        calendarScore = 0.0; // Explicit task keyword → task wins.
      } else {
        taskScore = 0.0; // No explicit task keyword → calendar wins.
      }
    }

    // === Day query signals ===
    double dayQueryScore = 0.0;

    if (_dayQueryPattern.hasMatch(trimmed)) {
      dayQueryScore += 0.55;
    }

    // Task-specific day queries.
    if (_taskDayQueryPattern.hasMatch(trimmed)) {
      dayQueryScore += 0.5;
    }

    // Guard: past-tense question → recall, not day query.
    if (dayQueryScore > 0 && _questionPastPattern.hasMatch(trimmed)) {
      dayQueryScore = 0.0;
    }

    // === Temporal modifier (context-dependent) ===
    //
    // Temporal references are ambiguous — they could indicate recall
    // (past-tense question) or scheduling (future-tense action).
    // We assign the temporal boost based on what other signals are present.
    if (_temporalPattern.hasMatch(trimmed)) {
      if (calendarScore > 0 || reminderScore > 0 || taskScore > 0) {
        // Calendar/reminder/task context: temporal boosts the dominant intent.
        final maxIntent = [
          calendarScore,
          reminderScore,
          taskScore,
        ].reduce((a, b) => a > b ? a : b);
        if (maxIntent == calendarScore && calendarScore >= reminderScore) {
          calendarScore += 0.25;
        } else if (maxIntent == reminderScore) {
          reminderScore += 0.25;
        } else {
          taskScore += 0.15;
        }
      } else if (dayQueryScore > 0) {
        dayQueryScore += 0.2;
      } else if (_isQuestionStructure(trimmed)) {
        // Past-tense question context: temporal boosts recall.
        queryScore += 0.3;
      } else if (_hasFutureActionContext(trimmed)) {
        // Future imperative without explicit calendar/reminder verb.
        calendarScore += 0.25;
      } else {
        // Narrative context: minimal recall signal.
        queryScore += 0.05;
      }
    }

    // === Build ranked results ===
    //
    // Primary intents must reach the 0.5 threshold to be actionable.
    // Sub-threshold intents are appended for multi-intent visibility
    // (e.g., collision detection) but don't drive routing.

    final results = <IntentResult>[];

    final clampedQuery = queryScore.clamp(0.0, 1.0);
    final clampedCalendar = calendarScore.clamp(0.0, 1.0);
    final clampedReminder = reminderScore.clamp(0.0, 1.0);
    final clampedTask = taskScore.clamp(0.0, 1.0);
    final clampedDayQuery = dayQueryScore.clamp(0.0, 1.0);

    // Add intents that reached the active threshold (>= 0.5).
    if (clampedQuery >= 0.5) {
      final uniqueTerms = searchTerms.toSet().toList();
      results.add(
        IntentResult(
          type: IntentType.query,
          confidence: clampedQuery,
          searchTerms: uniqueTerms.isEmpty ? [trimmed] : uniqueTerms,
        ),
      );
    }

    if (clampedCalendar >= 0.5) {
      results.add(
        IntentResult(
          type: IntentType.calendarEvent,
          confidence: clampedCalendar,
        ),
      );
    }

    if (clampedReminder >= 0.5) {
      results.add(
        IntentResult(type: IntentType.reminder, confidence: clampedReminder),
      );
    }

    if (clampedTask >= 0.5) {
      results.add(IntentResult(type: IntentType.task, confidence: clampedTask));
    }

    if (clampedDayQuery >= 0.5) {
      results.add(
        IntentResult(type: IntentType.dayQuery, confidence: clampedDayQuery),
      );
    }

    // Sort primary intents by confidence descending.
    results.sort((a, b) => b.confidence.compareTo(a.confidence));

    // If no intent reached threshold, journal is primary.
    if (results.isEmpty) {
      final maxOther = [
        clampedQuery,
        clampedCalendar,
        clampedReminder,
        clampedTask,
        clampedDayQuery,
      ].reduce((a, b) => a > b ? a : b);
      results.add(
        IntentResult(type: IntentType.journal, confidence: 1.0 - maxOther),
      );
    }

    // Append sub-threshold intents for multi-intent visibility.
    // These are secondary — routing uses results.first as primary.
    if (clampedQuery > 0 && clampedQuery < 0.5) {
      final uniqueTerms = searchTerms.toSet().toList();
      results.add(
        IntentResult(
          type: IntentType.query,
          confidence: clampedQuery,
          searchTerms: uniqueTerms.isEmpty ? [trimmed] : uniqueTerms,
        ),
      );
    }
    if (clampedCalendar > 0 && clampedCalendar < 0.5) {
      results.add(
        IntentResult(
          type: IntentType.calendarEvent,
          confidence: clampedCalendar,
        ),
      );
    }
    if (clampedReminder > 0 && clampedReminder < 0.5) {
      results.add(
        IntentResult(type: IntentType.reminder, confidence: clampedReminder),
      );
    }
    if (clampedTask > 0 && clampedTask < 0.5) {
      results.add(IntentResult(type: IntentType.task, confidence: clampedTask));
    }
    if (clampedDayQuery > 0 && clampedDayQuery < 0.5) {
      results.add(
        IntentResult(type: IntentType.dayQuery, confidence: clampedDayQuery),
      );
    }

    return results;
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

  /// Temporal references: past and future days, weeks, months, dates.
  ///
  /// Includes both past references (yesterday, last week, 3 days ago) and
  /// future references (tomorrow, next week, this evening) for calendar
  /// intent detection (ADR-0020 §3).
  static final _temporalPattern = RegExp(
    r'\b(yesterday|'
    r'last (week|month|year|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|'
    r'(\d+ )?(days?|weeks?|months?) ago|'
    r'in (january|february|march|april|may|june|july|august|september|october|november|december)|'
    r'in \d+ (minute|minutes|min|mins|hour|hours|hr|hrs|second|seconds|sec|secs)\b|'
    r'in (a|an) (minute|hour|second|sec)\b|'
    r'this (week|month|year)|'
    r'the other day|'
    r'recently|'
    r'tomorrow|'
    r'next (week|month|year|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|'
    r'tonight|'
    r'this (evening|afternoon|morning)|'
    r'on (monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b',
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

  /// Event nouns used in explicit calendar intent patterns.
  ///
  /// Shared between [_calendarIntentPattern] and [_hasStrongCalendarSignal].
  /// Both locations must be updated together whenever nouns are added or removed —
  /// keeping them in sync is enforced by this shared constant.
  ///
  /// Note: [_eventNounPattern] intentionally includes a broader set of nouns
  /// (breakfast, brunch, date, party, interview, conference, hangout) used only for
  /// temporal-disambiguation scoring, not for explicit scheduling intent. The two
  /// lists are not equivalent by design.
  static const _calendarEventNouns =
      r'(meeting|appointment|event|dinner|lunch|call|reservation)';

  /// Explicit calendar intent phrases.
  ///
  /// Matches imperative scheduling commands and calendar references:
  /// - "Schedule a meeting", "Book dinner", "Set up a call"
  /// - "Add to my calendar", "Put on calendar"
  /// - "I want to schedule", "Can you book"
  /// - "Add/set [modifier] <event noun>" — word-count wildcard covers any calendar
  ///   brand modifier (Google Calendar, Outlook Calendar, iCloud Calendar, etc.)
  ///   without a fixed char limit. Uses [_calendarEventNouns] shared constant.
  /// - "Okay add a meeting" — \b anchor (not ^) allows voice preambles.
  static final _calendarIntentPattern = RegExp(
    r'^(schedule|book|set up|plan|arrange)\b|'
            r'\b(add|put)\b.{0,40}\b(to|on)\s+(my\s+|the\s+)?(google\s+)?calendar\b|'
            r'\b(want to|need to|going to|let.?s|can you|could you)\s+(schedule|book|set up|plan|arrange)\b|'
            // Brand-agnostic: "add/set [0–4 words] <event noun>".
            // [\w-]+ treats hyphenated tokens (e.g. "follow-up") as a single word.
            // \b anchor (not ^) allows voice preambles ("Okay add a meeting").
            r'\b(add|set)\b(\s+[\w-]+){0,4}\s+\b' +
        _calendarEventNouns +
        r'\b',
    caseSensitive: false,
  );

  /// Future temporal references only (subset of _temporalPattern).
  ///
  /// Used to guard eventNoun+temporal scoring so that "I had a meeting
  /// last week" (past narrative) doesn't score as calendar intent.
  static final _futureTemporalPattern = RegExp(
    r'\b(tomorrow|'
    r'next (week|month|year|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|'
    r'tonight|'
    r'this (evening|afternoon|morning)|'
    r'on (monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b',
    caseSensitive: false,
  );

  /// Event nouns that suggest calendar context when combined with temporal.
  static final _eventNounPattern = RegExp(
    r'\b(meeting|appointment|event|dinner|lunch|breakfast|brunch|call|date|party|interview|reservation|conference|hangout)\b',
    caseSensitive: false,
  );

  /// Time specification pattern: "at 3pm", "from 2 to 4", "3:30".
  static final _timeSpecPattern = RegExp(
    r'\bat\s+\d{1,2}(:\d{2})?\s*(am|pm)?\b|'
    r'\bfrom\s+\d{1,2}(:\d{2})?\s*(am|pm)?\s+(to|until|till)\b|'
    r'\b\d{1,2}:\d{2}\s*(am|pm)?\b',
    caseSensitive: false,
  );

  /// Reminder intent phrases.
  ///
  /// Matches explicit reminder requests. "Remember to" is distinguished
  /// from "remember when" (recall) by the preposition.
  static final _reminderPattern = RegExp(
    r'\bremind me\b|'
    r'\bdon.?t (let me )?forget\b|'
    r'\bremember to\b|'
    r'\bmake sure i\b|'
    r'^remind\b',
    caseSensitive: false,
  );

  /// Task intent phrases — require explicit "task" or "to-do" keywords.
  ///
  /// Matches: "add a task", "create a task", "add me a to-do item",
  /// "add X to my task list", "new to-do", "put X on my list",
  /// "I need you to add a task".
  /// Does NOT match bare action verbs ("buy groceries") without task keywords.
  static final _taskIntentPattern = RegExp(
    r'\b(add|create|make|new)\s+(\w+\s+){0,2}(a\s+)?(task|to.?do)\b|'
    r'\badd\b.{0,50}\b(task\s*list|to.?do\s*list)\b|'
    r'^(add|create)\s+(a\s+)?task\b',
    caseSensitive: false,
  );

  /// Weaker task signal: "put X on my list" / "add X to my list".
  ///
  /// Without explicit "task" or "to-do", this is a weaker signal.
  static final _taskListReferencePattern = RegExp(
    r'\b(put|add)\b.{0,40}\b(on|to)\s+(my\s+)?list\b',
    caseSensitive: false,
  );

  /// Day query intent phrases.
  ///
  /// Matches present/future-tense questions about schedule:
  /// "What does my day look like?", "What's happening today?",
  /// "What's on my schedule?", "Tell me about my schedule".
  static final _dayQueryPattern = RegExp(
    r'\bwhat.{0,10}(my|the)\s+day\s+look\b|'
    r'\bwhat.{0,5}s?\s+(happening|going on|on my|on the)\b.{0,20}\b(today|tomorrow|schedule|calendar|agenda)\b|'
    r'\b(tell me about|give me|show me)\s+(my\s+)?(schedule|calendar|agenda|day)\b|'
    r'\bwhat.{0,5}s?\s+on\s+(my\s+)?(schedule|calendar|agenda|today|tomorrow)\b|'
    r'\bwhat.{0,5}s?\s+my\s+(day|schedule|calendar|agenda)\b|'
    r'\bhow.{0,5}s?\s+my\s+(day|schedule|calendar)\s+(look|shaping)\b',
    caseSensitive: false,
  );

  /// Task-specific day query: "any tasks for today?", "what tasks are due?"
  static final _taskDayQueryPattern = RegExp(
    r'\b(any|what)\s+tasks?\b.{0,20}\b(today|tomorrow|due|pending)\b|'
    r'\btasks?\s+(due|for)\s+(today|tomorrow)\b|'
    r'\bwhat.{0,10}(do i have|is)\b.{0,15}\b(today|tomorrow)\b',
    caseSensitive: false,
  );

  // =========================================================================
  // Helper methods
  // =========================================================================

  /// Check if a short message has a strong query signal.
  static bool _hasStrongQuerySignal(String text) {
    return RegExp(
      r'^(find|search|look up|look for)\b',
      caseSensitive: false,
    ).hasMatch(text);
  }

  /// Check if a short message has a strong calendar signal.
  ///
  /// Used by the short-message guard path in [classifyMulti] when
  /// `words.length <= 4`. The `^` anchor is intentional — this is a guard
  /// for short messages where start-of-string matching prevents false
  /// positives (unlike [_calendarIntentPattern] which uses `\b` for voice
  /// preamble support).
  ///
  /// Uses [_calendarEventNouns] — must be updated in sync with
  /// [_calendarIntentPattern]. See DISC-20260302-230547 (PR #57): failing to
  /// update both locations in the same commit is the root cause of that bug.
  static bool _hasStrongCalendarSignal(String text) {
    return RegExp(
      r'^(schedule|book|set up|plan|arrange)\b|'
              // Word-count wildcard: up to 4 intervening words.
              // [\w-]+ treats hyphenated tokens (e.g. "follow-up") as a single word.
              // ^ anchor preserved — short-message guard requires start-of-string.
              r'^(add|set)\b(\s+[\w-]+){0,4}\s+\b' +
          _calendarEventNouns +
          r'\b',
      caseSensitive: false,
    ).hasMatch(text);
  }

  /// Check if a short message has a strong reminder signal.
  static bool _hasStrongReminderSignal(String text) {
    return RegExp(r'^remind\b', caseSensitive: false).hasMatch(text);
  }

  /// Check if a short message has a strong task signal.
  static bool _hasStrongTaskSignal(String text) {
    return RegExp(
      r'^(add|create|new)\s+(\w+\s+){0,2}(a\s+)?(task|to.?do)\b',
      caseSensitive: false,
    ).hasMatch(text);
  }

  /// Check if a short message has a strong day query signal.
  static bool _hasStrongDayQuerySignal(String text) {
    return RegExp(
      r"^what.{0,5}s?\s+(my|on|happening|going)|"
      r"^what\s+tasks?\b|"
      r"^(show|give)\s+me\s+(my\s+)?(schedule|calendar|agenda|day)\b|"
      r"^tell\s+me\s+about\s+(my\s+)?(schedule|calendar|agenda|day)\b|"
      r"^any\s+tasks?\b",
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

  /// Check if the message has future-tense imperative/action context.
  ///
  /// Used for temporal disambiguation: temporal references in imperative
  /// sentences suggest scheduling intent rather than recall.
  static bool _hasFutureActionContext(String text) {
    // Imperative action verbs at the start of the sentence.
    if (RegExp(
      r'^(schedule|book|add|create|set up|put|plan|arrange|remind|meet)\b',
      caseSensitive: false,
    ).hasMatch(text)) {
      return true;
    }
    // Intent expression: "I want to schedule", "going to add".
    if (RegExp(
      r'\b(want to|need to|going to|let.?s)\s+(schedule|book|add|create|set up|plan|meet|arrange)\b',
      caseSensitive: false,
    ).hasMatch(text)) {
      return true;
    }
    return false;
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
