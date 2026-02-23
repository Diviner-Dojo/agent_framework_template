// ===========================================================================
// file: lib/services/voice_command_classifier.dart
// purpose: Rule-based classifier for voice commands during continuous mode.
//
// Modeled on IntentClassifier (lib/services/intent_classifier.dart):
//   Both use regex pattern matching with confidence scoring. This classifier
//   detects session-control commands ("I'm done", "delete this", "undo")
//   while IntentClassifier detects journal-vs-recall intent.
//
// Confidence tiers:
//   >=0.8: High — execute command directly (with verbal confirmation for
//          destructive actions like discard)
//   <0.8:  Low — ask for verbal confirmation before executing
//
// Ambiguity handling:
//   "I'm done with the dishes" vs "I'm done journaling" — the classifier
//   uses context clues (standalone phrases, trailing punctuation) to
//   distinguish. When unsure, verbal confirmation is always required.
//
// See: ADR-0015 (Voice Mode Architecture, Phase 7B)
// ===========================================================================

/// Types of voice commands that control the session.
enum VoiceCommand {
  /// No command detected — treat as normal journal input.
  none,

  /// End the current session (e.g., "I'm done", "goodbye").
  endSession,

  /// Discard the current session (e.g., "delete this", "throw it away").
  discard,

  /// Undo the last session close (e.g., "undo", "go back").
  undo,
}

/// Result of voice command classification.
///
/// Contains the detected command and a confidence score. The orchestrator
/// uses [confidence] to decide whether to execute directly (>=0.8) or
/// request verbal confirmation (<0.8).
class VoiceCommandResult {
  /// The detected command type.
  final VoiceCommand command;

  /// Confidence in the classification (0.0 to 1.0).
  ///
  /// >=0.8: High confidence — execute (with verbal confirm for destructive).
  /// <0.8:  Low confidence — ask "Did you mean to...?"
  final double confidence;

  const VoiceCommandResult({required this.command, required this.confidence});

  @override
  String toString() =>
      'VoiceCommandResult(command: $command, confidence: $confidence)';
}

/// Classifies transcribed speech as voice commands or normal input.
///
/// Uses rule-based pattern matching to detect end-session, discard, and
/// undo commands. Conservative default: returns [VoiceCommand.none] unless
/// patterns match with sufficient confidence.
class VoiceCommandClassifier {
  /// Classify a transcribed text as a voice command or normal input.
  ///
  /// Returns [VoiceCommandResult] with the command type and confidence.
  /// Empty input always returns [VoiceCommand.none] with 0 confidence.
  VoiceCommandResult classify(String text) {
    final cleaned = _clean(text);

    if (cleaned.isEmpty) {
      return const VoiceCommandResult(
        command: VoiceCommand.none,
        confidence: 0.0,
      );
    }

    // Check undo first — it's the most specific and least ambiguous.
    final undoResult = _checkUndo(cleaned);
    if (undoResult != null) return undoResult;

    // Check discard — destructive, so we want high confidence.
    final discardResult = _checkDiscard(cleaned);
    if (discardResult != null) return discardResult;

    // Check end session — most common voice command.
    final endResult = _checkEndSession(cleaned);
    if (endResult != null) return endResult;

    return const VoiceCommandResult(
      command: VoiceCommand.none,
      confidence: 0.0,
    );
  }

  // ===========================================================================
  // Pattern checks
  // ===========================================================================

  /// Check for undo commands.
  VoiceCommandResult? _checkUndo(String text) {
    // Strong undo signals — standalone or nearly standalone.
    if (_strongUndoPattern.hasMatch(text)) {
      return const VoiceCommandResult(
        command: VoiceCommand.undo,
        confidence: 0.9,
      );
    }

    // Weaker undo signals — could be conversational.
    if (_weakUndoPattern.hasMatch(text)) {
      return const VoiceCommandResult(
        command: VoiceCommand.undo,
        confidence: 0.7,
      );
    }

    return null;
  }

