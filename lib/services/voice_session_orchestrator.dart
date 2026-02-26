// ===========================================================================
// file: lib/services/voice_session_orchestrator.dart
// purpose: State machine for the continuous voice loop (Phase 7B).
//
// The orchestrator manages both push-to-talk (7A) and continuous (7B) modes.
// It coordinates STT, TTS, and audio focus services, handling the full
// listen→process→speak→listen cycle without requiring screen touches.
//
// State machine transitions:
//   idle ──[startContinuousMode]──> speaking (greeting)
//   speaking ──[TTS complete]──> listening
//   listening ──[SpeechResult.isFinal]──> processing
//   processing ──[response ready]──> speaking
//   speaking ──[interrupt button]──> listening
//   any ──[error]──> error
//   error ──[recover/timeout]──> idle or listening
//   any ──[pause]──> paused
//   paused ──[resume]──> (previous phase)
//
// Architecture:
//   The orchestrator does NOT depend on SessionNotifier directly. Instead,
//   it receives callbacks for sendMessage, endSession, discardSession, and
//   resumeSession. This avoids circular provider dependencies.
//
// See: ADR-0015 (Voice Mode Architecture, Phase 7B)
// ===========================================================================

import 'dart:async';

import 'package:flutter/foundation.dart';

import 'audio_focus_service.dart';
import 'event_extraction_service.dart';
import 'speech_recognition_service.dart';
import 'text_to_speech_service.dart';
import 'voice_command_classifier.dart';
import '../constants/voice_recovery_messages.dart';

/// The phases of the voice orchestrator state machine.
enum VoiceLoopPhase {
  /// No voice activity. Default state.
  idle,

  /// STT is active, capturing user speech.
  listening,

  /// User speech captured, waiting for LLM response.
  processing,

  /// TTS is speaking the assistant's response.
  speaking,

  /// An error occurred. May recover or fall back to idle.
  error,

  /// Paused (audio focus loss, app backgrounded).
  paused,
}

/// Immutable state emitted by the voice orchestrator.
class VoiceOrchestratorState {
  /// Current phase of the voice loop.
  final VoiceLoopPhase phase;

  /// Real-time STT text shown on screen during listening.
  final String transcriptPreview;

  /// Error message when in error phase.
  final String? errorMessage;

  /// True when in continuous mode (auto-loop), false for push-to-talk.
  final bool isContinuousMode;

  const VoiceOrchestratorState({
    this.phase = VoiceLoopPhase.idle,
    this.transcriptPreview = '',
    this.errorMessage,
    this.isContinuousMode = false,
  });

  VoiceOrchestratorState copyWith({
    VoiceLoopPhase? phase,
    String? transcriptPreview,
    String? errorMessage,
    bool? isContinuousMode,
    bool clearError = false,
  }) {
    return VoiceOrchestratorState(
      phase: phase ?? this.phase,
      transcriptPreview: transcriptPreview ?? this.transcriptPreview,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      isContinuousMode: isContinuousMode ?? this.isContinuousMode,
    );
  }
}

/// Callback type for sending a message and getting the response text.
typedef SendMessageCallback =
    Future<String?> Function(String text, {String inputMethod});

/// Callback type for session lifecycle actions (end, discard).
typedef SessionActionCallback = Future<void> Function();

/// Callback type for resuming a session by ID.
typedef ResumeSessionCallback = Future<String?> Function(String sessionId);

/// Manages the continuous voice loop state machine.
///
/// Coordinates STT, TTS, and audio focus for hands-free journaling.
/// Handles both push-to-talk (7A) and continuous (7B) modes.
///
/// The orchestrator emits [VoiceOrchestratorState] via a [ValueNotifier]
/// so the UI can reactively rebuild on state changes.
class VoiceSessionOrchestrator {
  final SpeechRecognitionService _sttService;
  final TextToSpeechService _ttsService;
  final AudioFocusService _audioFocusService;
  final VoiceCommandClassifier _commandClassifier = VoiceCommandClassifier();

  /// Callbacks set by the UI to wire into SessionNotifier without
  /// creating circular provider dependencies.
  SendMessageCallback? onSendMessage;
  SessionActionCallback? onEndSession;
  SessionActionCallback? onDiscardSession;
  ResumeSessionCallback? onResumeSession;

  /// Callback for confirming a calendar event (verbal "yes").
  SessionActionCallback? onConfirmCalendarEvent;

