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
// ===========================================================================

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
  bool _isSending = false;
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

    return Scaffold(
      appBar: AppBar(
        title: const Text('Journal Entry'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => _handleBack(context),
        ),
        actions: [
          // End session button — shows confirmation dialog.
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
          if (sessionState.isSessionEnding)
            const Padding(
              padding: EdgeInsets.all(8),
              child: Text('Wrapping up your session...'),
            ),

          // Text input field — hidden when session is ending.
          if (!sessionState.isSessionEnding) _buildInputField(context),
        ],
      ),
    );
  }

  /// Build the message input field and send button.
  Widget _buildInputField(BuildContext context) {
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
              textCapitalization: TextCapitalization.sentences,
              maxLines: null, // Allows multi-line input.
              decoration: const InputDecoration(
                hintText: 'Type your thoughts...',
              ),
              onSubmitted: (_) => _sendMessage(),
            ),
          ),
          const SizedBox(width: 8),
          // Send button — disabled while a message is being processed.
          IconButton.filled(
            onPressed: _isSending ? null : _sendMessage,
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

    setState(() => _isSending = true);
    _textController.clear();

    await ref.read(sessionNotifierProvider.notifier).sendMessage(text);

    if (mounted) {
      setState(() => _isSending = false);

      // Check if the session ended (notifier cleared the active session).
      final sessionState = ref.read(sessionNotifierProvider);
      if (sessionState.activeSessionId == null && mounted) {
        Navigator.of(context).pop();
      }
    }
  }

  /// End the session and navigate back to the list.
  Future<void> _endSession(BuildContext context) async {
    await ref.read(sessionNotifierProvider.notifier).endSession();
    if (context.mounted) {
      Navigator.of(context).pop();
    }
  }

  /// Handle the back button — end the session if one is active.
  Future<void> _handleBack(BuildContext context) async {
    final sessionState = ref.read(sessionNotifierProvider);
    if (sessionState.activeSessionId != null) {
      await ref.read(sessionNotifierProvider.notifier).endSession();
    }
    if (context.mounted) {
      Navigator.of(context).pop();
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
