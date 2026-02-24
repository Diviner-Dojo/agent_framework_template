// ===========================================================================
// file: lib/services/event_extraction_service.dart
// purpose: Extract structured event details from natural language.
//
// Two-layer strategy matching the ConversationLayer pattern:
//   Layer A (rule-based): Basic regex extraction of dates, times, quoted titles.
//   Layer B (LLM): ClaudeApiService call requesting JSON output for title,
//     date, time, duration. Used when Claude proxy is configured.
//
// Strict output validation (blocking review finding, SPEC §Task 5):
//   - Title: non-empty, under 200 characters
//   - DateTime: valid ISO 8601, within sane range (not before today -1 day,
//     not after today +2 years)
//   - No unexpected keys forwarded to Calendar API
//
// Failure contract:
//   - Malformed JSON → ExtractionError (typed error, not exception)
//   - Missing fields → partial extraction with nulls
//   - Past datetime → flagged for user confirmation
//
// See: ADR-0020 §4 (Event Extraction Routing)
// ===========================================================================

import 'dart:convert';

import 'package:flutter/foundation.dart';

import 'claude_api_service.dart';

/// Extracted event details from a user message.
class ExtractedEvent {
  /// Event title (non-empty, max 200 chars).
  final String title;

  /// Event start time (validated within sane range).
  final DateTime startTime;

  /// Event end time (nullable — reminders may not have one).
  final DateTime? endTime;

  /// Whether the extracted time is in the past.
  final bool isPastTime;

  /// Create an [ExtractedEvent].
  const ExtractedEvent({
    required this.title,
    required this.startTime,
    this.endTime,
    this.isPastTime = false,
  });
}

/// Typed error for extraction failures (not an exception — callers check
/// the Either-like result).
class ExtractionError {
  /// Human-readable explanation of what went wrong.
  final String reason;

  /// Create an [ExtractionError].
  const ExtractionError(this.reason);

  @override
  String toString() => 'ExtractionError: $reason';
}

/// Result of event extraction — sealed for exhaustive pattern matching.
///
/// Callers use Dart 3.x switch expressions:
///   switch (result) {
///     case ExtractionSuccess(:final event): /* use event */
///     case ExtractionFailure(:final error): /* handle error */
///   }
sealed class ExtractionResult {
  /// Whether extraction succeeded.
  bool get isSuccess;

  /// The extracted event (null on failure).
  ExtractedEvent? get event;

  /// The error (null on success).
  ExtractionError? get error;
}

/// Successful extraction containing the parsed event.
class ExtractionSuccess implements ExtractionResult {
  @override
  final ExtractedEvent event;

  /// Create a success result.
  const ExtractionSuccess(this.event);

  @override
  bool get isSuccess => true;

  @override
  ExtractionError? get error => null;
}

/// Failed extraction containing the typed error.
class ExtractionFailure implements ExtractionResult {
  @override
  final ExtractionError error;

  /// Create a failure result.
  const ExtractionFailure(this.error);

  @override
  bool get isSuccess => false;

  @override
  ExtractedEvent? get event => null;
}

/// Service for extracting structured event details from natural language.
///
/// Uses a two-layer strategy:
///   1. If [ClaudeApiService] is configured, use LLM extraction.
///   2. Otherwise, fall back to basic regex extraction (Layer A).
class EventExtractionService {
  final ClaudeApiService? _claudeApi;

  /// Create an EventExtractionService.
  ///
  /// [claudeApi] — provide for LLM-powered extraction. When null or
  /// not configured, falls back to regex extraction.
  EventExtractionService({ClaudeApiService? claudeApi})
    : _claudeApi = claudeApi;

  /// Extract event details from a user message.
  ///
  /// [message] — the raw user message classified as calendar/reminder intent.
  /// [now] — current time for validation and relative date resolution.
  ///   Injected for testability.
  Future<ExtractionResult> extract(String message, DateTime now) async {
    // Try LLM extraction first.
    if (_claudeApi != null && _claudeApi.isConfigured) {
      return _extractWithLlm(message, now);
    }

    // Fall back to regex extraction (Layer A).
    return _extractWithRegex(message, now);
  }

  // =========================================================================
  // Layer B: LLM extraction
  // =========================================================================

  Future<ExtractionResult> _extractWithLlm(String message, DateTime now) async {
    try {
      final prompt = _buildExtractionPrompt(message, now);
      final response = await _claudeApi!.chat(
        messages: [
          {'role': 'user', 'content': prompt},
        ],
      );

      return _parseAndValidateLlmResponse(response, now);
    } on ClaudeApiException catch (e) {
      if (kDebugMode) {
        debugPrint('LLM extraction failed: $e — falling back to regex');
      }
      // Graceful fallback to regex on API failure.
      return _extractWithRegex(message, now);
    }
  }