  /// Callback for dismissing a calendar event (verbal "no").
  SessionActionCallback? onDismissCalendarEvent;

  /// The current orchestrator state.
  final ValueNotifier<VoiceOrchestratorState> stateNotifier = ValueNotifier(
    const VoiceOrchestratorState(),
  );

  /// Current state (convenience getter).
  VoiceOrchestratorState get state => stateNotifier.value;

  StreamSubscription<SpeechResult>? _recognitionSubscription;
  StreamSubscription<AudioFocusEvent>? _audioFocusSubscription;
  Timer? _silenceTimer;
  Timer? _undoTimer;
  Timer? _confirmationTimer;

  /// Phase before pausing — restored on resume.
  VoiceLoopPhase? _phaseBeforePause;

  /// Awaiting verbal confirmation for a command.
  bool _awaitingConfirmation = false;

  /// The command awaiting confirmation.
  VoiceCommand? _pendingCommand;

  /// The current active session ID, set by the UI when wiring callbacks.
  String? currentSessionId;

  /// Last closed session ID for undo support.
  String? _lastClosedSessionId;

  /// Whether TTS has been initialized.
  bool _ttsInitialized = false;

  /// Whether we are actively using audio (STT/TTS).
  /// Used to ignore audio focus loss events triggered by our own recording.
  bool _isOurAudioActive = false;

  /// Confidence threshold for direct command execution.
  static const _highConfidenceThreshold = 0.8;

  /// Silence timeout before re-prompting (seconds).
  final int _silenceTimeoutSeconds;

  /// Confirmation timeout (seconds) — prevents ambient audio spoofing.
  static const _confirmationTimeoutSeconds = 10;

  VoiceSessionOrchestrator({
    required SpeechRecognitionService sttService,
    required TextToSpeechService ttsService,
    required AudioFocusService audioFocusService,
    int silenceTimeoutSeconds = 15,
  }) : _sttService = sttService,
       _ttsService = ttsService,
       _silenceTimeoutSeconds = silenceTimeoutSeconds,
       _audioFocusService = audioFocusService {
    // Subscribe to audio focus changes.
    _audioFocusSubscription = _audioFocusService.onFocusChanged.listen(
      _onAudioFocusChanged,
    );
  }

  // ===========================================================================
  // Public API — Mode entry points
  // ===========================================================================

  /// Start continuous voice mode with a spoken greeting.
  ///
  /// Transition: idle → speaking (greeting) → listening → ...
  Future<void> startContinuousMode(String greeting) async {
    if (state.phase != VoiceLoopPhase.idle) return;

    // Reset any stale confirmation state from a previous session.
    _resetConfirmationState();

    _updateState(
      state.copyWith(
        phase: VoiceLoopPhase.speaking,
        isContinuousMode: true,
        clearError: true,
      ),
    );

    _isOurAudioActive = true;
    await _audioFocusService.requestFocus();
    await _speak(greeting);

    // After greeting finishes, start listening.
    if (state.phase == VoiceLoopPhase.speaking && state.isContinuousMode) {
      await _startListening();
    }
  }

  /// Start push-to-talk mode (single utterance).
  ///
  /// Transition: idle → listening → idle (after final result).
  Future<void> startPushToTalk() async {
    if (state.phase != VoiceLoopPhase.idle) return;

    // Reset any stale confirmation state from a previous session.
    _resetConfirmationState();

    _updateState(
      state.copyWith(
        phase: VoiceLoopPhase.listening,
        isContinuousMode: false,
        clearError: true,
      ),
    );

    _isOurAudioActive = true;
    await _audioFocusService.requestFocus();
    await _startListeningRaw();
  }

  /// Stop push-to-talk recording.
  Future<void> stopPushToTalk() async {
    if (state.phase != VoiceLoopPhase.listening || state.isContinuousMode) {
      return;
    }

    await _stopListening();
    _isOurAudioActive = false;
    await _audioFocusService.abandonFocus();
    _updateState(state.copyWith(phase: VoiceLoopPhase.idle));
  }

  /// Interrupt TTS and start listening.
  Future<void> interrupt() async {
    if (state.phase != VoiceLoopPhase.speaking) return;

    await _ttsService.stop();
    _updateState(
      state.copyWith(phase: VoiceLoopPhase.listening, transcriptPreview: ''),
    );

    if (state.isContinuousMode) {
      await _startListeningRaw();
      _startSilenceTimer();
    }
  }

