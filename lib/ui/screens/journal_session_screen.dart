// ===========================================================================
// file: lib/ui/screens/journal_session_screen.dart
// purpose: Active journaling conversation screen.
//
// This is where the conversation happens. It shows:
//   - A scrollable list of chat bubbles (assistant + user messages)
//   - A text input field at the bottom with a send button
//   - An overflow menu in the app bar (End Session / Discard)
//
// The screen auto-scrolls to the latest message when new messages arrive.
// On first load, the session has already been created by SessionNotifier
// (the greeting message is already in the database).
//
// UX features:
//   - PopScope intercepts back navigation with a confirmation dialog
//   - Escalating thinking indicator provides progress feedback
//   - Closing summary stays visible until user taps "Done"
//   - Auto-discard SnackBar when empty session is ended
//
// Phase 7B changes:
//   - Voice state delegated to VoiceSessionOrchestrator
//   - WidgetsBindingObserver for lifecycle management (auto-save)
//   - Continuous mode with phase indicator and interrupt button
//   - Transcript preview during listening
// ===========================================================================

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:record/record.dart';

import 'package:uuid/uuid.dart';

import '../../providers/calendar_providers.dart';
import '../../providers/database_provider.dart';
import '../../providers/photo_providers.dart';
import '../../providers/session_providers.dart';
import '../../providers/video_providers.dart';
import '../../providers/voice_providers.dart';
import '../../services/model_download_service.dart';
import '../../services/photo_service.dart';
import '../../constants/voice_recovery_messages.dart';
import '../../services/voice_session_orchestrator.dart';
import '../widgets/calendar_event_card.dart';
import '../widgets/chat_bubble.dart';
import '../widgets/model_download_dialog.dart';
import '../widgets/photo_capture_sheet.dart';
import '../widgets/photo_preview_dialog.dart';
import '../widgets/photo_viewer.dart';
import '../widgets/video_player_widget.dart';

/// The active journal conversation screen.
class JournalSessionScreen extends ConsumerStatefulWidget {
  const JournalSessionScreen({super.key});

  @override
  ConsumerState<JournalSessionScreen> createState() =>
      _JournalSessionScreenState();
}

