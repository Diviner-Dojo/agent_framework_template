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
import 'package:just_audio/just_audio.dart';

import 'audio_focus_service.dart';
import 'event_extraction_service.dart';
import 'task_extraction_service.dart';
import 'speech_recognition_service.dart';
import 'speech_to_text_stt_service.dart' show SttTimeoutEscalation;
import 'text_to_speech_service.dart';
import 'voice_command_classifier.dart';
import '../constants/voice_recovery_messages.dart';
import '../utils/reusable_completer.dart';

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

/// Classification of voice session errors for typed error handling.
///
/// Each kind maps to a specific failure domain so the UI can display
/// contextually appropriate messages and recovery actions.
enum VoiceSessionErrorKind {
  /// Speech-to-text engine failed (microphone, recognition).
  sttFailure,

  /// Text-to-speech engine failed (audio output).
  ttsFailure,

  /// LLM processing or message sending failed.
  processingFailure,

  /// Audio focus was lost to another app.
  audioFocusLoss,
}

/// A typed error emitted by the voice orchestrator.
///
/// Carries both a machine-readable [kind] for UI branching and a
/// human-readable [message] for display.
class VoiceSessionError {
  /// The error classification.
  final VoiceSessionErrorKind kind;

  /// Human-readable error message (suitable for display or TTS).
  final String message;

  /// Creates a typed voice session error.
  const VoiceSessionError({required this.kind, required this.message});
}

/// Immutable state emitted by the voice orchestrator.
class VoiceOrchestratorState {
  /// Current phase of the voice loop.
  final VoiceLoopPhase phase;

  /// Real-time STT text shown on screen during listening.
  final String transcriptPreview;

  /// Typed error when in error phase.
  final VoiceSessionError? error;

  /// True when in continuous mode (auto-loop), false for push-to-talk.
  final bool isContinuousMode;

  const VoiceOrchestratorState({
    this.phase = VoiceLoopPhase.idle,
    this.transcriptPreview = '',
    this.error,
    this.isContinuousMode = false,
  });