  /// Pause the orchestrator (audio focus loss, app backgrounding).
  Future<void> pause() async {
    final currentPhase = state.phase;
    if (currentPhase == VoiceLoopPhase.idle ||
        currentPhase == VoiceLoopPhase.paused) {
      return;
    }

    _phaseBeforePause = currentPhase;
    _silenceTimer?.cancel();

    // Stop active audio.
    if (_sttService.isListening) {
      await _stopListening();
    }
    if (_ttsService.isSpeaking) {
      await _ttsService.stop();
    }

    _updateState(state.copyWith(phase: VoiceLoopPhase.paused));
  }

  /// Resume from paused state.
  Future<void> resume() async {
    if (state.phase != VoiceLoopPhase.paused) return;

    final previousPhase = _phaseBeforePause ?? VoiceLoopPhase.idle;
    _phaseBeforePause = null;

    if (!state.isContinuousMode) {
      // Push-to-talk: return to idle.
      await _audioFocusService.abandonFocus();
      _updateState(state.copyWith(phase: VoiceLoopPhase.idle));
      return;
    }

    // Continuous mode: speak welcome back and resume listening.
    await _audioFocusService.requestFocus();

    if (previousPhase == VoiceLoopPhase.listening ||
        previousPhase == VoiceLoopPhase.speaking) {
      _updateState(state.copyWith(phase: VoiceLoopPhase.speaking));
      await _speak(VoiceRecoveryMessages.welcomeBack);
      if (state.phase == VoiceLoopPhase.speaking) {
        await _startListening();
      }
    } else {
      _updateState(state.copyWith(phase: previousPhase));
    }
  }

  /// Stop the orchestrator and return to idle.
  Future<void> stop() async {
    _silenceTimer?.cancel();
    _undoTimer?.cancel();
    _resetConfirmationState();

    if (_sttService.isListening) {
      await _stopListening();
    }
    if (_ttsService.isSpeaking) {
      await _ttsService.stop();
    }
    _isOurAudioActive = false;
    await _audioFocusService.abandonFocus();

    _updateState(const VoiceOrchestratorState());
  }

  /// Notify the orchestrator that a new assistant message is available.
  ///
  /// In continuous mode, the orchestrator speaks the response and resumes
  /// listening. Called by the UI when it detects a new assistant message.
  Future<void> onAssistantMessage(String text) async {
    if (!state.isContinuousMode) {
      // Push-to-talk: just speak the message.
      await _speakNonBlocking(text);
      return;
    }

    if (state.phase == VoiceLoopPhase.processing) {
      // Transition: processing → speaking → listening
      _updateState(state.copyWith(phase: VoiceLoopPhase.speaking));
      await _speakInSentences(text);

      // Resume listening after speaking (if still in continuous mode).
      if (state.phase == VoiceLoopPhase.speaking && state.isContinuousMode) {
        await _startListening();
      }
    }
  }

  /// Capture a voice description for a photo (Phase 9 — ADR-0018).
  ///
  /// Speaks "Tell me about this photo", then listens for a response.
  /// Returns the captured description text, or null if:
  ///   - Voice mode is not active
  ///   - The user stays silent for 5 seconds (timeout → skip)
  ///   - STT is not initialized
  ///
  /// The orchestrator temporarily pauses the normal voice loop,
  /// captures the description, then returns to the previous state.
  Future<String?> capturePhotoDescription() async {
    // Only works if STT service is initialized.
    if (!_sttService.isInitialized) return null;

    final wasInContinuousMode = state.isContinuousMode;
    final previousPhase = state.phase;

    // Pause normal listening if active.
    if (_sttService.isListening) {
      await _stopListening();
    }
    _silenceTimer?.cancel();

    // Speak the prompt.
    _updateState(state.copyWith(phase: VoiceLoopPhase.speaking));
    await _speak('Tell me about this photo.');

    if (state.phase != VoiceLoopPhase.speaking) {
      // Interrupted or stopped — return without description.
      return null;
    }

    // Listen for the description with a 5-second silence timeout.
    _updateState(
      state.copyWith(phase: VoiceLoopPhase.listening, transcriptPreview: ''),
    );

    String? description;
    final completer = Completer<String?>();

    // Cancel existing subscription temporarily.
    await _recognitionSubscription?.cancel();

    try {
      final stream = _sttService.startListening();
      Timer? descriptionTimer;

      _recognitionSubscription = stream.listen(
        (result) {
          _updateState(state.copyWith(transcriptPreview: result.text));

          // Reset the silence timer on each partial result.
          descriptionTimer?.cancel();
          descriptionTimer = Timer(const Duration(seconds: 5), () {
            if (!completer.isCompleted) {
              completer.complete(null); // Timeout → skip.
            }
          });

          if (result.isFinal) {
            descriptionTimer?.cancel();
            if (!completer.isCompleted) {
              description = result.text;
              completer.complete(result.text);
            }
          }
        },
        onError: (error) {
          descriptionTimer?.cancel();
          if (!completer.isCompleted) {
            completer.complete(null);
          }
        },
      );

      // Start the initial silence timeout.
      descriptionTimer = Timer(const Duration(seconds: 5), () {
        if (!completer.isCompleted) {
          completer.complete(null);
        }
      });

      description = await completer.future;
    } on Exception catch (e) {
      if (kDebugMode) {
        debugPrint('Photo description capture failed: $e');
      }
    } finally {
      await _stopListening();
    }

    // Resume previous state.
    if (wasInContinuousMode &&
        previousPhase != VoiceLoopPhase.idle &&
        state.phase != VoiceLoopPhase.idle) {
      await _startListening();
    } else {
      _updateState(state.copyWith(phase: previousPhase));
    }

    return description;
  }