  /// Build the extraction prompt for the LLM.
  String _buildExtractionPrompt(String message, DateTime now) {
    final isoNow = now.toUtc().toIso8601String();
    return '''Extract calendar event details from this message. '''
        '''The current date/time is $isoNow.

Message: "$message"

Respond with ONLY a JSON object (no markdown, no explanation):
{"title": "event title", "start_time": "ISO 8601 datetime", "end_time": "ISO 8601 datetime or null", "duration_minutes": number or null}

Rules:
- title: concise event name (not the full sentence)
- start_time: resolve relative dates ("tomorrow", "next Friday") to absolute ISO 8601
- end_time: null if not specified
- duration_minutes: null if not specified; if given, compute end_time = start_time + duration''';
  }

  /// Parse and validate the LLM's JSON response.
  ExtractionResult _parseAndValidateLlmResponse(String response, DateTime now) {
    // Strip markdown code fences if present.
    final cleaned = response
        .replaceAll(RegExp(r'^```json?\s*', multiLine: true), '')
        .replaceAll(RegExp(r'```\s*$', multiLine: true), '')
        .trim();

    Map<String, dynamic> json;
    try {
      final decoded = jsonDecode(cleaned);
      if (decoded is! Map<String, dynamic>) {
        return const ExtractionFailure(
          ExtractionError('LLM response is not a JSON object'),
        );
      }
      json = decoded;
    } on FormatException {
      return const ExtractionFailure(
        ExtractionError('LLM returned invalid JSON'),
      );
    }

    return _validateExtraction(json, now);
  }

  /// Truncate untrusted strings for error messages (security-specialist).
  static String _sanitize(String raw, {int maxLen = 30}) =>
      raw.length > maxLen ? '${raw.substring(0, maxLen)}...' : raw;

  /// Validate extracted fields against strict schema rules.
  ExtractionResult _validateExtraction(
    Map<String, dynamic> json,
    DateTime now,
  ) {
    // --- Title validation ---
    final rawTitle = json['title'];
    if (rawTitle is! String || rawTitle.trim().isEmpty) {
      return const ExtractionFailure(ExtractionError('Missing or empty title'));
    }
    final title = rawTitle.trim().length > 200
        ? rawTitle.trim().substring(0, 200)
        : rawTitle.trim();

    // --- Start time validation ---
    final rawStart = json['start_time'];
    if (rawStart is! String) {
      return const ExtractionFailure(ExtractionError('Missing start_time'));
    }
    final DateTime startTime;
    try {
      startTime = DateTime.parse(rawStart).toUtc();
    } on FormatException {
      return ExtractionFailure(
        ExtractionError('Invalid start_time format: ${_sanitize(rawStart)}'),
      );
    }

    // Sane range: not before yesterday, not after 2 years from now.
    final lowerBound = now.subtract(const Duration(days: 1));
    final upperBound = now.add(const Duration(days: 730));
    final isPastTime = startTime.isBefore(now);

    if (startTime.isBefore(lowerBound)) {
      return ExtractionFailure(
        ExtractionError(
          'Start time is too far in the past: ${_sanitize(rawStart)}',
        ),
      );
    }
    if (startTime.isAfter(upperBound)) {
      return ExtractionFailure(
        ExtractionError(
          'Start time is too far in the future: ${_sanitize(rawStart)}',
        ),
      );
    }

    // --- End time validation (optional) ---
    DateTime? endTime;
    final rawEnd = json['end_time'];
    if (rawEnd is String) {
      try {
        endTime = DateTime.parse(rawEnd).toUtc();
      } on FormatException {
        // Non-critical — proceed without end time.
        endTime = null;
      }
    }

    // If duration_minutes was provided but end_time wasn't, compute it.
    if (endTime == null && json['duration_minutes'] is num) {
      final durationMinutes = (json['duration_minutes'] as num).toInt();
      if (durationMinutes > 0 && durationMinutes <= 1440) {
        endTime = startTime.add(Duration(minutes: durationMinutes));
      }
    }

    return ExtractionSuccess(
      ExtractedEvent(
        title: title,
        startTime: startTime,
        endTime: endTime,
        isPastTime: isPastTime,
      ),
    );
  }

  // =========================================================================
  // Layer A: Regex extraction (fallback)
  // =========================================================================

