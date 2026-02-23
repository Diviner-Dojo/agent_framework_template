// ===========================================================================
// file: lib/ui/widgets/session_card.dart
// purpose: Card widget for displaying a journal session in the list.
//
// Shows: date, summary (or placeholder), duration, message count.
// Tapping navigates to the session detail (read-only transcript) screen.
// Overflow menu provides a "Delete" option with confirmation dialog.
// ===========================================================================

import 'package:flutter/material.dart';

import '../../database/app_database.dart';
import '../../models/sync_status.dart';
import '../../utils/timestamp_utils.dart';
import 'sync_status_indicator.dart';

/// A card representing a single past journal session.
///
/// [session] is the drift-generated JournalSession data class.
/// [messageCount] is the number of messages in this session.
/// [onTap] is called when the user taps the card.
/// [onDelete] is called when the user confirms deletion via the overflow menu.
class SessionCard extends StatelessWidget {
  final JournalSession session;
  final int messageCount;
  final VoidCallback? onTap;
  final VoidCallback? onDelete;

  const SessionCard({
    super.key,
    required this.session,
    required this.messageCount,
    this.onTap,
    this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    // Calculate session duration if both start and end times exist.
    final duration = session.endTime?.difference(session.startTime);

    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Top row: date, duration, and overflow menu.
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    formatShortDate(session.startTime),
                    style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      if (duration != null)
                        Text(
                          formatDuration(duration),
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                      if (onDelete != null)
                        _DeleteMenuButton(
                          session: session,
                          onDelete: onDelete!,
                        ),
                    ],
                  ),
                ],
              ),
              const SizedBox(height: 8),

              // Summary text or placeholder.
              Text(
                session.summary ?? 'No summary',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: session.summary != null
                      ? theme.colorScheme.onSurface
                      : theme.colorScheme.onSurfaceVariant,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 8),

              // Bottom row: message count and sync status.
              Row(
                children: [
                  Text(
                    '$messageCount message${messageCount == 1 ? '' : 's'}',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                  const Spacer(),
                  SyncStatusIndicator(
                    status: SyncStatus.fromString(session.syncStatus),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Overflow menu button for session card actions.
class _DeleteMenuButton extends StatelessWidget {
  final JournalSession session;
  final VoidCallback onDelete;

  const _DeleteMenuButton({required this.session, required this.onDelete});

  @override
  Widget build(BuildContext context) {
    return PopupMenuButton<String>(
      icon: const Icon(Icons.more_vert, size: 20),
      padding: EdgeInsets.zero,
      constraints: const BoxConstraints(),
      tooltip: 'Session options',
      onSelected: (value) {
        if (value == 'delete') {
          _showDeleteConfirmation(context);
        }
      },
      itemBuilder: (context) => [
        PopupMenuItem(
          value: 'delete',
          child: ListTile(
            leading: Icon(
              Icons.delete_outline,
              color: Theme.of(context).colorScheme.error,
            ),
            title: Text(
              'Delete',
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
            contentPadding: EdgeInsets.zero,
          ),
        ),
      ],
    );
  }

  void _showDeleteConfirmation(BuildContext context) {
    final dateStr = formatShortDate(session.startTime);
    final summaryPreview = session.summary != null
        ? '"${session.summary!.length > 60 ? '${session.summary!.substring(0, 60)}...' : session.summary!}"'
        : 'No summary';

    showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete this entry?'),
        content: Text('$dateStr\n$summaryPreview\n\nThis cannot be undone.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.error,
            ),
            onPressed: () {
              Navigator.of(context).pop(true);
              onDelete();
            },
            child: const Text('Delete'),
          ),
        ],
      ),
    );
  }
}