  /// Speak extracted calendar event details and capture verbal confirmation.
  ///
  /// Called when a calendar/reminder intent is detected during voice mode.
  /// Reads the extracted event aloud, then listens for yes/no.
  ///
  /// Returns true if the user confirmed, false if dismissed or timed out.
  Future<bool> confirmCalendarEvent(ExtractedEvent event) async {
    if (!_sttService.isInitialized) return false;

    final wasInContinuousMode = state.isContinuousMode;
    final previousPhase = state.phase;

    // Pause normal listening if active.
    if (_sttService.isListening) {
      await _stopListening();
    }
    _silenceTimer?.cancel();

    // Build the confirmation prompt.
    final timeStr = _formatTimeForSpeech(event.startTime);
    final prompt = "Add '${event.title}' $timeStr to your calendar?";

    // Speak the prompt.
    _updateState(state.copyWith(phase: VoiceLoopPhase.speaking));
    await _speak(prompt);

    if (state.phase != VoiceLoopPhase.speaking) return false;

    // Listen for yes/no with a timeout.
    _updateState(
      state.copyWith(phase: VoiceLoopPhase.listening, transcriptPreview: ''),
    );

    String? response;
    final completer = Completer<String?>();
    await _recognitionSubscription?.cancel();

    try {
      final stream = _sttService.startListening();
      Timer? responseTimer;

      _recognitionSubscription = stream.listen(
        (result) {
          _updateState(state.copyWith(transcriptPreview: result.text));
          responseTimer?.cancel();
          responseTimer = Timer(const Duration(seconds: 5), () {
            if (!completer.isCompleted) completer.complete(null);
          });

          if (result.isFinal) {
            responseTimer?.cancel();
            if (!completer.isCompleted) completer.complete(result.text);
          }
        },
        onError: (error) {
          responseTimer?.cancel();
          if (!completer.isCompleted) completer.complete(null);
        },
      );

      responseTimer = Timer(const Duration(seconds: 8), () {
        if (!completer.isCompleted) completer.complete(null);
      });

      response = await completer.future;
    } on Exception catch (e) {
      if (kDebugMode) {
        debugPrint('Calendar confirmation capture failed: $e');
      }
    } finally {
      await _stopListening();
    }

    // Process the response.
    final confirmed = response != null && _isAffirmative(response);

    if (confirmed) {
      _updateState(state.copyWith(phase: VoiceLoopPhase.speaking));
      await _speak("Adding it to your calendar.");
      if (onConfirmCalendarEvent != null) {
        await onConfirmCalendarEvent!();
      }
    } else {
      _updateState(state.copyWith(phase: VoiceLoopPhase.speaking));
      // Distinct feedback for timeout (silence) vs active decline.
      final feedback = response == null
          ? "Okay, I'll leave that for now."
          : "Okay, I won't add that.";
      await _speak(feedback);
      if (onDismissCalendarEvent != null) {
        await onDismissCalendarEvent!();
      }
    }

    // Resume previous state.
    if (wasInContinuousMode &&
        previousPhase != VoiceLoopPhase.idle &&
        state.phase != VoiceLoopPhase.idle) {
      await _startListening();
    } else {
      _updateState(state.copyWith(phase: previousPhase));
    }

    return confirmed;
  }

