// ===========================================================================
// file: lib/services/task_extraction_service.dart
// purpose: Extract structured task details from natural language.
//
// Two-layer strategy matching EventExtractionService:
//   Layer A (rule-based): Basic regex extraction of task title and due date.
//   Layer B (LLM): ClaudeApiService call requesting JSON output for title,
//     due_date, and notes.
//
// Validation:
//   - Title: non-empty, max 200 characters
//   - Due date: valid ISO 8601, within sane range (not before yesterday,
//     not after 2 years from now)
//
// See: Phase 13 plan (Google Tasks + Personal Assistant)
// ===========================================================================

import 'dart:convert';

import 'package:flutter/foundation.dart';

import 'claude_api_service.dart';

/// Extracted task details from a user message.
class ExtractedTask {
  /// Task title (non-empty, max 200 chars).
  final String title;

  /// Due date (nullable — many tasks are open-ended).
  ///
  /// Date-level precision only. For notification scheduling, use
  /// [reminderTime] which carries the full date-time when the user
  /// supplied an explicit time ("at 4pm", "in an hour", etc.).
  final DateTime? dueDate;

  /// Exact date-time at which a notification should fire (nullable).
  ///
  /// Set when the user specifies a time component ("at 4pm",
  /// "in an hour", "tomorrow morning"). Null for date-only or open-ended
  /// tasks. When non-null, [dueDate] is also set to the date portion.
  final DateTime? reminderTime;

  /// Optional notes/details.
  final String? notes;

  /// Create an [ExtractedTask].
  const ExtractedTask({
    required this.title,
    this.dueDate,
    this.reminderTime,
    this.notes,
  });
}

/// Sealed result type for task extraction.
sealed class TaskExtractionResult {
  /// Whether extraction succeeded.
  bool get isSuccess;
}

/// Successful task extraction.
class TaskExtractionSuccess implements TaskExtractionResult {
  /// The extracted task details.
  final ExtractedTask task;

  /// Create a success result.
  const TaskExtractionSuccess(this.task);

  @override
  bool get isSuccess => true;
}

/// Failed task extraction.
class TaskExtractionFailure implements TaskExtractionResult {
  /// Human-readable error message.
  final String reason;

  /// Create a failure result.
  const TaskExtractionFailure(this.reason);

  @override
  bool get isSuccess => false;
}

/// Service for extracting structured task details from natural language.
class TaskExtractionService {
  final ClaudeApiService? _claudeApi;

  /// Create a TaskExtractionService.
  ///
  /// [claudeApi] — provide for LLM-powered extraction. When null or
  /// not configured, falls back to regex extraction.
  TaskExtractionService({ClaudeApiService? claudeApi}) : _claudeApi = claudeApi;

  /// Extract task details from a user message.
  ///
  /// [context] — optional conversation history (up to 3 prior turns as
  /// `{role, content}` maps) used to resolve pronouns and implicit references.
  Future<TaskExtractionResult> extract(
    String message,
    DateTime now, {
    String? timezone,
    List<Map<String, String>>? context,
  }) async {
    if (_claudeApi != null && _claudeApi.isConfigured) {
      return _extractWithLlm(
        message,
        now,
        timezone: timezone,
        context: context,
      );
    }
    return _extractWithRegex(message, now);
  }

  // =========================================================================
  // Layer B: LLM extraction
  // =========================================================================