  /// Basic regex extraction for when LLM is not available.
  ///
  /// This is intentionally limited — it handles common patterns like
  /// "meeting tomorrow at 3pm" but won't handle complex temporal expressions.
  ExtractionResult _extractWithRegex(String message, DateTime now) {
    // Try to extract a title — text before temporal expressions.
    final title = _extractTitle(message);
    if (title == null) {
      return const ExtractionFailure(
        ExtractionError('Could not extract event title from message'),
      );
    }

    // Try to extract a datetime.
    final dateTime = _extractDateTime(message, now);
    if (dateTime == null) {
      return const ExtractionFailure(
        ExtractionError('Could not extract date/time from message'),
      );
    }

    final isPastTime = dateTime.isBefore(now);
    return ExtractionSuccess(
      ExtractedEvent(title: title, startTime: dateTime, isPastTime: isPastTime),
    );
  }

  // -------------------------------------------------------------------------
  // Regex helpers
  // -------------------------------------------------------------------------

  /// Extract a title from the message by removing temporal and action phrases.
  static String? _extractTitle(String message) {
    // Remove common action prefixes.
    var cleaned = message.replaceAll(
      RegExp(
        r'\b(add|schedule|book|set up|put|create|remind me to|remind me about|'
        r"don't let me forget to|remember to|make sure I)\b",
        caseSensitive: false,
      ),
      '',
    );

    // Remove temporal phrases.
    cleaned = cleaned.replaceAll(
      RegExp(
        r'\b(tomorrow|today|tonight|this morning|this afternoon|this evening|'
        r'next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday|'
        r'week|month)|on\s+(monday|tuesday|wednesday|thursday|friday|'
        r'saturday|sunday)|at\s+\d{1,2}(:\d{2})?\s*(am|pm)?|'
        r'in\s+\d+\s+(minutes?|hours?|days?)|for\s+(monday|tuesday|'
        r'wednesday|thursday|friday|saturday|sunday))\b',
        caseSensitive: false,
      ),
      '',
    );

    // Remove prepositions left hanging.
    cleaned = cleaned.replaceAll(
      RegExp(
        r'\b(to my calendar|on my calendar|to calendar)\b',
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

  /// Extract a datetime from temporal expressions in the message.
  static DateTime? _extractDateTime(String message, DateTime now) {
    final lower = message.toLowerCase();

    // Match "at H:MM am/pm" or "at H am/pm".
    final timeMatch = RegExp(
      r'at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?',
      caseSensitive: false,
    ).firstMatch(lower);

    int? hour;
    int? minute;
    if (timeMatch != null) {
      hour = int.parse(timeMatch.group(1)!);
      minute = timeMatch.group(2) != null ? int.parse(timeMatch.group(2)!) : 0;
      final ampm = timeMatch.group(3)?.toLowerCase();
      if (ampm == 'pm' && hour < 12) hour += 12;
      if (ampm == 'am' && hour == 12) hour = 0;
    }

    // Determine the date.
    DateTime date = now;

    if (lower.contains('tomorrow')) {
      date = now.add(const Duration(days: 1));
    } else if (lower.contains('tonight') || lower.contains('this evening')) {
      date = now;
      hour ??= 19; // Default "tonight" to 7 PM.
    } else if (lower.contains('this afternoon')) {
      date = now;
      hour ??= 14; // Default "this afternoon" to 2 PM.
    } else if (lower.contains('this morning')) {
      date = now;
      hour ??= 9; // Default "this morning" to 9 AM.
    } else {
      // Check for "next <day>" or "on <day>".
      final dayMatch = RegExp(
        r'(?:next|on)\s+(monday|tuesday|wednesday|thursday|friday|'
        r'saturday|sunday)',
        caseSensitive: false,
      ).firstMatch(lower);

      if (dayMatch != null) {
        final targetDay = _dayOfWeek(dayMatch.group(1)!.toLowerCase());
        if (targetDay != null) {
          date = _nextWeekday(now, targetDay);
        }
      }
    }

    // Default time to 9 AM if no time was extracted.
    hour ??= 9;
    minute ??= 0;

    return DateTime.utc(date.year, date.month, date.day, hour, minute);
  }

  /// Map day name to DateTime weekday (1=Monday, 7=Sunday).
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

  /// Find the next occurrence of a weekday from [from].
  static DateTime _nextWeekday(DateTime from, int weekday) {
    var daysUntil = weekday - from.weekday;
    if (daysUntil <= 0) daysUntil += 7;
    return from.add(Duration(days: daysUntil));
  }
}