  /// Speak a deferral message when Google Calendar is not connected.
  ///
  /// Called when a calendar intent is detected in voice mode but the user
  /// is not signed in to Google. The event is saved locally and the user
  /// is informed they can connect after the session (ADR-0020 §8).
  Future<void> speakDeferral() async {
    final wasInContinuousMode = state.isContinuousMode;
    final previousPhase = state.phase;

    // Pause normal listening if active.
    if (_sttService.isListening) {
      await _stopListening();
    }
    _silenceTimer?.cancel();

    _updateState(state.copyWith(phase: VoiceLoopPhase.speaking));
    await _speak(
      "I'd need to connect to your Google Calendar first. "
      "I'll remind you when we're done.",
    );

    // Resume previous state.
    if (wasInContinuousMode &&
        previousPhase != VoiceLoopPhase.idle &&
        state.phase != VoiceLoopPhase.idle) {
      await _startListening();
    } else {
      _updateState(state.copyWith(phase: previousPhase));
    }
  }

  /// Format a DateTime for spoken output.
  static String _formatTimeForSpeech(DateTime dt) {
    final local = dt.toLocal();
    final weekdays = [
      'Monday',
      'Tuesday',
      'Wednesday',
      'Thursday',
      'Friday',
      'Saturday',
      'Sunday',
    ];
    final dayName = weekdays[local.weekday - 1];
    final hour = local.hour > 12
        ? local.hour - 12
        : local.hour == 0
        ? 12
        : local.hour;
    final amPm = local.hour >= 12 ? 'PM' : 'AM';
    final minute = local.minute > 0
        ? ':${local.minute.toString().padLeft(2, '0')}'
        : '';
    return 'on $dayName at $hour$minute $amPm';
  }

  /// Clean up all resources.
  void dispose() {
    _silenceTimer?.cancel();
    _undoTimer?.cancel();
    _confirmationTimer?.cancel();
    _recognitionSubscription?.cancel();
    _audioFocusSubscription?.cancel();
    _resetConfirmationState();
    stateNotifier.dispose();
  }

  // ===========================================================================
  // Internal — Listening
  // ===========================================================================

  /// Transition to listening and start STT with silence timer.
  Future<void> _startListening() async {
    // Ensure TTS player is fully stopped to release its audio session
    // before starting STT. Without this, just_audio keeps reacting to
    // audio focus events which fights with speech_to_text for the mic.
    if (_ttsInitialized && _ttsService.isSpeaking) {
      await _ttsService.stop();
    }

    _updateState(
      state.copyWith(phase: VoiceLoopPhase.listening, transcriptPreview: ''),
    );
    await _startListeningRaw();
    _startSilenceTimer();
  }

  /// Start STT stream without state change (used by interrupt/resume too).
  Future<void> _startListeningRaw() async {
    if (_sttService.isListening) return;

    try {
      final stream = _sttService.startListening();
      _recognitionSubscription = stream.listen(
        _onSpeechResult,
        onError: _onSttError,
      );
    } on Exception catch (e) {
      _onSttError(e);
    }
  }

  /// Stop STT stream.
  Future<void> _stopListening() async {
    _silenceTimer?.cancel();
    await _recognitionSubscription?.cancel();
    _recognitionSubscription = null;

    if (_sttService.isListening) {
      await _sttService.stopListening();
    }
  }

  /// Start the silence timer. Resets on each partial result.
  void _startSilenceTimer() {
    _silenceTimer?.cancel();
    _silenceTimer = Timer(
      Duration(seconds: _silenceTimeoutSeconds),
      _onSilenceTimeout,
    );
  }

  // ===========================================================================
  // Internal — Speech result handling
  // ===========================================================================

  /// Handle incoming speech results.
  void _onSpeechResult(SpeechResult result) {
    // Reset silence timer on any speech activity.
    _startSilenceTimer();

    // Update transcript preview.
    _updateState(state.copyWith(transcriptPreview: result.text));

    if (result.isFinal) {
      final text = result.text.trim();
      if (text.isNotEmpty) {
        _processFinalResult(text);
      }
    }
  }

