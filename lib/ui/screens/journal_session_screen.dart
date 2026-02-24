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

import '../../providers/session_providers.dart';
import '../../providers/voice_providers.dart';
import '../../services/model_download_service.dart';
import '../../services/voice_session_orchestrator.dart';
import '../widgets/chat_bubble.dart';
import '../widgets/model_download_dialog.dart';

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

    // Keep orchestrator's session ID in sync for undo support.
    final sessionId = ref.read(sessionNotifierProvider).activeSessionId;
    orchestrator.currentSessionId = sessionId;
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
  void _autoSaveIfNeeded() {
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

    // Watch orchestrator state for UI rebuilds.
    final orchestrator = ref.watch(voiceOrchestratorProvider);

    // Listen for auto-discard signal and show SnackBar + auto-pop.
    ref.listen<bool>(wasAutoDiscardedProvider, (previous, wasDiscarded) {
      if (wasDiscarded) {
        // Reset the flag immediately so it doesn't re-trigger.
        ref.read(wasAutoDiscardedProvider.notifier).state = false;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Session discarded \u2014 nothing was recorded.'),
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
      if (!voiceEnabled) return;
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

    return PopScope(
      canPop:
          sessionState.isClosingComplete ||
          sessionState.activeSessionId == null,
      onPopInvokedWithResult: (didPop, _) {
        if (didPop) {
          // If closing is complete, dismiss state on pop.
          if (sessionState.isClosingComplete) {
            ref.read(sessionNotifierProvider.notifier).dismissSession();
          }
          // Stop orchestrator on navigation away.
          ref.read(voiceOrchestratorProvider).stop();
          return;
        }
        _showExitConfirmation();
      },
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Journal Entry'),
          leading: IconButton(
            icon: const Icon(Icons.arrow_back),
            onPressed: () {
              if (sessionState.isClosingComplete) {
                _dismissAndPop();
              } else {
                _showExitConfirmation();
              }
            },
          ),
          actions: [
            // Overflow menu — hidden when session is already ending.
            if (!sessionState.isSessionEnding)
              PopupMenuButton<String>(
                icon: const Icon(Icons.more_vert),
                tooltip: 'Session options',
                onSelected: (value) {
                  switch (value) {
                    case 'end':
                      _endSession(context);
                    case 'discard':
                      _showDiscardConfirmation();
                  }
                },
                itemBuilder: (context) => [
                  const PopupMenuItem(
                    value: 'end',
                    child: ListTile(
                      leading: Icon(Icons.stop_circle_outlined),
                      title: Text('End Session'),
                      contentPadding: EdgeInsets.zero,
                    ),
                  ),
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
                  return ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.only(top: 8, bottom: 8),
                    itemCount: messages.length,
                    itemBuilder: (context, index) {
                      final msg = messages[index];
                      return ChatBubble(
                        content: msg.content,
                        role: msg.role,
                        timestamp: msg.timestamp,
                      );
                    },
                  );
                },
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (error, stack) => Center(child: Text('Error: $error')),
              ),
            ),

            // "Session ending..." indicator when wrapping up.
            if (sessionState.isSessionEnding && !sessionState.isClosingComplete)
              const Padding(
                padding: EdgeInsets.all(8),
                child: Text('Wrapping up your session...'),
              ),

            // "Done" button — shown after closing summary is saved.
            if (sessionState.isClosingComplete) _buildDoneButton(context),

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

  /// Build the "Done" button shown after the closing summary is ready.
  Widget _buildDoneButton(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: SizedBox(
        width: double.infinity,
        child: FilledButton(
          onPressed: _dismissAndPop,
          child: const Text('Done'),
        ),
      ),
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
              Expanded(
                child: TextField(
                  controller: _textController,
                  enabled: !isWaiting && !isListening && !isSpeaking,
                  textCapitalization: TextCapitalization.sentences,
                  maxLines: null, // Allows multi-line input.
                  decoration: InputDecoration(
                    hintText: isListening
                        ? 'Listening...'
                        : 'Type your thoughts...',
                  ),
                  onSubmitted: isWaiting ? null : (_) => _sendMessage(),
                ),
              ),
              const SizedBox(width: 8),
              // Action button: mic, stop, interrupt, or send.
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
            orchestrator.stopPushToTalk();
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

    // Check if model is downloaded (await the async check).
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

  /// Send the user's message to the session notifier.
  Future<void> _sendMessage() async {
    final text = _textController.text.trim();
    if (text.isEmpty) return;

    _textController.clear();

    await ref
        .read(sessionNotifierProvider.notifier)
        .sendMessage(text, inputMethod: 'TEXT');
  }

  /// End the session (summary will be generated; UI stays on screen).
  Future<void> _endSession(BuildContext context) async {
    // Stop orchestrator before ending session.
    ref.read(voiceOrchestratorProvider).stop();
    await ref.read(sessionNotifierProvider.notifier).endSession();
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

  /// Show a confirmation dialog before ending and leaving the session.
  Future<void> _showExitConfirmation() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('End this session?'),
        content: const Text('Your conversation will be saved with a summary.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('End'),
          ),
        ],
      ),
    );

    if (confirmed == true && mounted) {
      ref.read(voiceOrchestratorProvider).stop();
      await ref.read(sessionNotifierProvider.notifier).endSession();
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
