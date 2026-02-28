// ===========================================================================
// file: lib/ui/screens/tasks_screen.dart
// purpose: Dedicated Tasks screen accessible from the home screen icon bar.
//
// Features:
//   - Segmented control: Active / Completed
//   - List of TaskItemWidgets from reactive streams
//   - Add task form (title + optional date picker)
//   - Empty state
//
// See: Phase 13 plan (Google Tasks + Personal Assistant)
// ===========================================================================

import 'package:drift/drift.dart' hide Column;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../database/app_database.dart';
import '../../database/daos/task_dao.dart';
import '../../providers/calendar_providers.dart';
import '../../providers/database_provider.dart';
import '../../providers/task_providers.dart';
import '../../services/google_tasks_service.dart';
import '../../utils/uuid_generator.dart';
import '../widgets/task_item.dart';

/// Dedicated screen for managing tasks.
class TasksScreen extends ConsumerStatefulWidget {
  const TasksScreen({super.key});

  @override
  ConsumerState<TasksScreen> createState() => _TasksScreenState();
}

class _TasksScreenState extends ConsumerState<TasksScreen> {
  /// 0 = Active, 1 = Completed.
  int _selectedSegment = 0;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Tasks'),
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            tooltip: 'Add task',
            onPressed: () => _showAddTaskDialog(context),
          ),
        ],
      ),
      body: Column(
        children: [
          // Segmented control.
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: SegmentedButton<int>(
              segments: const [
                ButtonSegment(value: 0, label: Text('Active')),
                ButtonSegment(value: 1, label: Text('Completed')),
              ],
              selected: {_selectedSegment},
              onSelectionChanged: (selection) {
                setState(() => _selectedSegment = selection.first);
              },
              style: SegmentedButton.styleFrom(
                selectedBackgroundColor: theme.colorScheme.primaryContainer,
              ),
            ),
          ),

          // Task list.
          Expanded(
            child: _selectedSegment == 0
                ? _ActiveTasksList()
                : _CompletedTasksList(),
          ),
        ],
      ),
    );
  }

  /// Show the add task bottom sheet.
  void _showAddTaskDialog(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (context) => _AddTaskSheet(),
    );
  }
}

/// Active tasks list.
class _ActiveTasksList extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tasksAsync = ref.watch(activeTasksStreamProvider);

    return tasksAsync.when(
      data: (tasks) {
        if (tasks.isEmpty) {
          return _buildEmptyState(
            context,
            'No active tasks',
            'Tap + to add your first task.',
          );
        }
        return ListView.builder(
          itemCount: tasks.length,
          itemBuilder: (context, index) {
            final task = tasks[index] as Task;
            return TaskItemWidget(
              task: task,
              onToggleComplete: (completed) =>
                  _toggleComplete(ref, task, completed),
              onDelete: () => _deleteTask(ref, task),
              onEdit: () => _showEditDialog(context, ref, task),
            );
          },
        );
      },
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('Error: $e')),
    );
  }

  Widget _buildEmptyState(BuildContext context, String title, String subtitle) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.task_alt_outlined,
              size: 64,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
            const SizedBox(height: 16),
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text(
              subtitle,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _toggleComplete(WidgetRef ref, Task task, bool completed) async {
    final taskDao = ref.read(taskDaoProvider);
    if (completed) {
      await taskDao.completeTask(task.taskId, DateTime.now().toUtc());
      // Sync completion to Google Tasks if connected.
      await _syncTaskCompletion(ref, task);
    } else {
      await taskDao.uncompleteTask(task.taskId);
    }
    ref.invalidate(taskCountProvider);
  }

  Future<void> _syncTaskCompletion(WidgetRef ref, Task task) async {
    if (task.googleTaskId == null || task.googleTaskListId == null) return;
    final isConnected = ref.read(isGoogleConnectedProvider);
    if (!isConnected) return;

    try {
      final authService = ref.read(googleAuthServiceProvider);
      final authClient = await authService.getAuthClient();
      if (authClient == null) return;

      final tasksService = GoogleTasksService.withClient(authClient);
      await tasksService.completeTask(
        googleTaskId: task.googleTaskId!,
        taskListId: task.googleTaskListId!,
      );

      final taskDao = ref.read(taskDaoProvider);
      await taskDao.updateSyncStatus(task.taskId, TaskSyncStatus.synced);
    } on Exception {
      // Sync failure is non-blocking — task is already completed locally.
    }
  }

  Future<void> _deleteTask(WidgetRef ref, Task task) async {
    final taskDao = ref.read(taskDaoProvider);

    // Delete from Google Tasks if synced.
    if (task.googleTaskId != null && task.googleTaskListId != null) {
      final isConnected = ref.read(isGoogleConnectedProvider);
      if (isConnected) {
        try {
          final authService = ref.read(googleAuthServiceProvider);
          final authClient = await authService.getAuthClient();
          if (authClient != null) {
            final tasksService = GoogleTasksService.withClient(authClient);
            await tasksService.deleteTask(
              googleTaskId: task.googleTaskId!,
              taskListId: task.googleTaskListId!,
            );
          }
        } on Exception {
          // Delete failure is non-blocking.
        }
      }
    }

    await taskDao.deleteTask(task.taskId);
    ref.invalidate(taskCountProvider);
  }

  void _showEditDialog(BuildContext context, WidgetRef ref, Task task) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (context) => _EditTaskSheet(task: task),
    );
  }
}

