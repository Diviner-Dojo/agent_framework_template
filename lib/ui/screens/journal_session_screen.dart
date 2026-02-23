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
// ===========================================================================

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../providers/session_providers.dart';
import '../../providers/voice_providers.dart';
import '../../services/model_download_service.dart';
import '../../services/speech_recognition_service.dart';
import '../widgets/chat_bubble.dart';
import '../widgets/model_download_dialog.dart';

/// The active journal conversation screen.
class JournalSessionScreen extends ConsumerStatefulWidget {
  const JournalSessionScreen({super.key});

  @override
  ConsumerState<JournalSessionScreen> createState() =>
      _JournalSessionScreenState();
}

class _JournalSessionScreenState extends ConsumerState<JournalSessionScreen> {
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  int _lastMessageCount = 0;

  // Voice state.
  bool _isRecording = false;
  bool _isInitializingStt = false;
  bool _lastInputWasVoice = false;
  bool _ttsInitialized = false;
  StreamSubscription<SpeechResult>? _recognitionSubscription;
  String _previousTranscriptId = '';

  @override
  void initState() {
    super.initState();
    // Rebuild when text changes so mic/send button toggles correctly.
    _textController.addListener(() {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _stopRecording();
    _textController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final sessionState = ref.watch(sessionNotifierProvider);
    final messagesAsync = ref.watch(activeSessionMessagesProvider);

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
            if (!sessionState.isSessionEnding) _buildInputField(context),
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
  ///
  /// When voice mode is enabled and the text field is empty, shows a mic
  /// button instead of the send button. When recording, shows a stop button.
  Widget _buildInputField(BuildContext context) {
    final isWaiting = ref.watch(
      sessionNotifierProvider.select((s) => s.isWaitingForAgent),
    );
    final voiceEnabled = ref.watch(voiceModeEnabledProvider);

    // Listen for new assistant messages to trigger TTS.
    ref.listen<AsyncValue<List<dynamic>>>(activeSessionMessagesProvider, (
      previous,
      next,
    ) {
      if (!voiceEnabled) return;
      final messages = next.valueOrNull;
      if (messages == null || messages.isEmpty) return;
      final lastMsg = messages.last;
      // Only speak new assistant messages.
      if (lastMsg.role == 'ASSISTANT') {
        final msgId = '${lastMsg.messageId}';
        if (msgId != _previousTranscriptId) {
          _previousTranscriptId = msgId;
          _speakAssistantMessage(lastMsg.content);
        }
      }
    });

    return Container(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 16),
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
          // Recording indicator.
          if (_isRecording)
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
                    'Recording...',
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
                  enabled: !isWaiting && !_isRecording,
                  textCapitalization: TextCapitalization.sentences,
                  maxLines: null, // Allows multi-line input.
                  decoration: InputDecoration(
                    hintText: _isRecording
                        ? 'Listening...'
                        : 'Type your thoughts...',
                  ),
                  onSubmitted: isWaiting ? null : (_) => _sendMessage(),
                ),
              ),
              const SizedBox(width: 8),
              // Action button: mic, stop, or send.
              _buildActionButton(isWaiting, voiceEnabled),
            ],
          ),
        ],
      ),
    );
  }

  /// Build the action button (mic/stop/send/initializing) based on state.
  Widget _buildActionButton(bool isWaiting, bool voiceEnabled) {
    if (_isInitializingStt) {
      // Loading spinner while STT model is initializing (5-8s).
      return const SizedBox(
        width: 48,
        height: 48,
        child: Padding(
          padding: EdgeInsets.all(12),
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
      );
    }

    if (_isRecording) {
      // Stop recording button.
      return IconButton.filled(
        tooltip: 'Stop recording',
        onPressed: _stopRecording,
        style: IconButton.styleFrom(
          backgroundColor: Theme.of(context).colorScheme.error,
        ),
        icon: const Icon(Icons.stop),
      );
    }

    if (voiceEnabled && _textController.text.isEmpty && !isWaiting) {
      // Mic button — shown when text field is empty and voice is enabled.
      return IconButton.filled(
        tooltip: 'Start voice input',
        onPressed: _startRecording,
        icon: const Icon(Icons.mic),
      );
    }

    // Send button — default behavior.
    return IconButton.filled(
      tooltip: 'Send message',
      onPressed: isWaiting ? null : _sendMessage,
      icon: const Icon(Icons.send),
    );
  }

  /// Start voice recording and transcription.
  Future<void> _startRecording() async {
    // Guard against double-tap during async initialization.
    if (_isInitializingStt || _isRecording) return;

    // Check if model is downloaded.
    final modelReady = ref.read(sttModelReadyProvider).valueOrNull ?? false;
    if (!modelReady) {
      // Trigger model download dialog.
      final downloadService = ModelDownloadService();
      final downloaded = await showModelDownloadDialog(
        context: context,
        downloadService: downloadService,
      );
      downloadService.dispose();

      if (!downloaded || !mounted) return;
      // Invalidate so the provider re-checks.
      ref.invalidate(sttModelReadyProvider);
    }

    // Show loading indicator during STT initialization (5-8 seconds).
    final sttService = ref.read(speechRecognitionServiceProvider);
    if (!sttService.isInitialized) {
      setState(() => _isInitializingStt = true);
      try {
        final modelPath = await ref.read(sttModelPathProvider.future);
        await sttService.initialize(modelPath: modelPath);
      } finally {
        if (mounted) setState(() => _isInitializingStt = false);
      }
      if (!mounted) return;
    }

    // Start listening.
    final stream = sttService.startListening();
    setState(() => _isRecording = true);

    _recognitionSubscription = stream.listen(
      (result) {
        if (!mounted) return;
        setState(() {
          _textController.text = result.text;
          _textController.selection = TextSelection.fromPosition(
            TextPosition(offset: result.text.length),
          );
        });
        // On final result, stop recording automatically and mark as voice input.
        if (result.isFinal) {
          _lastInputWasVoice = true;
          _stopRecording();
        }
      },
      onError: (Object error) {
        if (mounted) {
          _stopRecording();
          ScaffoldMessenger.of(
            context,
          ).showSnackBar(SnackBar(content: Text('Voice error: $error')));
        }
      },
    );
  }

  /// Stop voice recording.
  Future<void> _stopRecording() async {
    if (!_isRecording) return;

    await _recognitionSubscription?.cancel();
    _recognitionSubscription = null;

    final sttService = ref.read(speechRecognitionServiceProvider);
    if (sttService.isListening) {
      await sttService.stopListening();
    }

    if (mounted) {
      setState(() => _isRecording = false);
    }
  }

  /// Speak an assistant message via TTS.
  ///
  /// Lazily initializes the TTS service on first use. TTS failures are
  /// non-critical — the user can still read the text.
  Future<void> _speakAssistantMessage(String text) async {
    final ttsService = ref.read(textToSpeechServiceProvider);
    try {
      // Lazy initialization on first TTS use.
      if (!_ttsInitialized) {
        await ttsService.initialize();
        _ttsInitialized = true;
      }
      if (ttsService.isSpeaking) {
        await ttsService.stop();
      }
      await ttsService.speak(text);
    } catch (e) {
      // TTS failures are non-critical — user can still read the text.
      debugPrint('[TTS] Error: $e');
    }
  }

  /// Send the user's message to the session notifier.
  Future<void> _sendMessage() async {
    final text = _textController.text.trim();
    if (text.isEmpty) return;

    // Capture voice input flag before clearing.
    // _lastInputWasVoice is set in the stream listener when endpoint detection
    // auto-stops recording. _isRecording is also checked for the case where
    // the user taps send while still recording (before endpoint fires).
    final wasVoiceInput = _lastInputWasVoice || _isRecording;
    _lastInputWasVoice = false;
    if (_isRecording) {
      await _stopRecording();
    }

    _textController.clear();

    await ref
        .read(sessionNotifierProvider.notifier)
        .sendMessage(text, inputMethod: wasVoiceInput ? 'VOICE' : 'TEXT');
  }

  /// End the session (summary will be generated; UI stays on screen).
  Future<void> _endSession(BuildContext context) async {
    await ref.read(sessionNotifierProvider.notifier).endSession();
  }

  /// Dismiss the completed session and navigate back to the list.
  void _dismissAndPop() {
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
