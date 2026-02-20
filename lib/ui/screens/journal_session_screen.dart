// ===========================================================================
// file: lib/ui/screens/journal_session_screen.dart
// purpose: Active journaling conversation screen.
//
// This is where the conversation happens. It shows:
//   - A scrollable list of chat bubbles (assistant + user messages)
//   - A text input field at the bottom with a send button
//   - An end session button in the app bar
//
// The screen auto-scrolls to the latest message when new messages arrive.
// On first load, the session has already been created by SessionNotifier
// (the greeting message is already in the database).
//
// UX features:
//   - PopScope intercepts back navigation with a confirmation dialog
//   - Escalating thinking indicator provides progress feedback
//   - Closing summary stays visible until user taps "Done"
// ===========================================================================

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../providers/session_providers.dart';
import '../widgets/chat_bubble.dart';
import '../widgets/end_session_button.dart';

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

  @override
  void dispose() {
    _textController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final sessionState = ref.watch(sessionNotifierProvider);
    final messagesAsync = ref.watch(activeSessionMessagesProvider);

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
            // End session button — hidden when session is already ending.
            if (!sessionState.isSessionEnding)
              EndSessionButton(onEndSession: () => _endSession(context)),
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

  /// Build the message input field and send button.
  Widget _buildInputField(BuildContext context) {
    final isWaiting = ref.watch(
      sessionNotifierProvider.select((s) => s.isWaitingForAgent),
    );

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
      child: Row(
        children: [
          // Text field — expands to fill available width.
          Expanded(
            child: TextField(
              controller: _textController,
              enabled: !isWaiting,
              textCapitalization: TextCapitalization.sentences,
              maxLines: null, // Allows multi-line input.
              decoration: const InputDecoration(
                hintText: 'Type your thoughts...',
              ),
              onSubmitted: isWaiting ? null : (_) => _sendMessage(),
            ),
          ),
          const SizedBox(width: 8),
          // Send button — disabled while waiting for agent response.
          IconButton.filled(
            onPressed: isWaiting ? null : _sendMessage,
            icon: const Icon(Icons.send),
          ),
        ],
      ),
    );
  }

  /// Send the user's message to the session notifier.
  Future<void> _sendMessage() async {
    final text = _textController.text.trim();
    if (text.isEmpty) return;

    _textController.clear();

    await ref.read(sessionNotifierProvider.notifier).sendMessage(text);
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
///   0s  → "Thinking..."
///   8s  → "Still thinking..."
///   15s → "Taking a moment..."
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
