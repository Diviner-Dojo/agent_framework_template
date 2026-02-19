// ===========================================================================
// file: lib/ui/widgets/chat_bubble.dart
// purpose: Chat message bubble widget for the conversation view.
//
// Visually distinguishes USER messages (right-aligned, colored) from
// ASSISTANT messages (left-aligned, neutral background).
// Used in both the active session screen and the read-only detail screen.
// ===========================================================================

import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import '../../utils/timestamp_utils.dart';

/// A single chat message bubble.
///
/// [content] is the message text.
/// [role] is 'USER', 'ASSISTANT', or 'SYSTEM'.
/// [timestamp] is the UTC time when the message was sent.
/// [isUser] is derived from role for alignment/styling.
class ChatBubble extends StatelessWidget {
  final String content;
  final String role;
  final DateTime timestamp;

  const ChatBubble({
    super.key,
    required this.content,
    required this.role,
    required this.timestamp,
  });

  /// Whether this message was sent by the user.
  bool get isUser => role == 'USER';

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    // Determine bubble color based on sender and theme.
    final bubbleColor = isUser
        ? (isDark ? AppTheme.userBubbleDark : AppTheme.userBubbleLight)
        : (isDark
              ? AppTheme.assistantBubbleDark
              : AppTheme.assistantBubbleLight);

    // User text is white on colored background; assistant is themed text.
    final textColor = isUser
        ? Colors.white
        : theme.textTheme.bodyLarge?.color ?? Colors.black;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      child: Row(
        // Align user messages to the right, assistant to the left.
        mainAxisAlignment: isUser
            ? MainAxisAlignment.end
            : MainAxisAlignment.start,
        children: [
          // Constrain bubble width to 75% of screen width.
          ConstrainedBox(
            constraints: BoxConstraints(
              maxWidth: MediaQuery.of(context).size.width * 0.75,
            ),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              decoration: BoxDecoration(
                color: bubbleColor,
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(16),
                  topRight: const Radius.circular(16),
                  // Round the corner opposite to the sender's side.
                  bottomLeft: Radius.circular(isUser ? 16 : 4),
                  bottomRight: Radius.circular(isUser ? 4 : 16),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Message text.
                  Text(
                    content,
                    style: TextStyle(
                      color: textColor,
                      fontSize: 15,
                      height: 1.4,
                    ),
                  ),
                  const SizedBox(height: 4),
                  // Timestamp — small, muted text below the message.
                  Text(
                    formatForDisplay(timestamp),
                    style: TextStyle(
                      color: textColor.withValues(alpha: 0.6),
                      fontSize: 11,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
