// ===========================================================================
// file: lib/ui/widgets/session_card.dart
// purpose: Card widget for displaying a journal session in the list.
//
// Shows: date, summary (or placeholder), duration, message count.
// Tapping navigates to the session detail (read-only transcript) screen.
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
class SessionCard extends StatelessWidget {
  final JournalSession session;
  final int messageCount;
  final VoidCallback? onTap;

  const SessionCard({
    super.key,
    required this.session,
    required this.messageCount,
    this.onTap,
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
              // Top row: date and duration.
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    formatShortDate(session.startTime),
                    style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  if (duration != null)
                    Text(
                      formatDuration(duration),
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
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
