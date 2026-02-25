// ===========================================================================
// file: lib/ui/widgets/calendar_event_card.dart
// purpose: Inline confirmation card for calendar event/reminder creation.
//
// Shown in the journal session screen when the intent classifier detects
// a calendar or reminder intent. Displays extracted event details and
// action buttons for confirm/dismiss.
//
// States:
//   - Extracting: loading spinner while EventExtractionService runs
//   - Extracted: shows title, date/time, action buttons
//   - Error: shows extraction error with dismiss button
//   - Not connected: shows "Connect Google Calendar" instead of "Add"
//
// See: ADR-0020 §7 (Event Confirmation Policy)
// ===========================================================================

import 'package:flutter/material.dart';

import '../../services/event_extraction_service.dart';

/// Inline confirmation card for a pending calendar event or reminder.
///
/// [extractedEvent] is the parsed event details (null while extracting).
/// [isExtracting] shows a loading state during extraction.
/// [extractionError] displays an error message if extraction failed.
/// [isReminder] distinguishes reminders from events in the UI copy.
/// [isGoogleConnected] gates whether "Add to Calendar" or "Connect" is shown.
/// [onConfirm] is called when the user taps "Add to Calendar".
/// [onDismiss] is called when the user taps "Dismiss".
/// [onConnect] is called when the user taps "Connect Google Calendar".
class CalendarEventCard extends StatelessWidget {
  final ExtractedEvent? extractedEvent;
  final bool isExtracting;
  final String? extractionError;
  final bool isReminder;
  final bool isGoogleConnected;
  final VoidCallback onConfirm;
  final VoidCallback onDismiss;
  final VoidCallback? onConnect;

  const CalendarEventCard({
    super.key,
    this.extractedEvent,
    this.isExtracting = false,
    this.extractionError,
    this.isReminder = false,
    this.isGoogleConnected = false,
    required this.onConfirm,
    required this.onDismiss,
    this.onConnect,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      elevation: 2,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: colorScheme.primary.withValues(alpha: 0.3)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            // Header row with icon and title.
            Row(
              children: [
                Icon(
                  isReminder ? Icons.alarm : Icons.event,
                  color: colorScheme.primary,
                  size: 20,
                ),
                const SizedBox(width: 8),
                Text(
                  isReminder ? 'Reminder' : 'Calendar Event',
                  style: theme.textTheme.titleSmall?.copyWith(
                    color: colorScheme.primary,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const Spacer(),
                // Dismiss (X) button.
                IconButton(
                  icon: const Icon(Icons.close, size: 18),
                  onPressed: onDismiss,
                  tooltip: 'Dismiss',
                ),
              ],
            ),
            const SizedBox(height: 8),

            // Body: loading, error, or event details.
            if (isExtracting) _buildLoading(context),
            if (!isExtracting && extractionError != null)
              _buildError(context, extractionError!),
            if (!isExtracting &&
                extractionError == null &&
                extractedEvent != null)
              _buildEventDetails(context, extractedEvent!),

            // Action buttons.
            if (!isExtracting && extractedEvent != null) ...[
              const SizedBox(height: 12),
              _buildActions(context),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildLoading(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.symmetric(vertical: 12),
      child: Row(
        children: [
          SizedBox(
            width: 16,
            height: 16,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
          SizedBox(width: 12),
          Text('Extracting event details...'),
        ],
      ),
    );
  }

  Widget _buildError(BuildContext context, String error) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Text(
        'Could not extract event details: $error',
        style: TextStyle(
          color: Theme.of(context).colorScheme.error,
          fontSize: 13,
        ),
      ),
    );
  }

  Widget _buildEventDetails(BuildContext context, ExtractedEvent event) {
    final theme = Theme.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Event title.
        Text(
          event.title,
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 4),

        // Date row.
        Row(
          children: [
            Icon(
              Icons.calendar_today,
              size: 14,
              color: theme.colorScheme.onSurfaceVariant,
            ),
            const SizedBox(width: 6),
            Text(
              _formatDate(event.startTime.toLocal()),
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
        const SizedBox(height: 2),

        // Time row.
        Row(
          children: [
            Icon(
              Icons.access_time,
              size: 14,
              color: theme.colorScheme.onSurfaceVariant,
            ),
            const SizedBox(width: 6),
            Text(
              event.endTime != null
                  ? '${_formatTime(event.startTime.toLocal())} – '
                        '${_formatTime(event.endTime!.toLocal())}'
                  : _formatTime(event.startTime.toLocal()),
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),

        // Past time warning.
        if (event.isPastTime) ...[
          const SizedBox(height: 8),
          Row(
            children: [
              Icon(
                Icons.warning_amber_rounded,
                size: 14,
                color: theme.colorScheme.error,
              ),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  'This time is in the past',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.error,
                  ),
                ),
              ),
            ],
          ),
        ],
      ],
    );
  }

  /// Format a date as "Wednesday, Feb 25, 2026".
  static String _formatDate(DateTime dt) {
    const weekdays = [
      'Monday',
      'Tuesday',
      'Wednesday',
      'Thursday',
      'Friday',
      'Saturday',
      'Sunday',
    ];
    const months = [
      'Jan',
      'Feb',
      'Mar',
      'Apr',
      'May',
      'Jun',
      'Jul',
      'Aug',
      'Sep',
      'Oct',
      'Nov',
      'Dec',
    ];
    return '${weekdays[dt.weekday - 1]}, ${months[dt.month - 1]} ${dt.day}, ${dt.year}';
  }

  /// Format a time as "3:00 PM".
  static String _formatTime(DateTime dt) {
    final hour = dt.hour > 12
        ? dt.hour - 12
        : dt.hour == 0
        ? 12
        : dt.hour;
    final minute = dt.minute.toString().padLeft(2, '0');
    final amPm = dt.hour >= 12 ? 'PM' : 'AM';
    return '$hour:$minute $amPm';
  }

  /// Test access to [_formatDate].
  @visibleForTesting
  static String formatDateForTest(DateTime dt) => _formatDate(dt);

  /// Test access to [_formatTime].
  @visibleForTesting
  static String formatTimeForTest(DateTime dt) => _formatTime(dt);

  Widget _buildActions(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.end,
      children: [
        // Dismiss button.
        TextButton(onPressed: onDismiss, child: const Text('Dismiss')),
        const SizedBox(width: 8),

        // Add to Calendar or Connect button.
        if (isGoogleConnected)
          FilledButton.icon(
            onPressed: onConfirm,
            icon: Icon(isReminder ? Icons.alarm_add : Icons.event_available),
            label: const Text('Add to Calendar'),
          )
        else
          OutlinedButton.icon(
            onPressed: onConnect,
            icon: const Icon(Icons.link),
            label: const Text('Connect Google Calendar'),
          ),
      ],
    );
  }
}