  Future<TaskExtractionResult> _extractWithLlm(
    String message,
    DateTime now, {
    String? timezone,
    List<Map<String, String>>? context,
  }) async {
    try {
      final localNow = now.toLocal();
      final isoLocal = localNow.toIso8601String();
      final tz = _sanitizeTimezone(timezone ?? localNow.timeZoneName);

      // Build conversation history block to help the LLM resolve pronouns.
      final contextBlock = (context != null && context.isNotEmpty)
          ? 'Conversation history:\n${context.map((m) => '[${m['role']?.toUpperCase() ?? 'UNKNOWN'}]: ${m['content'] ?? ''}').join('\n')}\n\n'
          : '';

      final prompt =
          '''Extract task details from this message. '''
          '''The current local date/time is $isoLocal (timezone: $tz).

${contextBlock}Message: "$message"

Respond with ONLY a JSON object (no markdown, no explanation):
{"title": "task title", "due_date": "ISO 8601 date or null", "reminder_time": "ISO 8601 datetime or null", "notes": "additional details or null"}

Rules:
- title: concise task name (not the full sentence). Remove action verbs like "add a task to", "create a task", "remind me to", "set a reminder to". Use conversation history to resolve pronouns like "it" or "that".
- due_date: null if not specified. Resolve relative dates ("tomorrow", "next Friday") to absolute ISO 8601 date (date only, no time).
- reminder_time: null if no specific time is mentioned. When the message contains an explicit time ("at 4pm", "in an hour", "in 30 minutes", "tomorrow morning", "tonight"), set this to the absolute ISO 8601 datetime (date + time). "in an hour" = current time + 1 hour. "tomorrow morning" = tomorrow at 09:00. "tonight" = today at 20:00.
- notes: null if no additional details beyond the title.''';

      final response = await _claudeApi!.chat(
        messages: [
          {'role': 'user', 'content': prompt},
        ],
      );

      return _parseAndValidateLlmResponse(response, now);
    } on ClaudeApiException catch (e) {
      if (kDebugMode) {
        debugPrint('LLM task extraction failed: $e — falling back to regex');
      }
      return _extractWithRegex(message, now);
    }
  }

  TaskExtractionResult _parseAndValidateLlmResponse(
    String response,
    DateTime now,
  ) {
    final cleaned = response
        .replaceAll(RegExp(r'^```json?\s*', multiLine: true), '')
        .replaceAll(RegExp(r'```\s*$', multiLine: true), '')
        .trim();

    Map<String, dynamic> json;
    try {
      final decoded = jsonDecode(cleaned);
      if (decoded is! Map<String, dynamic>) {
        return const TaskExtractionFailure('LLM response is not a JSON object');
      }
      json = decoded;
    } on FormatException {
      return const TaskExtractionFailure('LLM returned invalid JSON');
    }

    // --- Title validation ---
    final rawTitle = json['title'];
    if (rawTitle is! String || rawTitle.trim().isEmpty) {
      return const TaskExtractionFailure('Missing or empty title');
    }
    final title = rawTitle.trim().length > 200
        ? rawTitle.trim().substring(0, 200)
        : rawTitle.trim();

    // --- Due date validation (optional) ---
    DateTime? dueDate;
    final rawDue = json['due_date'];
    if (rawDue is String && rawDue.toLowerCase() != 'null') {
      try {
        dueDate = DateTime.parse(rawDue).toUtc();
        // Sane range check.
        final lowerBound = now.subtract(const Duration(days: 1));
        final upperBound = now.add(const Duration(days: 730));
        if (dueDate.isBefore(lowerBound) || dueDate.isAfter(upperBound)) {
          dueDate = null; // Out of range — ignore, don't fail.
        }
      } on FormatException {
        dueDate = null; // Invalid format — ignore, don't fail.
      }
    }

    // --- Notes (optional) ---
    final rawNotes = json['notes'];
    final notes =
        (rawNotes is String &&
            rawNotes.trim().isNotEmpty &&
            rawNotes.toLowerCase() != 'null')
        ? rawNotes.trim()
        : null;

    // --- Reminder time (optional) ---
    DateTime? reminderTime;
    final rawReminder = json['reminder_time'];
    if (rawReminder is String && rawReminder.toLowerCase() != 'null') {
      try {
        final parsed = DateTime.parse(rawReminder);
        // Reject past times (past-time guard — spec Requirement 8).
        if (parsed.isAfter(now.subtract(const Duration(minutes: 1)))) {
          reminderTime = parsed.toUtc();
          // Sync dueDate to the date portion of reminderTime when not set.
          dueDate ??= DateTime(parsed.year, parsed.month, parsed.day).toUtc();
        }
      } on FormatException {
        reminderTime = null; // Invalid format — ignore, don't fail.
      }
    }

    return TaskExtractionSuccess(
      ExtractedTask(
        title: title,
        dueDate: dueDate,
        reminderTime: reminderTime,
        notes: notes,
      ),
    );
  }