  /// Process a final speech result — check for commands, then send.
  Future<void> _processFinalResult(String text) async {
    _silenceTimer?.cancel();

    // Stop listening during processing.
    await _stopListening();

    // Check for verbal confirmation response.
    if (_awaitingConfirmation) {
      await _handleConfirmationResponse(text);
      return;
    }

    // Check for voice commands.
    final commandResult = _commandClassifier.classify(text);

    if (commandResult.command != VoiceCommand.none) {
      await _handleVoiceCommand(commandResult, text);
      return;
    }

    // Normal message — send to session.
    if (state.isContinuousMode) {
      _updateState(
        state.copyWith(phase: VoiceLoopPhase.processing, transcriptPreview: ''),
      );
    } else {
      // Push-to-talk: return to idle after capturing text.
      await _audioFocusService.abandonFocus();
      _updateState(
        state.copyWith(phase: VoiceLoopPhase.idle, transcriptPreview: ''),
      );
    }

    // Fire the send callback. The UI is responsible for feeding the
    // response back via onAssistantMessage().
    if (onSendMessage != null) {
      try {
        await onSendMessage!(text, inputMethod: 'VOICE');
      } on Exception catch (e) {
        debugPrint('[VoiceOrchestrator] sendMessage error: $e');
        if (state.isContinuousMode) {
          await _handleError(VoiceRecoveryMessages.processingError);
        }
      }
    }
  }

  // ===========================================================================
  // Internal — Voice commands
  // ===========================================================================

  /// Handle a detected voice command.
  Future<void> _handleVoiceCommand(
    VoiceCommandResult result,
    String originalText,
  ) async {
    switch (result.command) {
      case VoiceCommand.endSession:
        if (result.confidence >= _highConfidenceThreshold) {
          await _executeEndSession();
        } else {
          await _requestConfirmation(
            VoiceCommand.endSession,
            VoiceRecoveryMessages.endSessionConfirmPrompt,
          );
        }

      case VoiceCommand.discard:
        // Discard always requires verbal confirmation regardless of confidence.
        await _requestConfirmation(
          VoiceCommand.discard,
          VoiceRecoveryMessages.verbalDiscardConfirm,
        );

      case VoiceCommand.undo:
        if (result.confidence >= _highConfidenceThreshold) {
          await _executeUndo();
        } else {
          await _requestConfirmation(
            VoiceCommand.undo,
            'Did you want to reopen the session? Say yes or no.',
          );
        }

      case VoiceCommand.none:
        break; // Should not reach here.
    }
  }

  /// Request verbal confirmation for a command.
  Future<void> _requestConfirmation(VoiceCommand command, String prompt) async {
    _awaitingConfirmation = true;
    _pendingCommand = command;

    // Start a bounded confirmation timeout to prevent ambient audio spoofing.
    _confirmationTimer?.cancel();
    _confirmationTimer = Timer(
      const Duration(seconds: _confirmationTimeoutSeconds),
      _onConfirmationTimeout,
    );

    _updateState(state.copyWith(phase: VoiceLoopPhase.speaking));
    await _speak(prompt);

    // Resume listening for the yes/no response.
    if (state.phase == VoiceLoopPhase.speaking) {
      await _startListening();
    }
  }

  /// Handle confirmation timeout — cancel the pending command.
  void _onConfirmationTimeout() {
    if (!_awaitingConfirmation) return;
    _resetConfirmationState();

    // Resume listening if in continuous mode, otherwise go idle.
    if (state.isContinuousMode) {
      _startListening();
    } else {
      _updateState(state.copyWith(phase: VoiceLoopPhase.idle));
    }
  }

  /// Reset confirmation-related state.
  void _resetConfirmationState() {
    _awaitingConfirmation = false;
    _pendingCommand = null;
    _confirmationTimer?.cancel();
  }

  /// Handle a yes/no response to a confirmation prompt.
  Future<void> _handleConfirmationResponse(String text) async {
    final command = _pendingCommand;
    _resetConfirmationState();

    final isYes = _isAffirmative(text);

    if (!isYes) {
      // User declined — resume listening.
      _updateState(state.copyWith(phase: VoiceLoopPhase.speaking));
      await _speak(VoiceRecoveryMessages.confirmationCancelled);
      if (state.isContinuousMode && state.phase == VoiceLoopPhase.speaking) {
        await _startListening();
      } else {
        _updateState(state.copyWith(phase: VoiceLoopPhase.idle));
      }
      return;
    }

    // User confirmed — execute the command.
    switch (command) {
      case VoiceCommand.endSession:
        await _executeEndSession();
      case VoiceCommand.discard:
        await _executeDiscard();
      case VoiceCommand.undo:
        await _executeUndo();
      case VoiceCommand.none:
      case null:
        // Resume listening.
        if (state.isContinuousMode) {
          await _startListening();
        }
    }
  }