/// Completed tasks list.
class _CompletedTasksList extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tasksAsync = ref.watch(completedTasksStreamProvider);

    return tasksAsync.when(
      data: (tasks) {
        if (tasks.isEmpty) {
          return Center(
            child: Text(
              'No completed tasks yet.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          );
        }
        return ListView.builder(
          itemCount: tasks.length,
          itemBuilder: (context, index) {
            final task = tasks[index] as Task;
            return TaskItemWidget(
              task: task,
              onToggleComplete: (completed) async {
                final taskDao = ref.read(taskDaoProvider);
                if (!completed) {
                  await taskDao.uncompleteTask(task.taskId);
                }
                ref.invalidate(taskCountProvider);
              },
              onDelete: () async {
                final taskDao = ref.read(taskDaoProvider);
                await taskDao.deleteTask(task.taskId);
                ref.invalidate(taskCountProvider);
              },
            );
          },
        );
      },
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('Error: $e')),
    );
  }
}

/// Bottom sheet for adding a new task.
class _AddTaskSheet extends ConsumerStatefulWidget {
  @override
  ConsumerState<_AddTaskSheet> createState() => _AddTaskSheetState();
}

class _AddTaskSheetState extends ConsumerState<_AddTaskSheet> {
  final _titleController = TextEditingController();
  final _notesController = TextEditingController();
  DateTime? _dueDate;
  bool _isSubmitting = false;

  @override
  void dispose() {
    _titleController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Padding(
      padding: EdgeInsets.only(
        left: 16,
        right: 16,
        top: 16,
        bottom: MediaQuery.of(context).viewInsets.bottom + 16,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('New Task', style: theme.textTheme.titleLarge),
          const SizedBox(height: 16),
          TextField(
            controller: _titleController,
            decoration: const InputDecoration(
              labelText: 'Task title',
              border: OutlineInputBorder(),
            ),
            autofocus: true,
            textCapitalization: TextCapitalization.sentences,
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _notesController,
            decoration: const InputDecoration(
              labelText: 'Notes (optional)',
              border: OutlineInputBorder(),
            ),
            maxLines: 2,
            textCapitalization: TextCapitalization.sentences,
          ),
          const SizedBox(height: 12),
          OutlinedButton.icon(
            onPressed: _pickDueDate,
            icon: const Icon(Icons.calendar_today, size: 18),
            label: Text(
              _dueDate != null ? _formatDate(_dueDate!) : 'Add due date',
            ),
          ),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: _isSubmitting ? null : _submit,
            child: _isSubmitting
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('Add Task'),
          ),
        ],
      ),
    );
  }

  Future<void> _pickDueDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _dueDate ?? DateTime.now(),
      firstDate: DateTime.now().subtract(const Duration(days: 1)),
      lastDate: DateTime.now().add(const Duration(days: 730)),
    );
    if (picked != null) {
      setState(() => _dueDate = picked);
    }
  }

  Future<void> _submit() async {
    final title = _titleController.text.trim();
    if (title.isEmpty) return;

    setState(() => _isSubmitting = true);

    final taskDao = ref.read(taskDaoProvider);
    final taskId = generateUuid();
    final notes = _notesController.text.trim();

    await taskDao.insertTask(
      TasksCompanion(
        taskId: Value(taskId),
        title: Value(title),
        notes: notes.isNotEmpty ? Value(notes) : const Value.absent(),
        dueDate: _dueDate != null ? Value(_dueDate!) : const Value.absent(),
        status: const Value(TaskStatus.active),
        syncStatus: const Value(TaskSyncStatus.pending),
        createdAt: Value(DateTime.now().toUtc()),
        updatedAt: Value(DateTime.now().toUtc()),
      ),
    );

    // Sync to Google Tasks if connected.
    final isConnected = ref.read(isGoogleConnectedProvider);
    if (isConnected) {
      try {
        final authService = ref.read(googleAuthServiceProvider);
        final authClient = await authService.getAuthClient();
        if (authClient != null) {
          final tasksService = GoogleTasksService.withClient(authClient);
          final result = await tasksService.createTask(
            title: title,
            notes: notes.isNotEmpty ? notes : null,
            dueDate: _dueDate,
          );
          await taskDao.updateGoogleTaskId(
            taskId,
            result.googleTaskId,
            result.googleTaskListId,
          );
        }
      } on Exception {
        // Sync failure is non-blocking.
      }
    }

    ref.invalidate(taskCountProvider);

    if (mounted) {
      Navigator.of(context).pop();
    }
  }

  String _formatDate(DateTime dt) {
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
    return '${months[dt.month - 1]} ${dt.day}, ${dt.year}';
  }
}