class _JournalSessionScreenState extends ConsumerState<JournalSessionScreen>
    with WidgetsBindingObserver {
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  int _lastMessageCount = 0;

  /// Tracks the last assistant message ID to avoid re-speaking.
  String _previousTranscriptId = '';

  /// Whether STT model is being initialized (5-8s loading).
  bool _isInitializingStt = false;

  /// Whether the orchestrator callbacks have been wired.
  bool _orchestratorWired = false;

  /// Whether continuous mode has been auto-started for this session.
  bool _continuousModeAutoStarted = false;

  /// Whether the native camera/gallery picker is open.
  ///
  /// Guards [_autoSaveIfNeeded] so the lifecycle pause from the native
  /// intent does not end the session mid-capture.
  bool _isCapturingMedia = false;

  /// Timer for the 800ms delay before calling stopPushToTalk().
  ///
  /// Users trail off at the end of speech; immediate stop on button release
  /// discards the last words. The delay gives STT time to capture trailing
  /// audio. Double-tap cancels the timer for immediate stop.
  Timer? _pttStopTimer;

  /// When true, the text field is active instead of the mic button.
  /// Defaults to false (voice input) when voice mode is enabled.
  bool _isTextInputMode = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    // Rebuild when text changes so mic/send button toggles correctly.
    _textController.addListener(() {
      if (mounted) setState(() {});
    });

    // Wire orchestrator callbacks after the first frame.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _wireOrchestrator();
    });
  }

  @override
  void dispose() {
    _pttStopTimer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    _textController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState lifecycleState) {
    final orchestrator = ref.read(voiceOrchestratorProvider);

    switch (lifecycleState) {
      case AppLifecycleState.paused:
      case AppLifecycleState.detached:
        // Pause voice and optionally auto-save.
        orchestrator.pause();
        _autoSaveIfNeeded();
      case AppLifecycleState.resumed:
        orchestrator.resume();
      case AppLifecycleState.inactive:
      case AppLifecycleState.hidden:
        break;
    }
  }

  /// Wire the orchestrator's callbacks to SessionNotifier methods.
  void _wireOrchestrator() {
    if (_orchestratorWired) return;
    _orchestratorWired = true;

    final orchestrator = ref.read(voiceOrchestratorProvider);
    final sessionNotifier = ref.read(sessionNotifierProvider.notifier);

    orchestrator.onSendMessage = (text, {String inputMethod = 'TEXT'}) async {
      await sessionNotifier.sendMessage(text, inputMethod: inputMethod);
      return null; // Response comes via message stream.
    };
    orchestrator.onEndSession = () async {
      await sessionNotifier.endSession();
      // Auto-dismiss after voice-initiated end session.
      if (mounted) _dismissAndPop();
    };
    orchestrator.onDiscardSession = () => sessionNotifier.discardSession();
    orchestrator.onResumeSession = (sessionId) =>
        sessionNotifier.resumeSession(sessionId);
    orchestrator.onConfirmCalendarEvent = () =>
        sessionNotifier.confirmCalendarEvent();
    orchestrator.onDismissCalendarEvent = () {
      sessionNotifier.dismissCalendarEvent();
      sessionNotifier.dismissReminder();
      return Future.value();
    };

    // Keep orchestrator's session ID in sync for undo support.
    final sessionId = ref.read(sessionNotifierProvider).activeSessionId;
    orchestrator.currentSessionId = sessionId;

    // Cancel PTT stop timer when voice state leaves listening.
    orchestrator.stateNotifier.addListener(() {
      if (orchestrator.state.phase != VoiceLoopPhase.listening) {
        _pttStopTimer?.cancel();
      }
    });
  }

  /// Start continuous mode with the greeting message.
  Future<void> _startContinuousModeWithGreeting(String greeting) async {
    final orchestrator = ref.read(voiceOrchestratorProvider);
    if (orchestrator.state.phase != VoiceLoopPhase.idle) return;

    // Ensure STT is initialized before starting continuous mode.
    final sttReady = await _ensureSttReady();
    if (!sttReady || !mounted) return;

    await orchestrator.startContinuousMode(greeting);
  }

  /// Auto-save session on backgrounding if enabled.
  ///
  /// Skipped when [_isCapturingMedia] is true — the native camera/gallery
  /// intent triggers [AppLifecycleState.paused] but the session should
  /// remain active.
  void _autoSaveIfNeeded() {
    if (_isCapturingMedia) return;

    final autoSave = ref.read(autoSaveOnExitProvider);
    final sessionState = ref.read(sessionNotifierProvider);

    if (autoSave &&
        sessionState.activeSessionId != null &&
        !sessionState.isSessionEnding) {
      ref.read(sessionNotifierProvider.notifier).endSession();
    }
  }

  @override
  Widget build(BuildContext context) {
    final sessionState = ref.watch(sessionNotifierProvider);
    final messagesAsync = ref.watch(activeSessionMessagesProvider);
    final voiceEnabled = ref.watch(voiceModeEnabledProvider);
    final sessionId = sessionState.activeSessionId;
    final photosAsync = sessionId != null
        ? ref.watch(sessionPhotosProvider(sessionId))
        : const AsyncValue<List<dynamic>>.data([]);
    final videosAsync = sessionId != null
        ? ref.watch(sessionVideosProvider(sessionId))
        : const AsyncValue<List<dynamic>>.data([]);

    // Watch orchestrator state for UI rebuilds.
    final orchestrator = ref.watch(voiceOrchestratorProvider);

    // Listen for empty-session-closed signal and show SnackBar + auto-pop.
    ref.listen<bool>(wasAutoDiscardedProvider, (previous, wasDiscarded) {
      if (wasDiscarded) {
        // Reset the flag immediately so it doesn't re-trigger.
        ref.read(wasAutoDiscardedProvider.notifier).state = false;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Session closed \u2014 nothing was recorded.'),
          ),
        );
        // Auto-pop back to the list after a brief delay.
        if (mounted) {
          Navigator.of(context).pop();
        }
      }
    });

    // Listen for new assistant messages to feed to the orchestrator.
    ref.listen<AsyncValue<List<dynamic>>>(activeSessionMessagesProvider, (
      previous,
      next,
    ) {
      if (!voiceEnabled || _isTextInputMode) return;
      final messages = next.valueOrNull;
      if (messages == null || messages.isEmpty) return;
      final lastMsg = messages.last;
      // Only process new assistant messages.
      if (lastMsg.role == 'ASSISTANT') {
        final msgId = '${lastMsg.messageId}';
        if (msgId != _previousTranscriptId) {
          _previousTranscriptId = msgId;

          // Auto-start continuous mode on the first greeting message.
          if (!_continuousModeAutoStarted &&
              orchestrator.state.phase == VoiceLoopPhase.idle) {
            _continuousModeAutoStarted = true;
            _startContinuousModeWithGreeting(lastMsg.content);
            return; // Don't also call onAssistantMessage.
          }

          orchestrator.onAssistantMessage(lastMsg.content);
        }
      }
    });

    // Listen for pending calendar events during voice mode — trigger
    // verbal confirmation or deferral when extraction completes.
    ref.listen<SessionState>(sessionNotifierProvider, (previous, next) {
      if (!voiceEnabled) return;
      if (orchestrator.state.phase == VoiceLoopPhase.idle) return;

      // Only trigger when extraction just completed (transition from
      // isExtracting=true to false with a non-null extractedEvent).
      final wasExtracting = previous?.isExtracting ?? false;
      if (wasExtracting &&
          !next.isExtracting &&
          next.pendingExtractedEvent != null) {
        final isConnected = ref.read(isGoogleConnectedProvider);
        if (isConnected) {
          orchestrator.confirmCalendarEvent(next.pendingExtractedEvent!);
        } else {
          // Defer: save event locally and inform user via TTS (ADR-0020 §8).
          final notifier = ref.read(sessionNotifierProvider.notifier);
          notifier.deferCalendarEvent();
          orchestrator.speakDeferral();
        }
      }
    });

    return PopScope(
      canPop:
          sessionState.isClosingComplete ||
          sessionState.isSessionEnding ||
          sessionState.activeSessionId == null,
      onPopInvokedWithResult: (didPop, _) {
        if (didPop) {
          // Dismiss state on pop.
          if (sessionState.isClosingComplete || sessionState.isSessionEnding) {
            ref.read(sessionNotifierProvider.notifier).dismissSession();
          }
          // Stop orchestrator on navigation away.
          ref.read(voiceOrchestratorProvider).stop();
          return;
        }
        // Save and close immediately — no confirmation dialog.
        _endSessionAndPop();
      },
      child: Scaffold(
        appBar: AppBar(
          title: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Journal Entry'),
              Text(
                ref.watch(activeLayerLabelProvider),
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Theme.of(context).colorScheme.onSurface.withAlpha(153),
                ),
              ),
            ],
          ),
          leading: IconButton(
            icon: const Icon(Icons.arrow_back),
            onPressed: () {
              if (sessionState.isClosingComplete ||
                  sessionState.isSessionEnding) {
                _dismissAndPop();
              } else {
                _endSessionAndPop();
              }
            },
          ),
          actions: [
            // "Done" button — promoted to AppBar for quick 1-tap end.
            if (!sessionState.isSessionEnding &&
                sessionState.activeSessionId != null)
              TextButton(
                onPressed: _endSessionAndPop,
                child: const Text('Done'),
              ),
            // Overflow menu — only Discard (destructive = hidden).
            if (!sessionState.isSessionEnding)
              PopupMenuButton<String>(
                icon: const Icon(Icons.more_vert),
                tooltip: 'Session options',
                onSelected: (value) {
                  switch (value) {
                    case 'discard':
                      _showDiscardConfirmation();
                  }
                },
                itemBuilder: (context) => [
                  PopupMenuItem(
                    value: 'discard',
                    child: ListTile(
                      leading: Icon(
                        Icons.delete_outline,
                        color: Theme.of(context).colorScheme.error,
                      ),
                      title: Text(
                        'Discard',
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                        ),
                      ),
                      contentPadding: EdgeInsets.zero,
                    ),
                  ),
                ],
              ),
          ],
        ),
        body: Column(
          children: [
            // Message list — takes all available vertical space.
            Expanded(
              child: messagesAsync.when(
                data: (messages) {
                  // Auto-scroll only when message count changes, not on
                  // every stream emission — avoids fighting the keyboard.
                  if (messages.length != _lastMessageCount) {
                    _lastMessageCount = messages.length;
                    WidgetsBinding.instance.addPostFrameCallback((_) {
                      _scrollToBottom();
                    });
                  }
                  // Index photos by messageId for chat bubbles.
                  final photos = photosAsync.valueOrNull ?? [];
                  final photoMap = <String, dynamic>{};
                  for (final photo in photos) {
                    if (photo.messageId != null) {
                      photoMap[photo.messageId as String] = photo;
                    }
                  }
                  // Index videos by videoId for chat bubbles.
                  final videos = videosAsync.valueOrNull ?? [];
                  final videoMap = <String, dynamic>{};
                  for (final video in videos) {
                    videoMap[video.videoId as String] = video;
                  }

                  return ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.only(top: 8, bottom: 8),
                    itemCount: messages.length,
                    itemBuilder: (context, index) {
                      final msg = messages[index];
                      final photo = msg.photoId != null
                          ? photoMap[msg.messageId]
                          : null;
                      final video = msg.videoId != null
                          ? videoMap[msg.videoId as String]
                          : null;
                      return ChatBubble(
                        content: msg.content,
                        role: msg.role,
                        timestamp: msg.timestamp,
                        photoPath: photo?.localPath as String?,
                        photoCaption: photo?.description as String?,
                        onPhotoTap: photo != null
                            ? () => Navigator.of(context).push(
                                MaterialPageRoute(
                                  builder: (_) => PhotoViewer(
                                    photoPath: photo.localPath as String,
                                    caption: photo.description as String?,
                                    heroTag: 'photo-chat-${photo.localPath}',
                                  ),
                                ),
                              )
                            : null,
                        videoThumbnailPath: video?.thumbnailPath as String?,
                        videoDuration: video?.durationSeconds as int?,
                        onVideoTap: video != null
                            ? () => showVideoPlayer(
                                context: context,
                                videoPath: video.localPath as String,
                              )
                            : null,
                      );
                    },
                  );
                },
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (error, stack) => Center(child: Text('Error: $error')),
              ),
            ),

            // Calendar event confirmation card — shown when a pending
            // calendar/reminder intent is detected (ADR-0020 §7).
            if (sessionState.pendingCalendarEvent != null ||
                sessionState.pendingReminder != null)
              _buildCalendarEventCard(sessionState),

            // Typing indicator — shown while waiting for agent response.
            if (sessionState.isWaitingForAgent && !sessionState.isSessionEnding)
              const _ThinkingIndicator(),

            // Text input field — hidden when session is ending.
            if (!sessionState.isSessionEnding)
              _buildInputField(context, voiceEnabled, orchestrator),
          ],
        ),
      ),
    );
  }

  /// Build the inline calendar event confirmation card.
  Widget _buildCalendarEventCard(SessionState sessionState) {
    final isReminder = sessionState.pendingReminder != null;
    final isConnected = ref.watch(isGoogleConnectedProvider);

    return CalendarEventCard(
      extractedEvent: sessionState.pendingExtractedEvent,
      isExtracting: sessionState.isExtracting,
      extractionError: sessionState.extractionError,
      isReminder: isReminder,
      isGoogleConnected: isConnected,
      onConfirm: () {
        ref.read(sessionNotifierProvider.notifier).confirmCalendarEvent();
      },
      onDismiss: () {
        if (isReminder) {
          ref.read(sessionNotifierProvider.notifier).dismissReminder();
        } else {
          ref.read(sessionNotifierProvider.notifier).dismissCalendarEvent();
        }
      },
      onConnect: () async {
        final connected = await ref
            .read(isGoogleConnectedProvider.notifier)
            .connect();
        if (connected && mounted) {
          // After connecting, the card will show "Add to Calendar"
          // because isGoogleConnectedProvider updates automatically.
        }
      },
    );
  }

  /// Build the message input field with send/mic button.
  Widget _buildInputField(
    BuildContext context,
    bool voiceEnabled,
    VoiceSessionOrchestrator orchestrator,
  ) {
    final isWaiting = ref.watch(
      sessionNotifierProvider.select((s) => s.isWaitingForAgent),
    );
    final voiceState = orchestrator.state;
    final isListening = voiceState.phase == VoiceLoopPhase.listening;
    final isSpeaking = voiceState.phase == VoiceLoopPhase.speaking;

    final bottomInset = MediaQuery.of(context).viewPadding.bottom;
    return Container(
      padding: EdgeInsets.fromLTRB(12, 8, 12, 16 + bottomInset),
      // Slight elevation to separate from the message list.
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 4,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Voice/Text input toggle — visible when voice is enabled.
          if (voiceEnabled)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: SegmentedButton<bool>(
                segments: const [
                  ButtonSegment<bool>(
                    value: false,
                    label: Text('Voice'),
                    icon: Icon(Icons.mic, size: 18),
                  ),
                  ButtonSegment<bool>(
                    value: true,
                    label: Text('Text'),
                    icon: Icon(Icons.keyboard, size: 18),
                  ),
                ],
                selected: {_isTextInputMode},
                onSelectionChanged: (selected) {
                  setState(() {
                    _isTextInputMode = selected.first;
                  });
                  if (selected.first) {
                    // Stop any active voice session when switching to text.
                    orchestrator.stop();
                  } else {
                    // Restart continuous voice mode when switching back.
                    _startContinuousModeWithGreeting(
                      VoiceRecoveryMessages.welcomeBack,
                    );
                  }
                },
                showSelectedIcon: false,
                style: ButtonStyle(
                  visualDensity: VisualDensity.compact,
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
              ),
            ),

          // Phase indicator chip for continuous mode.
          if (voiceEnabled && voiceState.isContinuousMode)
            _buildPhaseIndicator(voiceState),

          // Transcript preview during listening.
          if (isListening && voiceState.transcriptPreview.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Text(
                voiceState.transcriptPreview,
                style: TextStyle(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                  fontStyle: FontStyle.italic,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ),

          // Recording indicator.
          if (isListening && voiceState.transcriptPreview.isEmpty)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                children: [
                  Icon(
                    Icons.fiber_manual_record,
                    color: Theme.of(context).colorScheme.error,
                    size: 12,
                  ),
                  const SizedBox(width: 4),
                  Text(
                    'Listening...',
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                      fontSize: 12,
                      fontStyle: FontStyle.italic,
                    ),
                  ),
                ],
              ),
            ),

          Row(
            children: [
              // Text field — expands to fill available width.
              // In text input mode, always enabled (voice states don't block).
              Expanded(
                child: TextField(
                  controller: _textController,
                  enabled: _isTextInputMode
                      ? !isWaiting
                      : !isWaiting && !isListening && !isSpeaking,
                  textCapitalization: TextCapitalization.sentences,
                  maxLines: null, // Allows multi-line input.
                  decoration: InputDecoration(
                    hintText: isListening && !_isTextInputMode
                        ? 'Listening...'
                        : 'Type your thoughts...',
                  ),
                  onSubmitted: isWaiting ? null : (_) => _sendMessage(),
                ),
              ),
              // Camera button — always visible so users can add media
              // during voice mode.
              IconButton(
                tooltip: 'Add photo',
                onPressed: () => _captureMedia(context),
                icon: const Icon(Icons.camera_alt_outlined),
              ),
              // Action button: mic, stop, interrupt, or send.
              // In text input mode, always show send button.
              if (_isTextInputMode)
                IconButton.filled(
                  tooltip: 'Send message',
                  onPressed: isWaiting ? null : _sendMessage,
                  icon: const Icon(Icons.send),
                )
              else
                _buildActionButton(isWaiting, voiceEnabled, orchestrator),
            ],
          ),
        ],
      ),
    );
  }

  /// Build the voice phase indicator chip.
  Widget _buildPhaseIndicator(VoiceOrchestratorState voiceState) {
    final (label, icon, color) = switch (voiceState.phase) {
      VoiceLoopPhase.listening => (
        'Listening',
        Icons.mic,
        Theme.of(context).colorScheme.error,
      ),
      VoiceLoopPhase.processing => (
        'Thinking',
        Icons.psychology,
        Theme.of(context).colorScheme.primary,
      ),
      VoiceLoopPhase.speaking => (
        'Speaking',
        Icons.volume_up,
        Theme.of(context).colorScheme.tertiary,
      ),
      VoiceLoopPhase.paused => (
        'Paused',
        Icons.pause,
        Theme.of(context).colorScheme.onSurfaceVariant,
      ),
      VoiceLoopPhase.error => (
        'Error',
        Icons.error_outline,
        Theme.of(context).colorScheme.error,
      ),
      VoiceLoopPhase.idle => (
        'Voice Ready',
        Icons.mic_none,
        Theme.of(context).colorScheme.onSurfaceVariant,
      ),
    };

    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 4),
          Text(label, style: TextStyle(fontSize: 12, color: color)),
        ],
      ),
    );
  }

  /// Build the action button (mic/stop/interrupt/send/initializing).
  Widget _buildActionButton(
    bool isWaiting,
    bool voiceEnabled,
    VoiceSessionOrchestrator orchestrator,
  ) {
    final voiceState = orchestrator.state;

    // 1. STT initializing → spinner.
    if (_isInitializingStt) {
      return const SizedBox(
        width: 48,
        height: 48,
        child: Padding(
          padding: EdgeInsets.all(12),
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
      );
    }

    // 2. Speaking → interrupt button.
    if (voiceState.phase == VoiceLoopPhase.speaking) {
      return IconButton.filled(
        tooltip: 'Stop speaking',
        onPressed: () => orchestrator.interrupt(),
        style: IconButton.styleFrom(
          backgroundColor: Theme.of(context).colorScheme.tertiary,
        ),
        icon: const Icon(Icons.stop),
      );
    }

    // 3. Listening → stop button (red).
    if (voiceState.phase == VoiceLoopPhase.listening) {
      return IconButton.filled(
        tooltip: 'Stop recording',
        onPressed: () {
          if (voiceState.isContinuousMode) {
            orchestrator.stop();
          } else {
            // 800ms delay before stopping PTT to capture trailing speech.
            // Double-tap (timer already active) cancels and stops immediately.
            if (_pttStopTimer?.isActive ?? false) {
              _pttStopTimer?.cancel();
              orchestrator.stopPushToTalk();
            } else {
              _pttStopTimer = Timer(const Duration(milliseconds: 800), () {
                orchestrator.stopPushToTalk();
              });
            }
          }
        },
        style: IconButton.styleFrom(
          backgroundColor: Theme.of(context).colorScheme.error,
        ),
        icon: const Icon(Icons.stop),
      );
    }

    // 4. Idle + voice enabled + empty text → mic button.
    //    Single tap starts continuous mode (hands-free conversation).
    //    Long press starts push-to-talk (single utterance).
    if (voiceEnabled && _textController.text.isEmpty && !isWaiting) {
      return GestureDetector(
        onLongPress: () => _startPushToTalk(),
        child: IconButton.filled(
          tooltip: 'Start voice conversation',
          onPressed: () => _startContinuousMode(),
          icon: const Icon(Icons.mic),
        ),
      );
    }

    // 5. Default → send button.
    return IconButton.filled(
      tooltip: 'Send message',
      onPressed: isWaiting ? null : _sendMessage,
      icon: const Icon(Icons.send),
    );
  }

  /// Start push-to-talk via the orchestrator.
  Future<void> _startPushToTalk() async {
    final sttReady = await _ensureSttReady();
    if (!sttReady || !mounted) return;

    final orchestrator = ref.read(voiceOrchestratorProvider);
    await orchestrator.startPushToTalk();
  }

  /// Start continuous mode via the orchestrator.
  Future<void> _startContinuousMode() async {
    final sttReady = await _ensureSttReady();
    if (!sttReady || !mounted) return;

    final orchestrator = ref.read(voiceOrchestratorProvider);
    await orchestrator.startContinuousMode(
      "I'm listening. Go ahead and share what's on your mind.",
    );
  }

  /// Ensure STT model is downloaded and service is initialized.
  ///
  /// Returns true if STT is ready, false if not (user cancelled download
  /// or initialization failed).
  ///
  /// When the speech_to_text engine is selected, skips model download
  /// entirely — the system recognizer needs no local model files.
  Future<bool> _ensureSttReady() async {
    // Request microphone permission before anything else.
    final recorder = AudioRecorder();
    try {
      final hasPermission = await recorder.hasPermission();
      if (!hasPermission) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text(
                'Microphone permission is required for voice mode.',
              ),
            ),
          );
        }
        return false;
      }
    } finally {
      await recorder.dispose();
    }
    if (!mounted) return false;

    final engine = ref.read(sttEngineProvider);

    // speech_to_text uses the system recognizer — no model download needed.
    // sherpa_onnx requires the 71MB Zipformer model.
    if (engine == SttEngine.sherpaOnnx) {
      final modelReady = await ref.read(sttModelReadyProvider.future);
      if (!modelReady) {
        // Trigger model download dialog.
        final downloadService = ModelDownloadService();
        final downloaded = await showModelDownloadDialog(
          context: context,
          downloadService: downloadService,
        );
        downloadService.dispose();

        if (!downloaded || !mounted) return false;
        // Invalidate so the provider re-checks.
        ref.invalidate(sttModelReadyProvider);
      }
    }

    // Initialize STT if needed.
    final sttService = ref.read(speechRecognitionServiceProvider);
    if (!sttService.isInitialized) {
      setState(() => _isInitializingStt = true);
      try {
        final modelPath = await ref.read(sttModelPathProvider.future);
        await sttService.initialize(modelPath: modelPath);
      } finally {
        if (mounted) setState(() => _isInitializingStt = false);
      }
      if (!mounted) return false;
    }

    return true;
  }

  /// Capture a photo and add it to the session.
  ///
  /// Flow: show source sheet → capture/pick → preview → process → save.
  /// Sets [_isCapturingMedia] around the native picker to prevent
  /// [_autoSaveIfNeeded] from ending the session on lifecycle pause.
  Future<void> _captureMedia(BuildContext context) async {
    final sessionId = ref.read(sessionNotifierProvider).activeSessionId;
    if (sessionId == null) return;

    // Step 1: Choose source (photo/video, camera/gallery).
    // The bottom sheet is in-app UI — no lifecycle pause yet.
    final source = await showMediaCaptureSheet(context);
    if (source == null || !mounted) return;

    // The native picker/camera launches next and triggers lifecycle pause.
    _isCapturingMedia = true;
    try {
      // Route to the appropriate handler.
      switch (source) {
        case MediaSource.photoCamera:
        case MediaSource.photoGallery:
          await _handlePhotoCapture(context, sessionId, source);
        case MediaSource.videoCamera:
        case MediaSource.videoGallery:
          await _handleVideoCapture(context, sessionId, source);
      }
    } finally {
      _isCapturingMedia = false;
    }
  }

  /// Handle photo capture/pick flow.
  ///
  /// Pauses STT before camera access (audio focus conflict — matches
  /// [_handleVideoCapture] pattern) and resumes after capture completes.
  Future<void> _handlePhotoCapture(
    BuildContext context,
    String sessionId,
    MediaSource source,
  ) async {
    // Pause STT if voice mode is active (same pattern as _handleVideoCapture).
    final orchestrator = ref.read(voiceOrchestratorProvider);
    final wasSttActive =
        ref.read(voiceModeEnabledProvider) &&
        orchestrator.state.phase != VoiceLoopPhase.idle;
    if (wasSttActive) {
      orchestrator.pause();
    }

    // Track whether the photo was actually saved (for silent vs normal resume).
    var photoSaved = false;
    try {
      // Step 2: Capture or pick the photo.
      final photoService = ref.read(photoServiceProvider);
      final rawFile = source == MediaSource.photoCamera
          ? await photoService.takePhoto()
          : await photoService.pickFromGallery();
      if (rawFile == null || !mounted) return;

      // Step 3: Show preview and wait for user to confirm.
      final confirmed = await showPhotoPreviewDialog(
        context: context,
        photoFile: rawFile,
      );
      if (!confirmed || !mounted) return;

      // Step 4: Process and save (with user feedback).
      final uuid = const Uuid();
      final photoId = uuid.v4();
      final messageId = uuid.v4();

      // Show processing indicator while EXIF strip + resize runs.
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Row(
              children: [
                SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
                SizedBox(width: 12),
                Text('Processing photo...'),
              ],
            ),
            duration: Duration(seconds: 10),
          ),
        );
      }

      ProcessedPhoto? processed;
      try {
        processed = await photoService.processAndSave(
          rawFile,
          sessionId,
          photoId,
        );
      } on Exception {
        processed = null;
      }

      if (!mounted) return;
      ScaffoldMessenger.of(context).hideCurrentSnackBar();

      if (processed == null) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Failed to add photo. Please try again.'),
          ),
        );
        return;
      }

      // Step 5: Insert photo record and photo message.
      final photoDao = ref.read(photoDaoProvider);
      final messageDao = ref.read(messageDaoProvider);
      final now = DateTime.now().toUtc();

      await photoDao.insertPhoto(
        photoId: photoId,
        sessionId: sessionId,
        localPath: processed.file.path,
        timestamp: now,
        messageId: messageId,
        width: processed.width,
        height: processed.height,
        fileSizeBytes: processed.fileSizeBytes,
      );

      await messageDao.insertMessage(
        messageId,
        sessionId,
        'USER',
        '[Photo]',
        now,
        inputMethod: 'PHOTO',
        photoId: photoId,
      );

      photoSaved = true;

      // If voice mode is active, prompt for a photo description.
      if (!mounted) return;
      if (wasSttActive && orchestrator.state.phase != VoiceLoopPhase.idle) {
        final description = await orchestrator.capturePhotoDescription();
        if (description != null && description.trim().isNotEmpty) {
          await photoDao.updateDescription(photoId, description.trim());
        }
      }
    } finally {
      // Resume STT if we paused it.
      // Silent resume when photo was cancelled (no TTS interruption).
      // Normal resume when photo was saved (speaks brief "Go ahead.").
      if (wasSttActive && mounted) {
        orchestrator.resume(silent: !photoSaved);
      }
    }
  }

  /// Handle video capture/pick flow (Phase 12 — ADR-0021).
  ///
  /// Pauses STT before camera access (audio focus conflict — ADR-0021 §7),
  /// captures/picks the video, processes (metadata strip + thumbnail),
  /// and saves to the session via SessionNotifier.attachVideo().
  Future<void> _handleVideoCapture(
    BuildContext context,
    String sessionId,
    MediaSource source,
  ) async {
    // Pause STT if voice mode is active (ADR-0021 §7).
    final voiceEnabled = ref.read(voiceModeEnabledProvider);
    final orchestrator = ref.read(voiceOrchestratorProvider);
    final wasSttActive =
        voiceEnabled && orchestrator.state.phase != VoiceLoopPhase.idle;
    if (wasSttActive) {
      orchestrator.pause();
    }

    // Capture or pick the video.
    final videoService = ref.read(videoServiceProvider);
    final rawFile = source == MediaSource.videoCamera
        ? await videoService.recordVideo()
        : await videoService.pickFromGallery();

    if (rawFile == null || !mounted) {
      // Resume STT silently if we paused it (video was cancelled).
      if (wasSttActive && mounted) {
        orchestrator.resume(silent: true);
      }
      return;
    }

    // Show processing indicator while metadata strip + thumbnail runs.
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Row(
            children: [
              SizedBox(
                width: 16,
                height: 16,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
              SizedBox(width: 12),
              Text('Processing video...'),
            ],
          ),
          duration: Duration(seconds: 30),
        ),
      );
    }

    // Attach via SessionNotifier (processes, saves to DB, creates message).
    final success = await ref
        .read(sessionNotifierProvider.notifier)
        .attachVideo(rawFile);

    if (!mounted) return;
    ScaffoldMessenger.of(context).hideCurrentSnackBar();

    if (!success) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Failed to add video. File may be too large (100MB max).',
          ),
        ),
      );
    }

    // Resume STT if we paused it. Normal resume (video was saved/attempted).
    if (wasSttActive && mounted) {
      orchestrator.resume();
    }
  }

  /// Send the user's message to the session notifier.
  Future<void> _sendMessage() async {
    final text = _textController.text.trim();
    if (text.isEmpty) return;

    _textController.clear();

    await ref
        .read(sessionNotifierProvider.notifier)
        .sendMessage(text, inputMethod: 'TEXT');
  }

  /// End the session and navigate back immediately.
  Future<void> _endSessionAndPop() async {
    ref.read(voiceOrchestratorProvider).stop();
    await ref.read(sessionNotifierProvider.notifier).endSession();
    if (mounted) {
      ref.read(sessionNotifierProvider.notifier).dismissSession();
      Navigator.of(context).pop();
    }
  }

  /// Dismiss the completed session and navigate back to the list.
  void _dismissAndPop() {
    ref.read(voiceOrchestratorProvider).stop();
    ref.read(sessionNotifierProvider.notifier).dismissSession();
    if (mounted) {
      Navigator.of(context).pop();
    }
  }

  /// Show a confirmation dialog before discarding the session.
  Future<void> _showDiscardConfirmation() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Discard this entry?'),
        content: const Text('This cannot be undone.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.error,
            ),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Discard'),
          ),
        ],
      ),
    );

    if (confirmed == true && mounted) {
      ref.read(voiceOrchestratorProvider).stop();
      await ref.read(sessionNotifierProvider.notifier).discardSession();
      if (mounted) {
        Navigator.of(context).pop();
      }
    }
  }

  /// Scroll the message list to the bottom.
  void _scrollToBottom() {
    if (_scrollController.hasClients) {
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOut,
      );
    }
  }
}

