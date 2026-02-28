// ===========================================================================
// file: lib/services/app_logger.dart
// purpose: Structured logger that works in both debug AND release mode.
//
// Unlike debugPrint (which is gated behind kDebugMode), AppLogger stores
// log entries in an in-memory ring buffer accessible from the diagnostics
// screen. This provides visibility into initialization, layer selection,
// and retry/fallback decisions on release builds running on-device.
//
// Design:
//   - Singleton (static instance) — accessible from non-provider code
//   - In-memory ring buffer (no disk I/O, no storage permissions)
//   - 200 entry cap — enough to diagnose a session, not a memory leak
//   - Also calls debugPrint in debug mode for console output
//
// See: Runtime Observability plan
// ===========================================================================

import 'package:flutter/foundation.dart';

/// Severity level for log entries.
enum LogLevel {
  /// Informational messages (initialization, layer selection).
  info,

  /// Warning conditions (retry attempts, degraded functionality).
  warn,

  /// Error conditions (initialization failures, fallbacks).
  error,
}

/// A single structured log entry.
class LogEntry {
  /// When the entry was recorded.
  final DateTime timestamp;

  /// Category tag (e.g., 'init', 'layer', 'retry').
  final String tag;

  /// Severity level.
  final LogLevel level;

  /// Human-readable message.
  final String message;

  /// Creates a log entry.
  LogEntry({
    required this.timestamp,
    required this.tag,
    required this.level,
    required this.message,
  });

  /// Format as a single-line string for display.
  @override
  String toString() {
    final ts = timestamp.toIso8601String().substring(11, 23);
    final lvl = level.name.toUpperCase().padRight(5);
    return '$ts [$lvl] $tag: $message';
  }
}

/// Structured logger with in-memory ring buffer for release-mode diagnostics.
///
/// Provides static convenience methods for logging at different severity
/// levels. Entries are stored in a fixed-size ring buffer (oldest evicted
/// when full) and can be read from the diagnostics screen.
///
/// Usage:
/// ```dart
/// AppLogger.i('init', 'Supabase initialized');
/// AppLogger.w('retry', 'Timeout on attempt 1');
/// AppLogger.e('init', 'Supabase init failed: $e');
/// ```
class AppLogger {
  /// Maximum number of entries in the ring buffer.
  static const int maxEntries = 200;

  /// The ring buffer of log entries.
  static final List<LogEntry> _entries = [];

  /// All current log entries (most recent last).
  static List<LogEntry> get entries => List.unmodifiable(_entries);

  /// Log an informational message.
  static void i(String tag, String message) =>
      _log(tag, LogLevel.info, message);

  /// Log a warning message.
  static void w(String tag, String message) =>
      _log(tag, LogLevel.warn, message);

  /// Log an error message.
  static void e(String tag, String message) =>
      _log(tag, LogLevel.error, message);

  /// Clear all log entries.
  static void clear() => _entries.clear();

  static void _log(String tag, LogLevel level, String message) {
    final entry = LogEntry(
      timestamp: DateTime.now(),
      tag: tag,
      level: level,
      message: message,
    );

    _entries.add(entry);

    // Evict oldest entries when buffer is full.
    if (_entries.length > maxEntries) {
      _entries.removeAt(0);
    }

    // Also print to console in debug mode.
    if (kDebugMode) {
      debugPrint(entry.toString());
    }
  }
}
