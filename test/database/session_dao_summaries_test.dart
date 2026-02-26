// ===========================================================================
// file: test/database/session_dao_summaries_test.dart
// purpose: Tests for SessionDao.getRecentCompletedSessions() (ADR-0023).
// ===========================================================================

import 'package:flutter_test/flutter_test.dart';
import 'package:drift/native.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';

void main() {
  late AppDatabase database;
  late SessionDao sessionDao;

  setUp(() {
    database = AppDatabase.forTesting(NativeDatabase.memory());
    sessionDao = SessionDao(database);
  });

  tearDown(() async {
    await database.close();
  });

  group('getRecentCompletedSessions', () {
    test('returns empty list when no sessions exist', () async {
      final result = await sessionDao.getRecentCompletedSessions();
      expect(result, isEmpty);
    });

    test('excludes sessions without endTime', () async {
      final now = DateTime.utc(2026, 2, 26, 10, 0);
      await sessionDao.createSession('open-session', now, 'UTC');

      final result = await sessionDao.getRecentCompletedSessions();
      expect(result, isEmpty);
    });

    test('excludes sessions without summary', () async {
      final now = DateTime.utc(2026, 2, 26, 10, 0);
      await sessionDao.createSession('no-summary', now, 'UTC');
      await sessionDao.endSession(
        'no-summary',
        now.add(const Duration(minutes: 30)),
      );

      final result = await sessionDao.getRecentCompletedSessions();
      expect(result, isEmpty);
    });

    test('includes completed sessions with summaries', () async {
      final now = DateTime.utc(2026, 2, 26, 10, 0);
      await sessionDao.createSession('with-summary', now, 'UTC');
      await sessionDao.endSession(
        'with-summary',
        now.add(const Duration(minutes: 30)),
        summary: 'Discussed work stress and exercise plans.',
      );

      final result = await sessionDao.getRecentCompletedSessions();
      expect(result, hasLength(1));
      expect(result.first.sessionId, 'with-summary');
      expect(result.first.summary, 'Discussed work stress and exercise plans.');
    });

    test('returns sessions ordered newest first', () async {
      final base = DateTime.utc(2026, 2, 24, 10, 0);

      for (var i = 0; i < 3; i++) {
        final start = base.add(Duration(days: i));
        final id = 'session-$i';
        await sessionDao.createSession(id, start, 'UTC');
        await sessionDao.endSession(
          id,
          start.add(const Duration(minutes: 30)),
          summary: 'Summary for session $i',
        );
      }

      final result = await sessionDao.getRecentCompletedSessions();
      expect(result, hasLength(3));
      // Newest first.
      expect(result[0].sessionId, 'session-2');
      expect(result[1].sessionId, 'session-1');
      expect(result[2].sessionId, 'session-0');
    });

    test('respects the limit parameter', () async {
      final base = DateTime.utc(2026, 2, 20, 10, 0);

      for (var i = 0; i < 10; i++) {
        final start = base.add(Duration(days: i));
        final id = 'session-$i';
        await sessionDao.createSession(id, start, 'UTC');
        await sessionDao.endSession(
          id,
          start.add(const Duration(minutes: 30)),
          summary: 'Summary $i',
        );
      }

      final result = await sessionDao.getRecentCompletedSessions(limit: 3);
      expect(result, hasLength(3));
      // Should be the 3 most recent.
      expect(result[0].sessionId, 'session-9');
      expect(result[1].sessionId, 'session-8');
      expect(result[2].sessionId, 'session-7');
    });

    test('defaults to limit of 5', () async {
      final base = DateTime.utc(2026, 2, 15, 10, 0);

      for (var i = 0; i < 8; i++) {
        final start = base.add(Duration(days: i));
        final id = 'session-$i';
        await sessionDao.createSession(id, start, 'UTC');
        await sessionDao.endSession(
          id,
          start.add(const Duration(minutes: 30)),
          summary: 'Summary $i',
        );
      }

      final result = await sessionDao.getRecentCompletedSessions();
      expect(result, hasLength(5));
    });

    test('mixes completed-with-summary and other sessions correctly', () async {
      final base = DateTime.utc(2026, 2, 26, 10, 0);

      // Session 1: completed with summary (should be included).
      await sessionDao.createSession('complete', base, 'UTC');
      await sessionDao.endSession(
        'complete',
        base.add(const Duration(minutes: 30)),
        summary: 'Good session about family.',
      );

      // Session 2: still open (should be excluded).
      await sessionDao.createSession(
        'open',
        base.add(const Duration(hours: 1)),
        'UTC',
      );

      // Session 3: completed but no summary (should be excluded).
      await sessionDao.createSession(
        'no-summary',
        base.add(const Duration(hours: 2)),
        'UTC',
      );
      await sessionDao.endSession(
        'no-summary',
        base.add(const Duration(hours: 2, minutes: 30)),
      );

      final result = await sessionDao.getRecentCompletedSessions();
      expect(result, hasLength(1));
      expect(result.first.sessionId, 'complete');
    });
  });
}