  // =========================================================================
  // Layer A: Regex extraction (fallback)
  // =========================================================================

  TaskExtractionResult _extractWithRegex(String message, DateTime now) {
    final title = _extractTitle(message);
    if (title == null) {
      return const TaskExtractionFailure(
        'Could not extract task title from message',
      );
    }

    final localNow = now.toLocal();
    final dueDate = _extractDueDate(message, localNow);
    final reminderTime = _extractReminderTime(message, localNow, dueDate);

    return TaskExtractionSuccess(
      ExtractedTask(title: title, dueDate: dueDate, reminderTime: reminderTime),
    );
  }

  /// Extract a task title by removing task/reminder action phrases and temporal refs.
  static String? _extractTitle(String message) {
    var cleaned = message.replaceAll(
      RegExp(
        r'\b(add|create|make|new|put)\s+(a\s+)?(task|to.?do)\b\s*:?\s*',
        caseSensitive: false,
      ),
      '',
    );

    // Remove reminder action phrases ("remind me to", "set a reminder to").
    cleaned = cleaned.replaceAll(
      RegExp(
        r'\b(remind\s+me\s+to|set\s+(a\s+)?reminder\s+to|'
        r'set\s+(a\s+)?reminder\s+for|'
        r'remind\s+me\s+about)\b\s*',
        caseSensitive: false,
      ),
      '',
    );

    // Remove "to my task list / to-do list / list" phrases.
    cleaned = cleaned.replaceAll(
      RegExp(
        r'\b(to|on)\s+(my\s+)?(task\s*list|to.?do\s*list|list)\b',
        caseSensitive: false,
      ),
      '',
    );

    // Remove temporal phrases.
    cleaned = cleaned.replaceAll(
      RegExp(
        r'\b(tomorrow|today|tonight|by\s+(tomorrow|today|next\s+\w+)|'
        r'due\s+(tomorrow|today|next\s+\w+)|'
        r'for\s+(tomorrow|today|next\s+\w+))\b',
        caseSensitive: false,
      ),
      '',
    );

    // Clean up whitespace and punctuation.
    cleaned = cleaned.replaceAll(RegExp(r'\s+'), ' ').trim();
    cleaned = cleaned.replaceAll(RegExp(r'^[,.\s]+|[,.\s]+$'), '').trim();

    if (cleaned.isEmpty) return null;

    // Capitalize first letter.
    return cleaned[0].toUpperCase() + cleaned.substring(1);
  }

  /// Extract a due date from temporal expressions.
  static DateTime? _extractDueDate(String message, DateTime now) {
    final lower = message.toLowerCase();

    if (lower.contains('tomorrow')) {
      final tomorrow = now.add(const Duration(days: 1));
      return DateTime(tomorrow.year, tomorrow.month, tomorrow.day);
    }

    if (lower.contains('today') || lower.contains('tonight')) {
      return DateTime(now.year, now.month, now.day);
    }

    // "next <day>"
    final dayMatch = RegExp(
      r'(?:next|by|for|due)\s+(monday|tuesday|wednesday|thursday|friday|'
      r'saturday|sunday)',
      caseSensitive: false,
    ).firstMatch(lower);

    if (dayMatch != null) {
      final targetDay = _dayOfWeek(dayMatch.group(1)!.toLowerCase());
      if (targetDay != null) {
        final date = _nextWeekday(now, targetDay);
        return DateTime(date.year, date.month, date.day);
      }
    }

    return null;
  }