  /// Execute end session command.
  Future<void> _executeEndSession() async {
    _updateState(state.copyWith(phase: VoiceLoopPhase.speaking));
    await _speak(VoiceRecoveryMessages.sessionEndConfirm);

    // Phase guard: abort if interrupted (e.g., stop() called during TTS).
    if (state.phase != VoiceLoopPhase.speaking) return;

    if (onEndSession != null) {
      try {
        _lastClosedSessionId = currentSessionId;
        await onEndSession!();
        currentSessionId = null;
      } on Exception catch (e) {
        debugPrint('[VoiceOrchestrator] endSession error: $e');
        await _handleError(VoiceRecoveryMessages.processingError);
        return;
      }
    }

    _isOurAudioActive = false;
    await _audioFocusService.abandonFocus();
    _updateState(const VoiceOrchestratorState());
  }

  /// Execute discard command.
  Future<void> _executeDiscard() async {
    _updateState(state.copyWith(phase: VoiceLoopPhase.speaking));

    if (onDiscardSession != null) {
      try {
        await onDiscardSession!();

        // Phase guard: abort if interrupted during discard callback.
        if (state.phase != VoiceLoopPhase.speaking) return;

        await _speak(VoiceRecoveryMessages.discardComplete);
      } on Exception catch (e) {
        debugPrint('[VoiceOrchestrator] discardSession error: $e');
        await _handleError(VoiceRecoveryMessages.processingError);
        return;
      }
    }

    await _audioFocusService.abandonFocus();
    _updateState(const VoiceOrchestratorState());
  }

  /// Execute undo command.
  Future<void> _executeUndo() async {
    final sessionId = _lastClosedSessionId;
    if (sessionId == null) {
      _updateState(state.copyWith(phase: VoiceLoopPhase.speaking));
      await _speak(VoiceRecoveryMessages.undoExpired);
      if (state.isContinuousMode) {
        await _startListening();
      } else {
        _updateState(state.copyWith(phase: VoiceLoopPhase.idle));
      }
      return;
    }

    if (onResumeSession != null) {
      try {
        final resumed = await onResumeSession!(sessionId);
        if (resumed != null) {
          _lastClosedSessionId = null;
          _undoTimer?.cancel();

          _updateState(state.copyWith(phase: VoiceLoopPhase.speaking));
          await _speak(VoiceRecoveryMessages.undoSuccess);

          if (state.isContinuousMode &&
              state.phase == VoiceLoopPhase.speaking) {
            await _startListening();
          }
          return;
        }
      } on Exception catch (e) {
        debugPrint('[VoiceOrchestrator] resumeSession error: $e');
      }
    }

    // Undo failed — inform user.
    _updateState(state.copyWith(phase: VoiceLoopPhase.speaking));
    await _speak(VoiceRecoveryMessages.undoExpired);
    if (state.isContinuousMode) {
      await _startListening();
    } else {
      _updateState(state.copyWith(phase: VoiceLoopPhase.idle));
    }
  }

  /// Check if text is an affirmative response.
  static bool _isAffirmative(String text) {
    final cleaned = text.trim().toLowerCase().replaceAll(RegExp(r'[.!?,]'), '');
    return RegExp(
      r'^(yes|yeah|yep|yup|sure|ok|okay|confirm|do it|go ahead|affirmative|correct|right)$',
    ).hasMatch(cleaned);
  }

  // ===========================================================================
  // Internal — Error recovery
  // ===========================================================================

  /// Handle STT stream errors.
  void _onSttError(Object error) {
    debugPrint('[VoiceOrchestrator] STT error: $error');
    _handleError(VoiceRecoveryMessages.sttFailure);
  }

  /// Handle silence timeout (no final result within timeout period).
  Future<void> _onSilenceTimeout() async {
    if (state.phase != VoiceLoopPhase.listening) return;

    if (!state.isContinuousMode) {
      // Push-to-talk: just stop.
      await stopPushToTalk();
      return;
    }

    // Continuous mode: announce and restart listening.
    await _stopListening();
    _updateState(state.copyWith(phase: VoiceLoopPhase.speaking));
    await _speak(VoiceRecoveryMessages.sttEmpty);
    if (state.phase == VoiceLoopPhase.speaking && state.isContinuousMode) {
      await _startListening();
    }
  }

