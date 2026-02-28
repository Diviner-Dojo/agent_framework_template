import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/services/app_logger.dart';

void main() {
  setUp(() {
    AppLogger.clear();
  });

  group('AppLogger', () {
    test('logging adds entries to the ring buffer', () {
      AppLogger.i('test', 'info message');
      AppLogger.w('test', 'warn message');
      AppLogger.e('test', 'error message');

      expect(AppLogger.entries, hasLength(3));
    });

    test('entries contain correct tag, level, and message', () {
      AppLogger.i('init', 'Supabase initialized');

      final entry = AppLogger.entries.first;
      expect(entry.tag, 'init');
      expect(entry.level, LogLevel.info);
      expect(entry.message, 'Supabase initialized');
      expect(entry.timestamp, isA<DateTime>());
    });

    test('warn level is recorded correctly', () {
      AppLogger.w('retry', 'Timeout on attempt 1');

      final entry = AppLogger.entries.first;
      expect(entry.level, LogLevel.warn);
      expect(entry.tag, 'retry');
      expect(entry.message, 'Timeout on attempt 1');
    });

    test('error level is recorded correctly', () {
      AppLogger.e('init', 'Supabase init failed');

      final entry = AppLogger.entries.first;
      expect(entry.level, LogLevel.error);
    });

    test('ring buffer caps at maxEntries (oldest evicted)', () {
      for (var i = 0; i < AppLogger.maxEntries + 50; i++) {
        AppLogger.i('test', 'entry $i');
      }

      expect(AppLogger.entries, hasLength(AppLogger.maxEntries));
      // Oldest entries (0-49) should have been evicted.
      expect(AppLogger.entries.first.message, 'entry 50');
      expect(
        AppLogger.entries.last.message,
        'entry ${AppLogger.maxEntries + 49}',
      );
    });

    test('clear empties the buffer', () {
      AppLogger.i('test', 'message');
      AppLogger.w('test', 'another');
      expect(AppLogger.entries, hasLength(2));

      AppLogger.clear();
      expect(AppLogger.entries, isEmpty);
    });

    test('entries list is unmodifiable', () {
      AppLogger.i('test', 'message');
      final entries = AppLogger.entries;

      expect(
        () => entries.add(
          LogEntry(
            timestamp: DateTime.now(),
            tag: 'hack',
            level: LogLevel.info,
            message: 'injected',
          ),
        ),
        throwsA(isA<UnsupportedError>()),
      );
    });

    test('toString formats entry correctly', () {
      AppLogger.i('init', 'hello');
      final entry = AppLogger.entries.first;
      final str = entry.toString();

      // Format: HH:MM:SS.mmm [LEVEL] tag: message
      expect(str, contains('[INFO ]'));
      expect(str, contains('init: hello'));
    });

    test('entries are ordered chronologically', () {
      AppLogger.i('test', 'first');
      AppLogger.i('test', 'second');
      AppLogger.i('test', 'third');

      expect(AppLogger.entries[0].message, 'first');
      expect(AppLogger.entries[1].message, 'second');
      expect(AppLogger.entries[2].message, 'third');
    });
  });
}
