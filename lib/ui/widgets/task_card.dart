// ===========================================================================
// file: lib/ui/widgets/task_card.dart
// purpose: Inline confirmation card for task creation from conversation.
//
// Shown in the journal session screen when the intent classifier detects
// a task intent. Displays extracted task details and action buttons for
// confirm/dismiss. Follows CalendarEventCard pattern.
//
// See: Phase 13 plan (Google Tasks + Personal Assistant)
// ===========================================================================

import 'package:flutter/material.dart';

import '../../services/task_extraction_service.dart';

/// Inline confirmation card for a pending task.
class TaskCard extends StatelessWidget {
  /// The extracted task details (null while extracting).
  final ExtractedTask? extractedTask;

  /// Whether extraction is in progress.
  final bool isExtracting;

  /// Error message if extraction failed.
  final String? extractionError;

  /// Called when the user taps "Add to Tasks".
  final VoidCallback onConfirm;

  /// Called when the user taps "Dismiss".
  final VoidCallback onDismiss;

  /// Create a [TaskCard].
  const TaskCard({
    super.key,
    this.extractedTask,
    this.isExtracting = false,
    this.extractionError,
    required this.onConfirm,
    required this.onDismiss,
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
        side: BorderSide(color: colorScheme.tertiary.withValues(alpha: 0.3)),
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
                Icon(Icons.task_alt, color: colorScheme.tertiary, size: 20),
                const SizedBox(width: 8),
                Text(
                  'Task',
                  style: theme.textTheme.titleSmall?.copyWith(
                    color: colorScheme.tertiary,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const Spacer(),
                IconButton(
                  icon: const Icon(Icons.close, size: 18),
                  onPressed: onDismiss,
                  tooltip: 'Dismiss',
                ),
              ],
            ),
            const SizedBox(height: 8),

            // Body: loading, error, or task details.
            if (isExtracting) _buildLoading(context),
            if (!isExtracting && extractionError != null)
              _buildError(context, extractionError!),
            if (!isExtracting &&
                extractionError == null &&
                extractedTask != null)
              _buildTaskDetails(context, extractedTask!),

            // Action buttons.
            if (!isExtracting && extractedTask != null) ...[
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
          Text('Extracting task details...'),
        ],
      ),
    );
  }

  Widget _buildError(BuildContext context, String error) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Text(
        'Could not extract task details: $error',
        style: TextStyle(
          color: Theme.of(context).colorScheme.error,
          fontSize: 13,
        ),
      ),
    );
  }

  Widget _buildTaskDetails(BuildContext context, ExtractedTask task) {
    final theme = Theme.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Task title.
        Text(
          task.title,
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w600,
          ),
        ),

        // Due date (if any).
        if (task.dueDate != null) ...[
          const SizedBox(height: 4),
          Row(
            children: [
              Icon(
                Icons.calendar_today,
                size: 14,
                color: theme.colorScheme.onSurfaceVariant,
              ),
              const SizedBox(width: 6),
              Text(
                _formatDate(task.dueDate!.toLocal()),
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ],

        // Notes (if any).
        if (task.notes != null) ...[
          const SizedBox(height: 4),
          Text(
            task.notes!,
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ],
    );
  }

  Widget _buildActions(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.end,
      children: [
        TextButton(onPressed: onDismiss, child: const Text('Dismiss')),
        const SizedBox(width: 8),
        FilledButton.icon(
          onPressed: onConfirm,
          icon: const Icon(Icons.add_task),
          label: const Text('Add to Tasks'),
        ),
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
}