/// Bottom sheet for editing an existing task.
class _EditTaskSheet extends ConsumerStatefulWidget {
  final Task task;

  const _EditTaskSheet({required this.task});

  @override
  ConsumerState<_EditTaskSheet> createState() => _EditTaskSheetState();
}

class _EditTaskSheetState extends ConsumerState<_EditTaskSheet> {
  late final TextEditingController _titleController;
  late final TextEditingController _notesController;
  DateTime? _dueDate;
  bool _isSubmitting = false;

  @override
  void initState() {
    super.initState();
    _titleController = TextEditingController(text: widget.task.title);
    _notesController = TextEditingController(text: widget.task.notes ?? '');
    _dueDate = widget.task.dueDate;
  }

  @override
  void dispose() {
    _titleController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Padding(
      padding: EdgeInsets.only(
        left: 16,
        right: 16,
        top: 16,
        bottom: MediaQuery.of(context).viewInsets.bottom + 16,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('Edit Task', style: theme.textTheme.titleLarge),
          const SizedBox(height: 16),
          TextField(
            controller: _titleController,
            decoration: const InputDecoration(
              labelText: 'Task title',
              border: OutlineInputBorder(),
            ),
            textCapitalization: TextCapitalization.sentences,
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _notesController,
            decoration: const InputDecoration(
              labelText: 'Notes (optional)',
              border: OutlineInputBorder(),
            ),
            maxLines: 2,
            textCapitalization: TextCapitalization.sentences,
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _pickDueDate,
                  icon: const Icon(Icons.calendar_today, size: 18),
                  label: Text(
                    _dueDate != null ? _formatDate(_dueDate!) : 'Add due date',
                  ),
                ),
              ),
              if (_dueDate != null) ...[
                const SizedBox(width: 8),
                IconButton(
                  icon: const Icon(Icons.clear, size: 18),
                  onPressed: () => setState(() => _dueDate = null),
                  tooltip: 'Remove due date',
                ),
              ],
            ],
          ),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: _isSubmitting ? null : _save,
            child: _isSubmitting
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('Save'),
          ),
        ],
      ),
    );
  }

  Future<void> _pickDueDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _dueDate ?? DateTime.now(),
      firstDate: DateTime.now().subtract(const Duration(days: 1)),
      lastDate: DateTime.now().add(const Duration(days: 730)),
    );
    if (picked != null) {
      setState(() => _dueDate = picked);
    }
  }

  Future<void> _save() async {
    final title = _titleController.text.trim();
    if (title.isEmpty) return;

    setState(() => _isSubmitting = true);

    final taskDao = ref.read(taskDaoProvider);
    final notes = _notesController.text.trim();

    await taskDao.updateTask(
      widget.task.taskId,
      TasksCompanion(
        title: Value(title),
        notes: Value(notes.isNotEmpty ? notes : null),
        dueDate: Value(_dueDate),
        syncStatus: const Value(TaskSyncStatus.pending),
        updatedAt: Value(DateTime.now().toUtc()),
      ),
    );

    // Sync update to Google Tasks if connected and synced.
    if (widget.task.googleTaskId != null &&
        widget.task.googleTaskListId != null) {
      final isConnected = ref.read(isGoogleConnectedProvider);
      if (isConnected) {
        try {
          final authService = ref.read(googleAuthServiceProvider);
          final authClient = await authService.getAuthClient();
          if (authClient != null) {
            final tasksService = GoogleTasksService.withClient(authClient);
            await tasksService.updateTask(
              googleTaskId: widget.task.googleTaskId!,
              taskListId: widget.task.googleTaskListId!,
              title: title,
              notes: notes.isNotEmpty ? notes : null,
              dueDate: _dueDate,
            );
            await taskDao.updateSyncStatus(
              widget.task.taskId,
              TaskSyncStatus.synced,
            );
          }
        } on Exception {
          // Sync failure is non-blocking.
        }
      }
    }

    ref.invalidate(taskCountProvider);

    if (mounted) {
      Navigator.of(context).pop();
    }
  }

  String _formatDate(DateTime dt) {
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
    return '${months[dt.month - 1]} ${dt.day}, ${dt.year}';
  }
}
