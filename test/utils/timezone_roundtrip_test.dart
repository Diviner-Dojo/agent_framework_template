import 'package:flutter_test/flutter_test.dart';
import 'package:drift/native.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';
import 'package:agentic_journal/database/daos/message_dao.dart';
import 'package:agentic_journal/utils/timestamp_utils.dart';

void main() {
  group('UTC/Timezone round-trip', () {
    late AppDatabase database;
    late SessionDao sessionDao;
    late MessageDao messageDao;

    setUp(() {
      database = AppDatabase.forTesting(NativeDatabase.memory());
      sessionDao = SessionDao(database);
      messageDao = MessageDao(database);
    });

    tearDown(() async {
      await database.close();
    });

    test('session timestamps round-trip through DB as UTC', () async {
      // Create a UTC timestamp (as the app would).
      final utcNow = DateTime.utc(2026, 2, 23, 15, 30, 0);
      await sessionDao.createSession('s1', utcNow, 'America/Denver');

      // Retrieve from DB.
      final session = (await sessionDao.getSessionById('s1'))!;

      // Verify UTC round-trip (stored as UTC, retrieved as UTC).
      expect(session.startTime, utcNow);
      expect(session.startTime.isUtc, true);

      // Display conversion: toLocal() should produce a valid local time.
      final localTime = session.startTime.toLocal();
      expect(localTime.isUtc, false);

      // formatShortDate should not throw and should produce a string.
      final formatted = formatShortDate(session.startTime);
      expect(formatted, isNotEmpty);
    });

    test('message timestamps round-trip through DB as UTC', () async {
      final utcNow = DateTime.utc(2026, 2, 23, 15, 30, 0);
      await sessionDao.createSession('s1', utcNow, 'UTC');
      await messageDao.insertMessage('m1', 's1', 'USER', 'Hello', utcNow);

      // Retrieve from DB.
      final messages = await messageDao.getMessagesForSession('s1');
      expect(messages.length, 1);

      // Verify UTC round-trip.
      expect(messages[0].timestamp, utcNow);
      expect(messages[0].timestamp.isUtc, true);

      // Display conversion should work.
      final localTime = messages[0].timestamp.toLocal();
      expect(localTime.isUtc, false);
    });

    test('endSession timestamps are UTC', () async {
      final startUtc = DateTime.utc(2026, 2, 23, 10, 0, 0);
      final endUtc = DateTime.utc(2026, 2, 23, 10, 30, 0);
      await sessionDao.createSession('s1', startUtc, 'UTC');
      await sessionDao.endSession('s1', endUtc, summary: 'Test');

      final session = (await sessionDao.getSessionById('s1'))!;
      expect(session.startTime, startUtc);
      expect(session.endTime, endUtc);
      expect(session.startTime.isUtc, true);
      expect(session.endTime!.isUtc, true);
    });

    test('nowUtc() returns UTC', () {
      final utc = nowUtc();
      expect(utc.isUtc, true);
    });

    test('formatForDisplay converts UTC to local and formats', () {
      final utcTime = DateTime.utc(2026, 2, 23, 15, 30, 0);
      final result = formatForDisplay(utcTime);
      // Should contain the date and time (exact format depends on local TZ).
      expect(result, contains('2026'));
      expect(result, contains('Feb'));
    });

    test('formatDuration handles various durations', () {
      expect(formatDuration(const Duration(seconds: 30)), '<1 min');
      expect(formatDuration(const Duration(minutes: 5)), '5 min');
      expect(
        formatDuration(const Duration(hours: 1, minutes: 23)),
        '1 hr 23 min',
      );
      expect(formatDuration(const Duration(hours: 2)), '2 hr');
    });
  });
}