/// Escalating thinking indicator that updates its message over time.
///
/// Starts with "Thinking..." and escalates to provide reassurance
/// during slow API calls:
///   0s  -> "Thinking..."
///   8s  -> "Still thinking..."
///   15s -> "Taking a moment..."
class _ThinkingIndicator extends StatefulWidget {
  const _ThinkingIndicator();

  @override
  State<_ThinkingIndicator> createState() => _ThinkingIndicatorState();
}

class _ThinkingIndicatorState extends State<_ThinkingIndicator> {
  static const _messages = [
    'Thinking...',
    'Still thinking...',
    'Taking a moment...',
  ];
  static const _thresholds = [
    Duration.zero,
    Duration(seconds: 8),
    Duration(seconds: 15),
  ];

  int _messageIndex = 0;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer(_thresholds[1], () {
      if (mounted) {
        setState(() => _messageIndex = 1);
        _timer = Timer(_thresholds[2] - _thresholds[1], () {
          if (mounted) setState(() => _messageIndex = 2);
        });
      }
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Row(
        children: [
          SizedBox(
            width: 16,
            height: 16,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              color: Theme.of(context).colorScheme.primary,
            ),
          ),
          const SizedBox(width: 8),
          Text(
            _messages[_messageIndex],
            style: TextStyle(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
              fontStyle: FontStyle.italic,
            ),
          ),
        ],
      ),
    );
  }
}
