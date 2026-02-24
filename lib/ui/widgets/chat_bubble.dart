// ===========================================================================
// file: lib/ui/widgets/chat_bubble.dart
// purpose: Chat message bubble widget for the conversation view.
//
// Visually distinguishes USER messages (right-aligned, colored) from
// ASSISTANT messages (left-aligned, neutral background).
// Used in both the active session screen and the read-only detail screen.
//
// Recall mode (isRecall=true) adds a left border accent and "From your
// journal" header with citation chips. Used when the assistant answers a
// memory recall query with grounded citations (ADR-0013).
// ===========================================================================

import 'dart:io';

import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import '../../utils/timestamp_utils.dart';

/// Data for a single cited session in a recall bubble.
///
/// Used to render tappable citation chips below the recall answer.
class RecallCitation {
  /// The session ID for navigation.
  final String sessionId;

  /// Short label for the chip (e.g., "Feb 19 — Morning reflection").
  final String label;

  const RecallCitation({required this.sessionId, required this.label});
}

/// A single chat message bubble.
///
/// [content] is the message text.
/// [role] is 'USER', 'ASSISTANT', or 'SYSTEM'.
/// [timestamp] is the UTC time when the message was sent.
/// [isRecall] enables recall mode with left border accent and citation chips.
/// [citations] are the cited sessions shown as tappable chips in recall mode.
/// [onCitationTap] is called with a session ID when a citation chip is tapped.
/// [isOfflineRecall] shows an offline fallback message instead of the normal
///   recall header/footer.
/// [photoPath] if set, renders a photo thumbnail above the text content.
/// [photoCaption] optional caption displayed below the photo thumbnail.
/// [onPhotoTap] callback when the photo thumbnail is tapped (opens viewer).
class ChatBubble extends StatelessWidget {
  final String content;
  final String role;
  final DateTime timestamp;
  final bool isRecall;
  final List<RecallCitation> citations;
  final void Function(String sessionId)? onCitationTap;
  final bool isOfflineRecall;
  final String? photoPath;
  final String? photoCaption;
  final VoidCallback? onPhotoTap;

  /// Prefix for the Hero animation tag. Each screen must use a unique prefix
  /// to avoid duplicate Hero tags when multiple screens are in the widget tree.
  final String photoHeroPrefix;

  const ChatBubble({
    super.key,
    required this.content,
    required this.role,
    required this.timestamp,
    this.isRecall = false,
    this.citations = const [],
    this.onCitationTap,
    this.isOfflineRecall = false,
    this.photoPath,
    this.photoCaption,
    this.onPhotoTap,
    this.photoHeroPrefix = 'photo-chat',
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
                // Recall mode: left border accent (3px primary color).
                border: isRecall
                    ? Border(
                        left: BorderSide(
                          color: theme.colorScheme.primary,
                          width: 3,
                        ),
                      )
                    : null,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Photo thumbnail (Phase 9 — ADR-0018).
                  if (photoPath != null) ...[
                    Semantics(
                      label: photoCaption != null && photoCaption!.isNotEmpty
                          ? 'Photo: $photoCaption. Tap to view full screen.'
                          : 'Photo. Tap to view full screen.',
                      button: true,
                      child: GestureDetector(
                        onTap: onPhotoTap,
                        child: Hero(
                          tag: '$photoHeroPrefix-$photoPath',
                          child: ClipRRect(
                            borderRadius: BorderRadius.circular(8),
                            child: ConstrainedBox(
                              constraints: const BoxConstraints(
                                maxWidth: 200,
                                maxHeight: 200,
                              ),
                              child: Image.file(
                                File(photoPath!),
                                fit: BoxFit.cover,
                                errorBuilder: (_, __, ___) => const SizedBox(
                                  width: 200,
                                  height: 100,
                                  child: Center(
                                    child: Icon(Icons.broken_image, size: 40),
                                  ),
                                ),
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),
                    if (photoCaption != null) ...[
                      const SizedBox(height: 4),
                      Text(
                        photoCaption!,
                        style: TextStyle(
                          color: textColor,
                          fontSize: 13,
                          fontStyle: FontStyle.italic,
                        ),
                      ),
                    ],
                    const SizedBox(height: 4),
                  ],

                  // Recall header: "From your journal" with history icon.
                  if (isRecall && !isOfflineRecall)
                    _RecallHeader(textColor: textColor),
                  if (isRecall && isOfflineRecall)
                    _OfflineRecallHeader(textColor: textColor),

                  // Message text.
                  Text(
                    content,
                    style: TextStyle(
                      color: textColor,
                      fontSize: 15,
                      height: 1.4,
                    ),
                  ),

                  // Citation chips (recall mode only).
                  if (isRecall && citations.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 6,
                      runSpacing: 4,
                      children: citations.map((citation) {
                        return ActionChip(
                          avatar: Icon(
                            Icons.article_outlined,
                            size: 14,
                            color: theme.colorScheme.primary,
                          ),
                          label: Text(
                            citation.label,
                            style: theme.textTheme.labelSmall,
                          ),
                          onPressed: () =>
                              onCitationTap?.call(citation.sessionId),
                          materialTapTargetSize:
                              MaterialTapTargetSize.shrinkWrap,
                          visualDensity: VisualDensity.compact,
                        );
                      }).toList(),
                    ),
                  ],

                  // Recall footer: disclaimer.
                  if (isRecall && !isOfflineRecall && citations.isNotEmpty) ...[
                    const SizedBox(height: 6),
                    Text(
                      'Based on your entries',
                      style: TextStyle(
                        color: textColor.withValues(alpha: 0.5),
                        fontSize: 11,
                        fontStyle: FontStyle.italic,
                      ),
                    ),
                  ],

                  // Offline recall footer.
                  if (isRecall && isOfflineRecall) ...[
                    const SizedBox(height: 6),
                    Text(
                      'Full recall synthesis isn\'t available offline \u2014 '
                      'tap a session to read it.',
                      style: TextStyle(
                        color: textColor.withValues(alpha: 0.5),
                        fontSize: 11,
                        fontStyle: FontStyle.italic,
                      ),
                    ),
                  ],

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

/// Recall header showing "From your journal" with history icon.
class _RecallHeader extends StatelessWidget {
  final Color textColor;

  const _RecallHeader({required this.textColor});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.history,
            size: 14,
            color: textColor.withValues(alpha: 0.6),
          ),
          const SizedBox(width: 4),
          Text(
            'From your journal',
            style: TextStyle(
              color: textColor.withValues(alpha: 0.6),
              fontSize: 12,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }
}

/// Offline recall header showing cloud-off icon.
class _OfflineRecallHeader extends StatelessWidget {
  final Color textColor;

  const _OfflineRecallHeader({required this.textColor});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.cloud_off,
            size: 14,
            color: textColor.withValues(alpha: 0.6),
          ),
          const SizedBox(width: 4),
          Text(
            'From your journal (offline)',
            style: TextStyle(
              color: textColor.withValues(alpha: 0.6),
              fontSize: 12,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }
}
