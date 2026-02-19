import 'package:flutter_test/flutter_test.dart';
import 'package:drift/native.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';

void main() {
  late AppDatabase database;
  late SessionDao sessionDao;

  setUp(() {
    // Create an in-memory database for each test — completely isolated.
    database = AppDatabase.forTesting(NativeDatabase.memory());
    sessionDao = SessionDao(database);
  });

  tearDown(() async {
    // MUST close to avoid leaking connections (drift in-memory DBs don't auto-close).
    await database.close();
  });

  group('createSession + getSessionById', () {
    test('round-trip: created session can be retrieved', () async {
      final now = DateTime.utc(2026, 2, 19, 10, 0);
      await sessionDao.createSession('session-1', now, 'America/Denver');

      final result = await sessionDao.getSessionById('session-1');
      expect(result, isNotNull);
      expect(result!.sessionId, 'session-1');
      expect(result.startTime, now);
      expect(result.timezone, 'America/Denver');
      expect(result.endTime, isNull);
      expect(result.summary, isNull);
      expect(result.syncStatus, 'PENDING');
    });

    test('returns null for non-existent session', () async {
      final result = await sessionDao.getSessionById('does-not-exist');
      expect(result, isNull);
    });
  });

  group('getAllSessionsByDate', () {
    test('returns empty list when no sessions exist', () async {
      final result = await sessionDao.getAllSessionsByDate();
      expect(result, isEmpty);
    });

    test('returns sessions ordered newest first', () async {
      final older = DateTime.utc(2026, 2, 18, 10, 0);
      final newer = DateTime.utc(2026, 2, 19, 10, 0);
      await sessionDao.createSession('session-old', older, 'UTC');
      await sessionDao.createSession('session-new', newer, 'UTC');

      final result = await sessionDao.getAllSessionsByDate();
      expect(result.length, 2);
      expect(result[0].sessionId, 'session-new'); // Newest first.
      expect(result[1].sessionId, 'session-old');
    });
  });

  group('endSession', () {
    test('writes all 5 metadata fields', () async {
      final start = DateTime.utc(2026, 2, 19, 10, 0);
      final end = DateTime.utc(2026, 2, 19, 10, 30);
      await sessionDao.createSession('session-1', start, 'UTC');

      await sessionDao.endSession(
        'session-1',
        end,
        summary: 'Had a great day',
        moodTags: '["happy","grateful"]',
        people: '["Sarah"]',
        topicTags: '["work"]',
      );

      final result = await sessionDao.getSessionById('session-1');
      expect(result, isNotNull);
      expect(result!.endTime, end);
      expect(result.summary, 'Had a great day');
      expect(result.moodTags, '["happy","grateful"]');
      expect(result.people, '["Sarah"]');
      expect(result.topicTags, '["work"]');
    });

    test(
      'does not corrupt database when called on non-existent session',
      () async {
        // This should silently update 0 rows, not throw.
        await sessionDao.endSession(
          'non-existent',
          DateTime.utc(2026, 2, 19),
          summary: 'test',
        );

        // Database should still work fine.
        final result = await sessionDao.getAllSessionsByDate();
        expect(result, isEmpty);
      },
    );
  });

  group('getSessionsByDateRange', () {
    test('returns sessions within the range', () async {
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 17), 'UTC');
      await sessionDao.createSession('s2', DateTime.utc(2026, 2, 18), 'UTC');
      await sessionDao.createSession('s3', DateTime.utc(2026, 2, 19), 'UTC');

      final result = await sessionDao.getSessionsByDateRange(
        DateTime.utc(2026, 2, 17, 12),
        DateTime.utc(2026, 2, 18, 23, 59),
      );
      // Only s2 is within the range (s1 is before start, s3 is after end).
      expect(result.length, 1);
      expect(result[0].sessionId, 's2');
    });

    test('returns empty list for empty range', () async {
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 19), 'UTC');
      final result = await sessionDao.getSessionsByDateRange(
        DateTime.utc(2026, 1, 1),
        DateTime.utc(2026, 1, 2),
      );
      expect(result, isEmpty);
    });

    test('returns empty list for inverted range', () async {
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 19), 'UTC');
      // start > end — no results should match.
      final result = await sessionDao.getSessionsByDateRange(
        DateTime.utc(2026, 3, 1),
        DateTime.utc(2026, 1, 1),
      );
      expect(result, isEmpty);
    });
  });
}