  /// Check for discard commands.
  VoiceCommandResult? _checkDiscard(String text) {
    // Strong discard signals.
    if (_strongDiscardPattern.hasMatch(text)) {
      return const VoiceCommandResult(
        command: VoiceCommand.discard,
        confidence: 0.9,
      );
    }

    // Moderate discard signals.
    if (_moderateDiscardPattern.hasMatch(text)) {
      return const VoiceCommandResult(
        command: VoiceCommand.discard,
        confidence: 0.7,
      );
    }

    return null;
  }

  /// Check for end-session commands.
  VoiceCommandResult? _checkEndSession(String text) {
    // Strong end signals — standalone phrases that clearly mean "stop."
    if (_strongEndPattern.hasMatch(text)) {
      // But check for false positives: "I'm done with X" where X is
      // a topic, not a session-control word.
      if (_endSessionFalsePositive.hasMatch(text)) {
        return const VoiceCommandResult(
          command: VoiceCommand.endSession,
          confidence: 0.5,
        );
      }
      return const VoiceCommandResult(
        command: VoiceCommand.endSession,
        confidence: 0.9,
      );
    }

    // Moderate end signals — need more context.
    if (_moderateEndPattern.hasMatch(text)) {
      return const VoiceCommandResult(
        command: VoiceCommand.endSession,
        confidence: 0.7,
      );
    }

    return null;
  }

  // ===========================================================================
  // Pattern definitions
  // ===========================================================================

  // --- Undo patterns ---

  /// Strong undo: standalone "undo", "go back", "reopen".
  static final _strongUndoPattern = RegExp(
    r'^(undo|go back|take it back|reopen|re-open|open it back up|continue my journal|add to today)$',
    caseSensitive: false,
  );

  /// Weak undo: phrases containing undo intent but with more words.
  static final _weakUndoPattern = RegExp(
    r"\b(undo that|take that back|i (want|need) to go back|can (you |i )?(undo|go back|reopen)|wait i('m| am) not done)\b",
    caseSensitive: false,
  );

  // --- Discard patterns ---

  /// Strong discard: clear intent to delete.
  static final _strongDiscardPattern = RegExp(
    r'^(delete this|discard|discard this|throw (it|this) away|trash (it|this)|scrap (it|this)|erase (it|this|everything))$',
    caseSensitive: false,
  );

  /// Moderate discard: phrases with discard intent but more context.
  static final _moderateDiscardPattern = RegExp(
    r'\b(delete (this |the )?(entry|session|journal)|discard (this |the )?(entry|session)|don.t save (this|it|anything)|throw (this |it )away|get rid of (this|it))\b',
    caseSensitive: false,
  );

  // --- End session patterns ---

  /// Strong end: standalone phrases that clearly signal session termination.
  ///
  /// "stop", "finish", and "bye" are excluded here because they are common
  /// in narrative speech ("I told him to stop"). They live in
  /// [_moderateEndPattern] where they trigger verbal confirmation.
  static final _strongEndPattern = RegExp(
    r"^(i'm done|i am done|that's (it|all)|that is (it|all)|goodbye|good bye|wrap (it|this) up|end session|end the session|i'm finished|i am finished|done for (now|today)|that's all for (now|today))$",
    caseSensitive: false,
  );

  /// Moderate end: phrases that suggest ending but could be conversational.
  /// Includes "stop", "finish", "bye" as standalone words — too common in
  /// narrative speech for high-confidence direct execution.
  static final _moderateEndPattern = RegExp(
    r"^(stop|finish|bye)$|\b(i think (i'm|i am|that's) (done|finished|good)|let's (stop|end|wrap|finish)|i('m| am) (ready to )?(stop|end|finish|wrap up)|save (and|&) (close|end|stop)|nothing (more|else)( to (say|add|share))?)\b",
    caseSensitive: false,
  );

  /// False positive check for "I'm done with X" where X is a topic.
  /// These indicate the user is talking ABOUT being done, not commanding.
  static final _endSessionFalsePositive = RegExp(
    r"\b(i'm done|i am done) (with|about|talking about|thinking about|for) \w",
    caseSensitive: false,
  );

  // ===========================================================================
  // Helpers
  // ===========================================================================

  /// Clean input text: trim, strip trailing punctuation, lowercase.
  static String _clean(String text) {
    return text
        .trim()
        .replaceAll(RegExp(r'[.!?,;:]+$'), '')
        .trim()
        .toLowerCase();
  }
}
