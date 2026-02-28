// ===========================================================================
// file: lib/ui/widgets/calendar_event_edit_dialog.dart
// purpose: Bottom sheet dialog for editing confirmed calendar events.
//
// Allows editing title, date, and time of app-created calendar events.
// Syncs changes to Google Calendar via GoogleCalendarService.updateEvent().
//
// See: Phase 13 plan (Google Tasks + Personal Assistant)
// ===========================================================================

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../database/app_database.dart';
import '../../providers/calendar_providers.dart';
import '../../providers/database_provider.dart';
import '../../services/google_calendar_service.dart';

/// Shows a bottom sheet for editing a confirmed calendar event.
Future<void> showCalendarEventEditDialog(
  BuildContext context,
  CalendarEvent event,
) {
  return showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    builder: (context) => _CalendarEventEditSheet(event: event),
  );
}

class _CalendarEventEditSheet extends ConsumerStatefulWidget {
  final CalendarEvent event;

  const _CalendarEventEditSheet({required this.event});

  @override
  ConsumerState<_CalendarEventEditSheet> createState() =>
      _CalendarEventEditSheetState();
}

class _CalendarEventEditSheetState
    extends ConsumerState<_CalendarEventEditSheet> {
  late final TextEditingController _titleController;
  late DateTime _startDate;
  late TimeOfDay _startTime;
  late TimeOfDay _endTime;
  bool _isSubmitting = false;

  @override
  void initState() {
    super.initState();
    _titleController = TextEditingController(text: widget.event.title);
    final localStart = widget.event.startTime.toLocal();
    _startDate = DateTime(localStart.year, localStart.month, localStart.day);
    _startTime = TimeOfDay.fromDateTime(localStart);
    if (widget.event.endTime != null) {
      _endTime = TimeOfDay.fromDateTime(widget.event.endTime!.toLocal());
    } else {
      _endTime = TimeOfDay(
        hour: (_startTime.hour + 1) % 24,
        minute: _startTime.minute,
      );
    }
  }

  @override
  void dispose() {
    _titleController.dispose();
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
          Text('Edit Event', style: theme.textTheme.titleLarge),
          const SizedBox(height: 16),
          TextField(
            controller: _titleController,
            decoration: const InputDecoration(
              labelText: 'Title',
              border: OutlineInputBorder(),
            ),
            textCapitalization: TextCapitalization.sentences,
          ),
          const SizedBox(height: 12),
          OutlinedButton.icon(
            onPressed: _pickDate,
            icon: const Icon(Icons.calendar_today, size: 18),
            label: Text(_formatDate(_startDate)),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _pickStartTime,
                  icon: const Icon(Icons.access_time, size: 18),
                  label: Text('Start: ${_startTime.format(context)}'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _pickEndTime,
                  icon: const Icon(Icons.access_time, size: 18),
                  label: Text('End: ${_endTime.format(context)}'),
                ),
              ),
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

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _startDate,
      firstDate: DateTime.now().subtract(const Duration(days: 1)),
      lastDate: DateTime.now().add(const Duration(days: 730)),
    );
    if (picked != null) {
      setState(() => _startDate = picked);
    }
  }

  Future<void> _pickStartTime() async {
    final picked = await showTimePicker(
      context: context,
      initialTime: _startTime,
    );
    if (picked != null) {
      setState(() => _startTime = picked);
    }
  }

  Future<void> _pickEndTime() async {
    final picked = await showTimePicker(
      context: context,
      initialTime: _endTime,
    );
    if (picked != null) {
      setState(() => _endTime = picked);
    }
  }

  Future<void> _save() async {
    final title = _titleController.text.trim();
    if (title.isEmpty) return;

    setState(() => _isSubmitting = true);

    final calendarEventDao = ref.read(calendarEventDaoProvider);

    final newStartTime = DateTime(
      _startDate.year,
      _startDate.month,
      _startDate.day,
      _startTime.hour,
      _startTime.minute,
    ).toUtc();

    final newEndTime = DateTime(
      _startDate.year,
      _startDate.month,
      _startDate.day,
      _endTime.hour,
      _endTime.minute,
    ).toUtc();

    // Update local database.
    await calendarEventDao.updateEventDetails(
      widget.event.eventId,
      title: title,
      startTime: newStartTime,
      endTime: newEndTime,
    );

    // Sync to Google Calendar if the event is confirmed.
    if (widget.event.googleEventId != null) {
      final isConnected = ref.read(isGoogleConnectedProvider);
      if (isConnected) {
        try {
          final authService = ref.read(googleAuthServiceProvider);
          final authClient = await authService.getAuthClient();
          if (authClient != null) {
            final calendarService = GoogleCalendarService.withClient(
              authClient,
            );
            await calendarService.updateEvent(
              googleEventId: widget.event.googleEventId!,
              title: title,
              startTime: newStartTime,
              endTime: newEndTime,
            );
          }
        } on CalendarServiceException {
          // Update failure is non-blocking — local state is already updated.
        }
      }
    }

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