  VoiceOrchestratorState copyWith({
    VoiceLoopPhase? phase,
    String? transcriptPreview,
    VoiceSessionError? error,
    bool? isContinuousMode,
    bool clearError = false,
  }) {
    return VoiceOrchestratorState(
      phase: phase ?? this.phase,
      transcriptPreview: transcriptPreview ?? this.transcriptPreview,
      error: clearError ? null : (error ?? this.error),
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

  /// Callback for confirming a task (verbal "yes").
  SessionActionCallback? onConfirmTask;

  /// Callback for dismissing a task (verbal "no").
  SessionActionCallback? onDismissTask;

  /// The current orchestrator state.
  final ValueNotifier<VoiceOrchestratorState> stateNotifier = ValueNotifier(
    const VoiceOrchestratorState(),
  );

  /// Whether the orchestrator has been disposed.
  bool _disposed = false;

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

  /// Whether the user is actively speaking (interim results received).
  ///
  /// Gates silence timer start — the timer should not run concurrently
  /// with active speech. Set true on first interim result, false on
  /// isFinal or STT stop. See: SPEC-20260228 Task 1.
  bool _userIsSpeaking = false;

  /// Pending commit timer for confidence-weighted delay (Task 3).
  Timer? _commitDelayTimer;

  /// Audio player for the non-verbal thinking sound (Task 4, R14).
  AudioPlayer? _thinkingPlayer;

  /// Timer for turn-completeness re-prompt (Task 5, R23/R24).
  Timer? _turnCompletionTimer;

  /// Last closed session ID for undo support.
  String? _lastClosedSessionId;

  /// Whether TTS has been initialized.
  bool _ttsInitialized = false;

  /// Whether we are actively using audio (STT/TTS).
  /// Used to ignore audio focus loss events triggered by our own recording.
  bool _isOurAudioActive = false;

  /// Confidence threshold for direct command execution.
  static const _highConfidenceThreshold = 0.8;

  // Turn-completeness markers (Task 5, R21).
  static const _markerComplete = '✓';
  static const _markerIncomplete = '○';
  static const _markerDeliberating = '◐';

  /// Silence timeout before re-prompting (seconds).
  final int _silenceTimeoutSeconds;

  /// Whether the thinking sound is enabled (disable in tests where
  /// AudioPlayer platform bindings are unavailable).
  final bool _enableThinkingSound;

  /// Confirmation timeout (seconds) — prevents ambient audio spoofing.
  static const _confirmationTimeoutSeconds = 10;

  /// Delay after TTS playback before starting STT (milliseconds).
  ///
  /// Gives the OS time to release the audio session from just_audio before
  /// speech_to_text acquires the microphone. Set to 0 in tests to avoid
  /// timing sensitivity.
  final Duration _ttsReleaseDelay;

  VoiceSessionOrchestrator({
    required SpeechRecognitionService sttService,
    required TextToSpeechService ttsService,
    required AudioFocusService audioFocusService,
    int silenceTimeoutSeconds = 15,
    bool enableThinkingSound = true,
    Duration ttsReleaseDelay = const Duration(milliseconds: 150),
  }) : _sttService = sttService,
       _ttsService = ttsService,
       _silenceTimeoutSeconds = silenceTimeoutSeconds,
       _enableThinkingSound = enableThinkingSound,
       _ttsReleaseDelay = ttsReleaseDelay,
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
    _commitDelayTimer?.cancel();
    _turnCompletionTimer?.cancel();
    _stopThinkingSound();

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
  ///
  /// When [silent] is true, skips the welcome-back TTS and goes directly
  /// to listening. Used when resuming after a cancelled photo/video capture
  /// where speaking a message would be disruptive.
  Future<void> resume({bool silent = false}) async {
    if (state.phase != VoiceLoopPhase.paused) return;

    final previousPhase = _phaseBeforePause ?? VoiceLoopPhase.idle;
    _phaseBeforePause = null;

    if (!state.isContinuousMode) {
      // Push-to-talk: return to idle.
      await _audioFocusService.abandonFocus();
      _updateState(state.copyWith(phase: VoiceLoopPhase.idle));
      return;
    }

    // Continuous mode: optionally speak welcome back, then resume listening.
    await _audioFocusService.requestFocus();

    if (previousPhase == VoiceLoopPhase.listening ||
        previousPhase == VoiceLoopPhase.speaking) {
      if (silent) {
        // Skip TTS — go directly to listening.
        await _startListening();
      } else {
        _updateState(state.copyWith(phase: VoiceLoopPhase.speaking));
        await _speak(VoiceRecoveryMessages.welcomeBack);
        if (state.phase == VoiceLoopPhase.speaking) {
          await _startListening();
        }
      }
    } else {
      _updateState(state.copyWith(phase: previousPhase));
    }
  }

  /// Stop the orchestrator and return to idle.
  Future<void> stop() async {
    _silenceTimer?.cancel();
    _undoTimer?.cancel();
    _commitDelayTimer?.cancel();
    _turnCompletionTimer?.cancel();
    _stopThinkingSound();
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
    // Guard: ignore messages if the orchestrator is idle or disposed.
    // This happens when endSession()'s closing summary arrives after the
    // user already pressed back and stop() was called.
    if (_disposed || state.phase == VoiceLoopPhase.idle) return;

    // Parse turn-completeness marker (Task 5, R21/R22/R28).
    final parsed = _parseTurnMarker(text);
    final marker = parsed.$1;
    final cleanText = _stripMarkdown(parsed.$2);

    if (!state.isContinuousMode) {
      // Push-to-talk: just speak the message.
      await _speakNonBlocking(cleanText);
      return;
    }

    if (state.phase == VoiceLoopPhase.processing) {
      _stopThinkingSound();

      // Handle incomplete/deliberating markers (Task 5, R23/R24).
      if (marker == _markerIncomplete) {
        _turnCompletionTimer?.cancel();
        _turnCompletionTimer = Timer(
          const Duration(seconds: 5),
          () => _promptUserToContinue(brief: true),
        );
        await _startListening();
        return;
      }
      if (marker == _markerDeliberating) {
        _turnCompletionTimer?.cancel();
        _turnCompletionTimer = Timer(
          const Duration(seconds: 10),
          () => _promptUserToContinue(brief: false),
        );
        await _startListening();
        return;
      }

      // ✓ or no marker — speak normally.
      _updateState(state.copyWith(phase: VoiceLoopPhase.speaking));
      await _speakInSentences(cleanText);

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
    final completer = ReusableCompleter<String?>();

    // Cancel existing subscription temporarily.
    await _recognitionSubscription?.cancel();

    try {
      final stream = _sttService.startListening();

      _recognitionSubscription = stream.listen(
        (result) {
          _updateState(state.copyWith(transcriptPreview: result.text));

          // Reset the silence timer on each partial result.
          completer.setTimeout(const Duration(seconds: 5), null);

          if (result.isFinal) {
            description = result.text;
            completer.complete(result.text);
          }
        },
        onError: (error) {
          completer.complete(null);
        },
      );

      // Start the initial silence timeout.
      completer.setTimeout(const Duration(seconds: 5), null);

      description = await completer.future;
    } on Exception catch (e) {
      if (kDebugMode) {
        debugPrint('Photo description capture failed: $e');
      }
    } finally {
      completer.dispose();
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
    final completer = ReusableCompleter<String?>();
    await _recognitionSubscription?.cancel();

    try {
      final stream = _sttService.startListening();

      _recognitionSubscription = stream.listen(
        (result) {
          _updateState(state.copyWith(transcriptPreview: result.text));
          completer.setTimeout(const Duration(seconds: 5), null);

          if (result.isFinal) {
            completer.complete(result.text);
          }
        },
        onError: (error) {
          completer.complete(null);
        },
      );

      completer.setTimeout(const Duration(seconds: 8), null);

      response = await completer.future;
    } on Exception catch (e) {
      if (kDebugMode) {
        debugPrint('Calendar confirmation capture failed: $e');
      }
    } finally {
      completer.dispose();
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

  /// Speak extracted task details and capture verbal confirmation.
  ///
  /// Called when a task intent is detected during voice mode.
  /// Reads the task aloud, then listens for yes/no.
  ///
  /// Returns true if the user confirmed, false if dismissed or timed out.
  Future<bool> confirmTask(ExtractedTask task) async {
    if (!_sttService.isInitialized) return false;

    final wasInContinuousMode = state.isContinuousMode;
    final previousPhase = state.phase;

    if (_sttService.isListening) {
      await _stopListening();
    }
    _silenceTimer?.cancel();

    final prompt = "Add '${task.title}' to your tasks?";

    _updateState(state.copyWith(phase: VoiceLoopPhase.speaking));
    await _speak(prompt);

    if (state.phase != VoiceLoopPhase.speaking) return false;

    _updateState(
      state.copyWith(phase: VoiceLoopPhase.listening, transcriptPreview: ''),
    );

    String? response;
    final completer = ReusableCompleter<String?>();
    await _recognitionSubscription?.cancel();

    try {
      final stream = _sttService.startListening();

      _recognitionSubscription = stream.listen(
        (result) {
          _updateState(state.copyWith(transcriptPreview: result.text));
          completer.setTimeout(const Duration(seconds: 5), null);

          if (result.isFinal) {
            completer.complete(result.text);
          }
        },
        onError: (error) {
          completer.complete(null);
        },
      );

      completer.setTimeout(const Duration(seconds: 8), null);

      response = await completer.future;
    } on Exception catch (e) {
      if (kDebugMode) {
        debugPrint('Task confirmation capture failed: $e');
      }
    } finally {
      completer.dispose();
      await _stopListening();
    }

    final confirmed = response != null && _isAffirmative(response);

    if (confirmed) {
      _updateState(state.copyWith(phase: VoiceLoopPhase.speaking));
      await _speak("Added to your tasks.");
      if (onConfirmTask != null) {
        await onConfirmTask!();
      }
    } else {
      _updateState(state.copyWith(phase: VoiceLoopPhase.speaking));
      final feedback = response == null
          ? "Okay, I'll leave that for now."
          : "Okay, I won't add that.";
      await _speak(feedback);
      if (onDismissTask != null) {
        await onDismissTask!();
      }
    }

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
    _disposed = true;
    _silenceTimer?.cancel();
    _undoTimer?.cancel();
    _confirmationTimer?.cancel();
    _commitDelayTimer?.cancel();
    _turnCompletionTimer?.cancel();
    _recognitionSubscription?.cancel();
    _audioFocusSubscription?.cancel();
    _resetConfirmationState();
    _stopThinkingSound();
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
    if (_ttsInitialized) {
      if (_ttsService.isSpeaking) {
        await _ttsService.stop();
      }
      // Brief delay to let the OS release the audio session after TTS
      // playback ends. Without this, speech_to_text may fail to acquire
      // the microphone on some Android devices because just_audio's
      // AudioPlayer hasn't fully relinquished audio focus yet.
      if (_ttsReleaseDelay > Duration.zero) {
        await Future<void>.delayed(_ttsReleaseDelay);
      }
      // Guard: if the orchestrator was stopped or disposed during the
      // delay (e.g., user navigated away), don't proceed to listening.
      if (_disposed || state.phase == VoiceLoopPhase.idle) return;
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
    _userIsSpeaking = false;
    await _recognitionSubscription?.cancel();
    _recognitionSubscription = null;

    if (_sttService.isListening) {
      await _sttService.stopListening();
    }
  }

  /// Start the silence timer. Guarded by [_userIsSpeaking] — the timer
  /// must not run while the user is actively speaking (Task 1, R2).
  void _startSilenceTimer() {
    _silenceTimer?.cancel();
    if (_userIsSpeaking) return;
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
    // Cancel any pending confidence-delay commit on new input (Task 3, R9).
    _commitDelayTimer?.cancel();
    // Cancel turn-completion re-prompt if user speaks (Task 5, R26).
    _turnCompletionTimer?.cancel();

    if (!result.isFinal && result.text.isNotEmpty) {
      // Interim result — user is speaking. Cancel the silence timer
      // immediately so it doesn't fire mid-utterance (Task 1, R1/R2).
      _userIsSpeaking = true;
      _silenceTimer?.cancel();
    }

    // Update transcript preview.
    _updateState(state.copyWith(transcriptPreview: result.text));

    if (result.isFinal) {
      _userIsSpeaking = false;
      final text = result.text.trim();
      if (text.isNotEmpty) {
        _processFinalResult(text, result.confidence);
      } else {
        // Empty final — restart silence timer for continued listening.
        _startSilenceTimer();
      }
    }
  }

  /// Compute the commit delay based on STT confidence (Task 3, R7).
  ///
  /// High-confidence results commit immediately. Low-confidence results
  /// delay to give the user time to correct or continue speaking.
  @visibleForTesting
  static Duration computeCommitDelay(double confidence) {
    if (confidence >= 0.85) return Duration.zero;
    if (confidence >= 0.65) return const Duration(milliseconds: 400);
    return const Duration(milliseconds: 1200);
  }

  /// Process a final speech result — check for commands, then send.
  ///
  /// When [confidence] is below 0.85, a timer delays the commit to allow
  /// the user to continue speaking (Task 3, R8). The timer is cancelled
  /// if new speech arrives (R9).
  Future<void> _processFinalResult(String text, double confidence) async {
    final delay = computeCommitDelay(confidence);

    if (delay > Duration.zero) {
      _commitDelayTimer?.cancel();
      _commitDelayTimer = Timer(delay, () => _commitUserTurn(text));
      return;
    }

    await _commitUserTurn(text);
  }

  /// Commit the user's turn — stop listening, classify, and send.
  Future<void> _commitUserTurn(String text) async {
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
      _startThinkingSound();
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
          await _handleError(
            const VoiceSessionError(
              kind: VoiceSessionErrorKind.processingFailure,
              message: VoiceRecoveryMessages.processingError,
            ),
          );
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
        await _handleError(
          const VoiceSessionError(
            kind: VoiceSessionErrorKind.processingFailure,
            message: VoiceRecoveryMessages.processingError,
          ),
        );
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
        await _handleError(
          const VoiceSessionError(
            kind: VoiceSessionErrorKind.processingFailure,
            message: VoiceRecoveryMessages.processingError,
          ),
        );
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

    // Escalation after 3 consecutive timeouts — speak suggestion and idle.
    if (error is SttTimeoutEscalation) {
      _handleError(
        const VoiceSessionError(
          kind: VoiceSessionErrorKind.sttFailure,
          message: VoiceRecoveryMessages.sttEscalation,
        ),
      );
      return;
    }

    _handleError(
      const VoiceSessionError(
        kind: VoiceSessionErrorKind.sttFailure,
        message: VoiceRecoveryMessages.sttFailure,
      ),
    );
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
  Future<void> _handleError(VoiceSessionError error) async {
    _silenceTimer?.cancel();

    if (_sttService.isListening) {
      await _stopListening();
    }

    _stopThinkingSound();
    _updateState(state.copyWith(phase: VoiceLoopPhase.error, error: error));

    // Speak the error message.
    try {
      await _ensureTtsInitialized();
      if (_ttsService.isSpeaking) {
        await _ttsService.stop();
      }
      await _ttsService.speak(error.message);
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
  /// `[PAUSE]` markers are rendered as 2-second silences instead of TTS.
  Future<void> _speakInSentences(String text) async {
    final sentences = splitIntoSentences(text);
    if (sentences.isEmpty) return;

    for (final sentence in sentences) {
      // Check if we've been interrupted or paused.
      if (state.phase != VoiceLoopPhase.speaking) return;

      // [PAUSE] markers become 2-second silences.
      if (sentence == '[PAUSE]') {
        await Future<void>.delayed(const Duration(seconds: 2));
        continue;
      }

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
  /// Splits on `[PAUSE]` markers first (preserved as standalone segments),
  /// then splits remaining text on sentence-ending punctuation. Keeps the
  /// punctuation with the sentence. Filters out empty segments.
  @visibleForTesting
  static List<String> splitIntoSentences(String text) {
    final result = <String>[];

    // Split on [PAUSE] first, preserving it as a standalone segment.
    final pauseParts = text.split('[PAUSE]');

    for (var i = 0; i < pauseParts.length; i++) {
      // Split non-pause parts into sentences.
      final part = pauseParts[i].trim();
      if (part.isNotEmpty) {
        final sentences = part.split(RegExp(r'(?<=[.!?])\s+'));
        result.addAll(
          sentences.map((s) => s.trim()).where((s) => s.isNotEmpty),
        );
      }

      // Add [PAUSE] between parts (not after the last one).
      if (i < pauseParts.length - 1) {
        result.add('[PAUSE]');
      }
    }

    return result;
  }

  // ===========================================================================
  // Internal — Markdown stripping (Task 2)
  // ===========================================================================

  /// Strip markdown formatting before TTS (Task 2, R4/R5).
  ///
  /// Removes bold, italic, headers, and bullet markers so TTS speaks
  /// clean prose instead of "asterisk" or "dash".
  @visibleForTesting
  static String stripMarkdown(String text) {
    var result = text;
    // Bold: **text** or __text__
    result = result.replaceAllMapped(
      RegExp(r'\*\*(.+?)\*\*'),
      (m) => m.group(1)!,
    );
    result = result.replaceAllMapped(RegExp(r'__(.+?)__'), (m) => m.group(1)!);
    // Italic: *text* or _text_ (single)
    result = result.replaceAllMapped(
      RegExp(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)'),
      (m) => m.group(1)!,
    );
    result = result.replaceAllMapped(
      RegExp(r'(?<!_)_(?!_)(.+?)(?<!_)_(?!_)'),
      (m) => m.group(1)!,
    );
    // Headers: # Header → Header
    result = result.replaceAll(RegExp(r'^#{1,6}\s+', multiLine: true), '');
    // Bullet lists: - item or * item → item
    result = result.replaceAll(RegExp(r'^\s*[-*]\s+', multiLine: true), '');
    // Numbered lists: 1. item → item
    result = result.replaceAll(RegExp(r'^\s*\d+\.\s+', multiLine: true), '');
    // Inline code: `code` → code
    result = result.replaceAllMapped(RegExp(r'`(.+?)`'), (m) => m.group(1)!);
    return result.trim();
  }

  /// Instance wrapper for [stripMarkdown].
  String _stripMarkdown(String text) => stripMarkdown(text);

  // ===========================================================================
  // Internal — Thinking sound (Task 4)
  // ===========================================================================

  /// Start the looping thinking sound (Task 4, R15).
  void _startThinkingSound() {
    if (!_enableThinkingSound) return;
    _stopThinkingSound();
    try {
      _thinkingPlayer = AudioPlayer();
      _thinkingPlayer!
          .setAsset('assets/audio/thinking_chime.mp3')
          .then((_) => _thinkingPlayer?.setLoopMode(LoopMode.one))
          .then((_) => _thinkingPlayer?.setVolume(0.4))
          .then((_) => _thinkingPlayer?.play())
          .catchError((Object e) {
            debugPrint('[VoiceOrchestrator] thinking sound error: $e');
          });
    } on Exception catch (e) {
      debugPrint('[VoiceOrchestrator] thinking sound init error: $e');
    }
  }

  /// Stop and dispose the thinking sound player (Task 4, R16).
  void _stopThinkingSound() {
    try {
      _thinkingPlayer?.stop();
      _thinkingPlayer?.dispose();
    } on Exception catch (e) {
      debugPrint('[VoiceOrchestrator] thinking sound cleanup error: $e');
    }
    _thinkingPlayer = null;
  }

  // ===========================================================================
  // Internal — Turn-completeness markers (Task 5)
  // ===========================================================================

  /// Parse the turn-completeness marker from the LLM response (Task 5, R21).
  ///
  /// Returns a record of (marker, stripped_text). If no marker is found,
  /// returns [_markerComplete] as the default (R28 graceful fallback).
  @visibleForTesting
  static (String, String) parseTurnMarker(String text) {
    final trimmed = text.trimLeft();
    for (final marker in [
      _markerComplete,
      _markerIncomplete,
      _markerDeliberating,
    ]) {
      if (trimmed.startsWith(marker)) {
        return (marker, trimmed.substring(marker.length).trimLeft());
      }
    }
    // No marker found — treat as complete (R28).
    return (_markerComplete, text);
  }

  /// Instance wrapper for [parseTurnMarker].
  (String, String) _parseTurnMarker(String text) => parseTurnMarker(text);

  /// Gently prompt the user to continue after an incomplete turn (Task 5, R25).
  Future<void> _promptUserToContinue({required bool brief}) async {
    _turnCompletionTimer = null;
    _updateState(state.copyWith(phase: VoiceLoopPhase.speaking));
    if (brief) {
      await _speak(VoiceRecoveryMessages.turnIncompleteBrief);
    } else {
      await _speak(VoiceRecoveryMessages.turnIncompletePatient);
    }
    if (state.phase == VoiceLoopPhase.speaking && state.isContinuousMode) {
      await _startListening();
    }
  }

  // ===========================================================================
  // Internal — State management
  // ===========================================================================

  void _updateState(VoiceOrchestratorState newState) {
    if (_disposed) return;
    stateNotifier.value = newState;
  }
}
