// ===========================================================================
// file: lib/ui/widgets/task_item.dart
// purpose: Individual task row for the Tasks screen.
//
// Shows a checkbox, title, due date chip, reminder time chip, and
// swipe-to-delete. Tapping toggles completion.
//
// Due date color-coding:
//   overdue = red, today = orange, future = default, none = grey.
//
// Reminder time: shown with alarm icon when task.reminderTime != null.
//   upcoming = primary color, past = onSurfaceVariant.
//
// See: Phase 13 plan (Google Tasks + Personal Assistant),
//      SPEC-20260304-061650 (Scheduled Local Notifications)
// ===========================================================================

import 'package:flutter/material.dart';

import '../../database/app_database.dart';
import '../../database/daos/task_dao.dart';

/// A single task row in the Tasks screen list.
class TaskItemWidget extends StatelessWidget {
  /// The task data.
  final Task task;

  /// Called when the user toggles the completion checkbox.
  final ValueChanged<bool> onToggleComplete;

  /// Called when the user swipes to delete.
  final VoidCallback onDelete;

  /// Called when the user taps to edit.
  final VoidCallback? onEdit;

  /// Create a [TaskItemWidget].
  const TaskItemWidget({
    super.key,
    required this.task,
    required this.onToggleComplete,
    required this.onDelete,
    this.onEdit,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isCompleted = task.status == TaskStatus.completed;

    return Dismissible(
      key: Key(task.taskId),
      direction: DismissDirection.endToStart,
      background: Container(
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.symmetric(horizontal: 20),
        color: theme.colorScheme.error,
        child: Icon(Icons.delete, color: theme.colorScheme.onError),
      ),
      onDismissed: (_) => onDelete(),
      child: ListTile(
        leading: Checkbox(
          value: isCompleted,
          onChanged: (value) => onToggleComplete(value ?? false),
        ),
        title: Text(
          task.title,
          style: theme.textTheme.bodyLarge?.copyWith(
            decoration: isCompleted
                ? TextDecoration.lineThrough
                : TextDecoration.none,
            color: isCompleted
                ? theme.colorScheme.onSurfaceVariant
                : theme.colorScheme.onSurface,
          ),
        ),
        subtitle: _buildSubtitle(task, isCompleted),
        trailing: task.notes != null && task.notes!.isNotEmpty
            ? Icon(
                Icons.notes,
                size: 16,
                color: theme.colorScheme.onSurfaceVariant,
              )
            : null,
        onTap: onEdit,
      ),
    );
  }

  Widget? _buildSubtitle(Task task, bool isCompleted) {
    final hasDueDate = task.dueDate != null;
    final hasReminder = task.reminderTime != null;

    if (!hasDueDate && !hasReminder) return null;

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        if (hasDueDate)
          _DueDateChip(dueDate: task.dueDate!, isCompleted: isCompleted),
        if (hasDueDate && hasReminder) const SizedBox(width: 8),
        if (hasReminder)
          _ReminderTimeChip(
            reminderTime: task.reminderTime!,
            isCompleted: isCompleted,
          ),
      ],
    );
  }
}

/// Color-coded due date chip.
class _DueDateChip extends StatelessWidget {
  final DateTime dueDate;
  final bool isCompleted;

  const _DueDateChip({required this.dueDate, required this.isCompleted});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final dueDateLocal = dueDate.toLocal();
    final dueDay = DateTime(
      dueDateLocal.year,
      dueDateLocal.month,
      dueDateLocal.day,
    );

    Color chipColor;
    String label;

    if (isCompleted) {
      chipColor = theme.colorScheme.onSurfaceVariant;
      label = _formatShortDate(dueDateLocal);
    } else if (dueDay.isBefore(today)) {
      chipColor = theme.colorScheme.error;
      label = 'Overdue - ${_formatShortDate(dueDateLocal)}';
    } else if (dueDay.isAtSameMomentAs(today)) {
      chipColor = Colors.orange;
      label = 'Due today';
    } else if (dueDay.isAtSameMomentAs(today.add(const Duration(days: 1)))) {
      chipColor = theme.colorScheme.primary;
      label = 'Due tomorrow';
    } else {
      chipColor = theme.colorScheme.onSurfaceVariant;
      label = _formatShortDate(dueDateLocal);
    }

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(Icons.calendar_today, size: 12, color: chipColor),
        const SizedBox(width: 4),
        Text(
          label,
          style: theme.textTheme.bodySmall?.copyWith(color: chipColor),
        ),
      ],
    );
  }

  static String _formatShortDate(DateTime dt) {
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
    return '${months[dt.month - 1]} ${dt.day}';
  }
}

/// Scheduled alarm chip shown when a task has a [reminderTime].
///
/// Shows the alarm icon and formatted time. Color is primary for upcoming
/// reminders and onSurfaceVariant for past or completed tasks.
class _ReminderTimeChip extends StatelessWidget {
  final DateTime reminderTime;
  final bool isCompleted;

  const _ReminderTimeChip({
    required this.reminderTime,
    required this.isCompleted,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final localTime = reminderTime.toLocal();
    final isPast = localTime.isBefore(DateTime.now());

    final color = isCompleted || isPast
        ? theme.colorScheme.onSurfaceVariant
        : theme.colorScheme.primary;

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(Icons.alarm, size: 12, color: color),
        const SizedBox(width: 4),
        Text(
          _formatTime(localTime),
          style: theme.textTheme.bodySmall?.copyWith(color: color),
        ),
      ],
    );
  }

  /// Format reminder time as "3:47pm" (today) or "Mar 5 3:47pm" (other days).
  static String _formatTime(DateTime dt) {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final reminderDay = DateTime(dt.year, dt.month, dt.day);
    final isToday = reminderDay.isAtSameMomentAs(today);

    final hour = dt.hour;
    final minute = dt.minute;
    final period = hour >= 12 ? 'pm' : 'am';
    final h = hour > 12 ? hour - 12 : (hour == 0 ? 12 : hour);
    final m = minute.toString().padLeft(2, '0');
    final time = minute == 0 ? '$h$period' : '$h:$m$period';

    if (isToday) return time;

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
    return '${months[dt.month - 1]} ${dt.day} $time';
  }
}