  /// Extract a full reminder date-time from temporal expressions that include
  /// a time component ("at 4pm", "in an hour", "in 30 minutes", etc.).
  ///
  /// Returns null when no time component is found (date-only or no date).
  /// The returned DateTime is in local time.
  static DateTime? _extractReminderTime(
    String message,
    DateTime localNow,
    DateTime? dueDate,
  ) {
    final lower = message.toLowerCase();

    // "in N minutes" / "in N hours"
    final inDurationMatch = RegExp(
      r'\bin\s+(\d+)\s+(minute|minutes|min|hour|hours|hr)\b',
      caseSensitive: false,
    ).firstMatch(lower);
    if (inDurationMatch != null) {
      final amount = int.parse(inDurationMatch.group(1)!);
      final unit = inDurationMatch.group(2)!.toLowerCase();
      final duration = (unit.startsWith('h'))
          ? Duration(hours: amount)
          : Duration(minutes: amount);
      final scheduled = localNow.add(duration);
      // Past-time guard: reject if already elapsed.
      if (scheduled.isAfter(localNow)) return scheduled;
      return null;
    }

    // "at [H]H[:MM] [am/pm]" — e.g. "at 4pm", "at 4:30pm", "at 16:00"
    final atTimeMatch = RegExp(
      r'\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?',
      caseSensitive: false,
    ).firstMatch(lower);
    if (atTimeMatch != null) {
      var hour = int.parse(atTimeMatch.group(1)!);
      final minute = atTimeMatch.group(2) != null
          ? int.parse(atTimeMatch.group(2)!)
          : 0;
      final period = atTimeMatch.group(3)?.toLowerCase().replaceAll('.', '');

      if (period == 'pm' && hour < 12) hour += 12;
      if (period == 'am' && hour == 12) hour = 0;

      // Use dueDate's date component if available; else use today or tomorrow.
      final baseDate = dueDate ?? localNow;
      var scheduled = DateTime(
        baseDate.year,
        baseDate.month,
        baseDate.day,
        hour,
        minute,
      );
      // If the time is today but already past, advance to tomorrow.
      if (dueDate == null && scheduled.isBefore(localNow)) {
        scheduled = scheduled.add(const Duration(days: 1));
      }
      return scheduled;
    }

    // "tonight" → today at 20:00
    if (lower.contains('tonight')) {
      return DateTime(localNow.year, localNow.month, localNow.day, 20, 0);
    }

    // "tomorrow morning" → tomorrow at 09:00
    if (lower.contains('tomorrow morning') || lower.contains('tmrw morning')) {
      final tomorrow = localNow.add(const Duration(days: 1));
      return DateTime(tomorrow.year, tomorrow.month, tomorrow.day, 9, 0);
    }

    // "this morning" / "tomorrow afternoon" / "tomorrow evening"
    if (lower.contains('tomorrow afternoon') ||
        lower.contains('tmrw afternoon')) {
      final tomorrow = localNow.add(const Duration(days: 1));
      return DateTime(tomorrow.year, tomorrow.month, tomorrow.day, 14, 0);
    }
    if (lower.contains('tomorrow evening') || lower.contains('tmrw evening')) {
      final tomorrow = localNow.add(const Duration(days: 1));
      return DateTime(tomorrow.year, tomorrow.month, tomorrow.day, 19, 0);
    }

    return null;
  }

  static int? _dayOfWeek(String day) {
    const days = {
      'monday': DateTime.monday,
      'tuesday': DateTime.tuesday,
      'wednesday': DateTime.wednesday,
      'thursday': DateTime.thursday,
      'friday': DateTime.friday,
      'saturday': DateTime.saturday,
      'sunday': DateTime.sunday,
    };
    return days[day];
  }

  static DateTime _nextWeekday(DateTime from, int weekday) {
    var daysUntil = weekday - from.weekday;
    if (daysUntil <= 0) daysUntil += 7;
    return from.add(Duration(days: daysUntil));
  }

  /// Sanitize timezone string — returns 'UTC' for anything non-IANA.
  static String _sanitizeTimezone(String tz) {
    final ianaPattern = RegExp(r'^[A-Za-z0-9_\-+/]{1,64}$');
    return ianaPattern.hasMatch(tz) ? tz : 'UTC';
  }
}