  /// Handle an error by speaking a recovery message.
  Future<void> _handleError(String message) async {
    _silenceTimer?.cancel();

    if (_sttService.isListening) {
      await _stopListening();
    }

    _updateState(
      state.copyWith(phase: VoiceLoopPhase.error, errorMessage: message),
    );

    // Speak the error message.
    try {
      await _ensureTtsInitialized();
      if (_ttsService.isSpeaking) {
        await _ttsService.stop();
      }
      await _ttsService.speak(message);
    } on Exception catch (e) {
      debugPrint('[VoiceOrchestrator] TTS error during recovery: $e');
    }

    // Transition to idle after error announcement.
    await _audioFocusService.abandonFocus();
    _updateState(
      state.copyWith(phase: VoiceLoopPhase.idle, isContinuousMode: false),
    );
  }

  // ===========================================================================
  // Internal — Audio focus
  // ===========================================================================

  /// Handle audio focus change events from the platform.
  void _onAudioFocusChanged(AudioFocusEvent event) {
    switch (event) {
      case AudioFocusEvent.loss:
      case AudioFocusEvent.lossTransient:
        // Ignore focus loss triggered by our own recording/TTS.
        // The `record` package requests its own audio focus when it starts,
        // which fires a loss event on our separate listener.
        if (!_isOurAudioActive) {
          pause();
        }
      case AudioFocusEvent.gain:
        if (state.phase == VoiceLoopPhase.paused) {
          resume();
        }
      case AudioFocusEvent.lossTransientCanDuck:
        // Continue STT, but TTS should lower volume (handled by system).
        break;
    }
  }

  // ===========================================================================
  // Internal — TTS helpers
  // ===========================================================================

  /// Ensure TTS is initialized before speaking.
  Future<void> _ensureTtsInitialized() async {
    if (!_ttsInitialized) {
      await _ttsService.initialize();
      _ttsInitialized = true;
    }
  }

  /// Speak text and wait for completion.
  Future<void> _speak(String text) async {
    try {
      await _ensureTtsInitialized();
      if (_ttsService.isSpeaking) {
        await _ttsService.stop();
      }
      await _ttsService.speak(text);
    } on Exception catch (e) {
      debugPrint('[VoiceOrchestrator] TTS error: $e');
    }
  }

  /// Speak text without blocking (fire-and-forget for push-to-talk TTS).
  Future<void> _speakNonBlocking(String text) async {
    try {
      await _ensureTtsInitialized();
      if (_ttsService.isSpeaking) {
        await _ttsService.stop();
      }
      // Don't await — let it play in the background.
      // Use .catchError to prevent unhandled async exceptions in release.
      unawaited(
        _ttsService
            .speak(text)
            .catchError(
              (Object e) =>
                  debugPrint('[VoiceOrchestrator] TTS async error: $e'),
            ),
      );
    } on Exception catch (e) {
      debugPrint('[VoiceOrchestrator] TTS error: $e');
    }
  }

  /// Speak text in sentences for reduced perceived latency.
  ///
  /// Splits the response into sentences and speaks the first one immediately.
  /// The remaining sentences are queued and spoken sequentially.
  Future<void> _speakInSentences(String text) async {
    final sentences = splitIntoSentences(text);
    if (sentences.isEmpty) return;

    for (final sentence in sentences) {
      // Check if we've been interrupted or paused.
      if (state.phase != VoiceLoopPhase.speaking) return;

      try {
        await _ensureTtsInitialized();
        if (_ttsService.isSpeaking) {
          await _ttsService.stop();
        }
        await _ttsService.speak(sentence);
      } on Exception catch (e) {
        debugPrint('[VoiceOrchestrator] TTS sentence error: $e');
        return;
      }
    }
  }

  /// Split text into sentences for streaming TTS.
  ///
  /// Uses sentence-ending punctuation as split points. Keeps the
  /// punctuation with the sentence. Filters out empty segments.
  @visibleForTesting
  static List<String> splitIntoSentences(String text) {
    // Split on sentence boundaries but keep the delimiter with the sentence.
    final segments = text.split(RegExp(r'(?<=[.!?])\s+'));
    return segments.map((s) => s.trim()).where((s) => s.isNotEmpty).toList();
  }

  // ===========================================================================
  // Internal — State management
  // ===========================================================================

  void _updateState(VoiceOrchestratorState newState) {
    stateNotifier.value = newState;
  }
}
