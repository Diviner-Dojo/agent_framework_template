// ===========================================================================
// file: lib/constants/voice_recovery_messages.dart
// purpose: Static const strings for all verbal recovery and confirmation
//          messages spoken by the voice orchestrator.
//
// Centralizing messages here avoids scattering user-facing strings across
// the orchestrator's state machine transitions. All messages are spoken
// via TTS, so they should be conversational and concise.
//
// See: ADR-0015 (Voice Mode Architecture, Phase 7B)
// ===========================================================================

/// Verbal messages spoken by the voice orchestrator during continuous mode.
///
/// These are spoken via TTS to provide hands-free feedback. Keep messages
/// short and conversational — they're heard, not read.
class VoiceRecoveryMessages {
  VoiceRecoveryMessages._(); // coverage:ignore-line

  // =========================================================================
  // Session lifecycle
  // =========================================================================

  /// Spoken when continuous voice mode starts.
  static const greeting = "What's on your mind?";

  /// Spoken when the user returns after audio focus loss.
  static const welcomeBack = 'Go ahead.';

  /// Spoken when the session ends via voice command.
  static const sessionEndConfirm = 'Saving your session. Take care!';

  /// Spoken after the closing summary is generated.
  static const sessionEndComplete =
      'Your session has been saved. See you next time.';

  // =========================================================================
  // Verbal close commands
  // =========================================================================

  /// Spoken when a low-confidence end-session command is detected.
  static const endSessionConfirmPrompt =
      'Did you want to end the session? Say yes or no.';

  /// Spoken when the user confirms discarding the session.
  static const verbalDiscardConfirm =
      'Are you sure you want to discard this entry? Say yes to confirm.';

  /// Spoken after the session is discarded.
  static const discardComplete = 'Entry discarded. Nothing was saved.';

  /// Spoken when a discard or end confirmation is cancelled.
  static const confirmationCancelled = "OK, let's keep going.";

  /// Spoken when undo is available after ending a session.
  static const undoAvailable =
      'If you want to continue, say undo within thirty seconds.';

  /// Spoken when the undo window has expired.
  static const undoExpired = 'The undo window has closed.';

  /// Spoken when undo successfully resumes the session.
  static const undoSuccess = "OK, I've reopened your session. Go ahead.";

  // =========================================================================
  // Error recovery
  // =========================================================================

  /// Spoken when the STT engine encounters an error.
  static const sttFailure =
      "I'm having trouble hearing you. You can type instead.";

  /// Spoken when no speech is detected within the silence timeout.
  static const sttEmpty = "I didn't catch anything. I'm still listening.";

  /// Spoken after 3 consecutive STT timeouts (escalation).
  static const sttEscalation =
      'Having trouble hearing you. Try speaking louder, or switch to text.';

  /// Spoken when the LLM is taking longer than expected (non-blocking).
  static const llmThinking = 'Still thinking...';

  /// Spoken when a general error occurs during processing.
  static const processingError =
      'Something went wrong. You can try again or type your message.';

  // =========================================================================
  // Mode transitions
  // =========================================================================

  /// Spoken when pausing (e.g., audio focus loss or app backgrounding).
  static const paused = 'Paused.';

  /// Spoken when voice mode is interrupted by the user tapping interrupt.
  static const interrupted = "I'll stop talking. Go ahead.";
}
