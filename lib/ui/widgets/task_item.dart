// ===========================================================================
// file: lib/ui/widgets/task_item.dart
// purpose: Individual task row for the Tasks screen.
//
// Shows a checkbox, title, due date chip, and swipe-to-delete.
// Tapping toggles completion. Due date is color-coded:
//   overdue = red, today = orange, future = default, none = grey.
//
// See: Phase 13 plan (Google Tasks + Personal Assistant)
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
        subtitle: task.dueDate != null
            ? _DueDateChip(dueDate: task.dueDate!, isCompleted: isCompleted)
            : null,
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
