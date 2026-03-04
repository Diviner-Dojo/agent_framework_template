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

import '../theme/app_theme.dart' show ChatBubbleColors;
import '../../utils/timestamp_utils.dart';
import '../../providers/theme_providers.dart' show BubbleShape;

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
/// [videoThumbnailPath] if set, renders a video thumbnail with play overlay.
/// [videoDuration] the video duration in seconds (shown as overlay badge).
/// [onVideoTap] callback when the video thumbnail is tapped (opens player).
/// [bubbleShape] controls the border radius style (rounded, soft square, pill).
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
  final String? videoThumbnailPath;
  final int? videoDuration;
  final VoidCallback? onVideoTap;

  /// Controls the border radius shape of the bubble.
  final BubbleShape bubbleShape;

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
    this.videoThumbnailPath,
    this.videoDuration,
    this.onVideoTap,
    this.bubbleShape = BubbleShape.rounded,
  });

  /// Whether this message was sent by the user.
  bool get isUser => role == 'USER';

  /// Compute the border radius for the bubble based on [shape] and sender.
  ///
  /// All shapes preserve the asymmetric "tail" corner (smaller radius on the
  /// sender's bottom corner) to maintain message direction scanning.
  static BorderRadius _bubbleRadius(BubbleShape shape, bool isUser) {
    return switch (shape) {
      BubbleShape.rounded => BorderRadius.only(
        topLeft: const Radius.circular(16),
        topRight: const Radius.circular(16),
        bottomLeft: Radius.circular(isUser ? 16 : 4),
        bottomRight: Radius.circular(isUser ? 4 : 16),
      ),
      BubbleShape.softSquare => BorderRadius.only(
        topLeft: const Radius.circular(8),
        topRight: const Radius.circular(8),
        bottomLeft: Radius.circular(isUser ? 8 : 2),
        bottomRight: Radius.circular(isUser ? 2 : 8),
      ),
      BubbleShape.pill => BorderRadius.only(
        topLeft: const Radius.circular(24),
        topRight: const Radius.circular(24),
        bottomLeft: Radius.circular(isUser ? 24 : 6),
        bottomRight: Radius.circular(isUser ? 6 : 24),
      ),
    };
  }

  /// Format seconds as mm:ss for the duration badge.
  static String _formatSeconds(int seconds) {
    final m = (seconds ~/ 60).toString().padLeft(2, '0');
    final s = (seconds % 60).toString().padLeft(2, '0');
    return '$m:$s';
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final bubbleColors = theme.extension<ChatBubbleColors>();

    // Determine bubble color from the active palette's ThemeExtension.
    final bubbleColor = isUser
        ? (bubbleColors?.userBubble ?? theme.colorScheme.primary)
        : (bubbleColors?.assistantBubble ??
              theme.colorScheme.surfaceContainerHighest);

    // Text color from the ThemeExtension with safe fallbacks.
    final textColor = isUser
        ? (bubbleColors?.userText ?? theme.colorScheme.onPrimary)
        : (bubbleColors?.assistantText ??
              theme.textTheme.bodyLarge?.color ??
              Colors.black);

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
                borderRadius: _bubbleRadius(bubbleShape, isUser),
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
                                errorBuilder: (_, _, _) => const SizedBox(
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

                  // Video thumbnail with play overlay (Phase 12 — ADR-0021).
                  if (videoThumbnailPath != null) ...[
                    Semantics(
                      label:
                          'Video${videoDuration != null ? ', ${videoDuration}s' : ''}. Tap to play.',
                      button: true,
                      child: GestureDetector(
                        onTap: onVideoTap,
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(8),
                          child: ConstrainedBox(
                            constraints: const BoxConstraints(
                              maxWidth: 200,
                              maxHeight: 150,
                            ),
                            child: Stack(
                              alignment: Alignment.center,
                              children: [
                                Image.file(
                                  File(videoThumbnailPath!),
                                  fit: BoxFit.cover,
                                  width: 200,
                                  errorBuilder: (_, _, _) => Container(
                                    width: 200,
                                    height: 112,
                                    color: Colors.black26,
                                    child: const Center(
                                      child: Icon(
                                        Icons.videocam_off,
                                        size: 40,
                                        color: Colors.white54,
                                      ),
                                    ),
                                  ),
                                ),
                                // Play button overlay.
                                Container(
                                  width: 48,
                                  height: 48,
                                  decoration: BoxDecoration(
                                    color: Colors.black54,
                                    shape: BoxShape.circle,
                                  ),
                                  child: const Icon(
                                    Icons.play_arrow,
                                    color: Colors.white,
                                    size: 32,
                                  ),
                                ),
                                // Duration badge.
                                if (videoDuration != null && videoDuration! > 0)
                                  Positioned(
                                    bottom: 4,
                                    right: 4,
                                    child: Container(
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 6,
                                        vertical: 2,
                                      ),
                                      decoration: BoxDecoration(
                                        color: Colors.black54,
                                        borderRadius: BorderRadius.circular(4),
                                      ),
                                      child: Text(
                                        _formatSeconds(videoDuration!),
                                        style: const TextStyle(
                                          color: Colors.white,
                                          fontSize: 11,
                                        ),
                                      ),
                                    ),
                                  ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
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
