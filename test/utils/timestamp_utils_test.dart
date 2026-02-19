import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/utils/timestamp_utils.dart';

void main() {
  group('formatForDisplay', () {
    // These tests use UTC times and verify the formatted output.
    // Since toLocal() behavior depends on the test machine's timezone,
    // we test the formatting logic by passing local times as UTC
    // (the formatting function converts UTC→local, so on a machine where
    // local == UTC, these are identity conversions).

    test('formats midnight correctly as 12:00 AM', () {
      // Create a time that will be midnight in local time.
      final midnight = DateTime(2026, 2, 19, 0, 0);
      final result = formatForDisplay(midnight.toUtc());
      // Should show "12:00 AM" regardless of timezone offset.
      expect(result, contains('12:00 AM'));
    });

    test('formats noon correctly as 12:00 PM', () {
      final noon = DateTime(2026, 2, 19, 12, 0);
      final result = formatForDisplay(noon.toUtc());
      expect(result, contains('12:00 PM'));
    });

    test('formats 1 AM correctly', () {
      final oneAm = DateTime(2026, 2, 19, 1, 0);
      final result = formatForDisplay(oneAm.toUtc());
      expect(result, contains('1:00 AM'));
    });

    test('formats 1 PM correctly', () {
      final onePm = DateTime(2026, 2, 19, 13, 30);
      final result = formatForDisplay(onePm.toUtc());
      expect(result, contains('1:30 PM'));
    });

    test('includes month, day, and year', () {
      final time = DateTime(2026, 2, 19, 10, 41);
      final result = formatForDisplay(time.toUtc());
      expect(result, contains('Feb'));
      expect(result, contains('19'));
      expect(result, contains('2026'));
    });
  });

  group('formatShortDate', () {
    test('omits year for current year', () {
      final now = DateTime.now();
      final sameYear = DateTime(now.year, 3, 15);
      final result = formatShortDate(sameYear.toUtc());
      expect(result, 'Mar 15');
      expect(result, isNot(contains('${now.year}')));
    });

    test('includes year for different year', () {
      final oldDate = DateTime(2025, 6, 1);
      final result = formatShortDate(oldDate.toUtc());
      expect(result, 'Jun 1, 2025');
    });
  });

  group('formatDuration', () {
    test('returns "<1 min" for zero seconds', () {
      expect(formatDuration(Duration.zero), '<1 min');
    });

    test('returns "<1 min" for 59 seconds', () {
      expect(formatDuration(const Duration(seconds: 59)), '<1 min');
    });

    test('returns "1 min" for one minute', () {
      expect(formatDuration(const Duration(minutes: 1)), '1 min');
    });

    test('returns "59 min" for 59 minutes', () {
      expect(formatDuration(const Duration(minutes: 59)), '59 min');
    });

    test('returns "1 hr" for exactly one hour', () {
      expect(formatDuration(const Duration(hours: 1)), '1 hr');
    });

    test('returns "1 hr 30 min" for 90 minutes', () {
      expect(
        formatDuration(const Duration(hours: 1, minutes: 30)),
        '1 hr 30 min',
      );
    });
  });
}
