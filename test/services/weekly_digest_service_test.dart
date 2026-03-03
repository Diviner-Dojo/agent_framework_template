// ===========================================================================
// file: test/services/weekly_digest_service_test.dart
// purpose: Unit tests for WeeklyDigestService.
//
// Covers:
//   - Returns null when no sessions exist
//   - Returns null when dismissed within 7 days
//   - Returns digest with correct sessionCount
//   - highlightSession is null when no session has a summary
//   - highlightSession is the most recent session with a summary
//   - Excludes quick_mood_tap sessions from the count
//   - Excludes incomplete sessions (endTime == null)
//   - Returns null when all eligible sessions are quick_mood_tap
//   - Session from 8 days ago is outside the 7-day window
//   - dismissDigest() persists across service instances
//   - Dismissal expires after 7 days (old timestamp → returns digest)
// ===========================================================================

import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';
import 'package:agentic_journal/services/weekly_digest_service.dart';

void main() {
  late AppDatabase database;
  late SessionDao sessionDao;
  late SharedPreferences prefs;

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    prefs = await SharedPreferences.getInstance();
    database = AppDatabase.forTesting(NativeDatabase.memory());
    sessionDao = SessionDao(database);
  });

  tearDown(() async {
    await database.close();
  });

  WeeklyDigestService makeService() => WeeklyDigestService(sessionDao, prefs);

  /// Insert a completed session [daysAgo] days in the past.
  Future<String> insertCompletedSession(
    int daysAgo, {
    String? summary,
    String? journalingMode,
  }) async {
    final id =
        'session-$daysAgo-${DateTime.now().microsecondsSinceEpoch}-${summary?.hashCode ?? 0}';
    final startTime = DateTime.now().toUtc().subtract(Duration(days: daysAgo));
    await sessionDao.createSession(id, startTime, 'UTC');
    if (journalingMode != null) {
      await sessionDao.updateJournalingMode(id, journalingMode);
    }
    await sessionDao.endSession(
      id,
      startTime,
      summary: summary ?? 'Session from $daysAgo days ago.',
    );
    return id;
  }

  group('getDigest', () {
    test('returns null when no sessions exist', () async {
      final result = await makeService().getDigest();
      expect(result, isNull);
    });

    test('returns null when dismissed within 7 days', () async {
      await insertCompletedSession(3);
      final service = makeService();
      await service.dismissDigest();

      final result = await service.getDigest();
      expect(result, isNull);
    });

    test('returns digest with correct sessionCount', () async {
      await insertCompletedSession(1);
      await insertCompletedSession(2);
      await insertCompletedSession(5);

      final result = await makeService().getDigest();
      expect(result, isNotNull);
      expect(result!.sessionCount, 3);
    });

    test('highlightSession is null when no session has a summary', () async {
      final id = 'no-summary';
      final startTime = DateTime.now().toUtc().subtract(
        const Duration(days: 3),
      );
      await sessionDao.createSession(id, startTime, 'UTC');
      await sessionDao.endSession(id, startTime); // no summary

      final result = await makeService().getDigest();
      expect(result, isNotNull);
      expect(result!.highlightSession, isNull);
    });

    test(
      'highlightSession is the most recent session with a summary',
      () async {
        // Insert older session with summary.
        final oldId = await insertCompletedSession(
          5,
          summary: 'Older session.',
        );
        // Insert newer session with summary — should be the highlight.
        final newId = await insertCompletedSession(
          1,
          summary: 'Recent session summary.',
        );

        final result = await makeService().getDigest();
        expect(result, isNotNull);
        // The most recent session (1 day ago) should be the highlight.
        expect(result!.highlightSession?.sessionId, newId);
        expect(result.highlightSession?.sessionId, isNot(oldId));
      },
    );

    test('excludes quick_mood_tap sessions from the count', () async {
      await insertCompletedSession(
        2,
        summary: 'Mood: 😐 Neutral',
        journalingMode: 'quick_mood_tap',
      );
      await insertCompletedSession(3, summary: 'Real session.');

      final result = await makeService().getDigest();
      // quick_mood_tap is excluded — only the real session counts.
      expect(result!.sessionCount, 1);
    });

    test('returns null when all sessions are quick_mood_tap', () async {
      await insertCompletedSession(
        2,
        summary: 'Mood: 😊 Good',
        journalingMode: 'quick_mood_tap',
      );
      await insertCompletedSession(
        4,
        summary: 'Mood: 😐 Neutral',
        journalingMode: 'quick_mood_tap',
      );

      final result = await makeService().getDigest();
      expect(result, isNull);
    });

    test('excludes incomplete sessions (endTime is null)', () async {
      // Insert an in-progress session (not ended).
      final id = 'incomplete';
      final startTime = DateTime.now().toUtc().subtract(
        const Duration(days: 3),
      );
      await sessionDao.createSession(id, startTime, 'UTC');
      // No endSession() call — endTime remains null.

      final result = await makeService().getDigest();
      // Only the incomplete session exists — no eligible sessions.
      expect(result, isNull);
    });

    test('session from 8 days ago is outside the 7-day window', () async {
      // 8-day-old session is outside the window.
      await insertCompletedSession(8);

      final result = await makeService().getDigest();
      expect(result, isNull);
    });

    test('session from 6 days ago is within the 7-day window', () async {
      await insertCompletedSession(6);

      final result = await makeService().getDigest();
      expect(result, isNotNull);
      expect(result!.sessionCount, 1);
    });
  });

  group('dismissDigest', () {
    test('dismissDigest() causes getDigest() to return null', () async {
      await insertCompletedSession(3);
      expect(await makeService().getDigest(), isNotNull);

      await makeService().dismissDigest();
      expect(await makeService().getDigest(), isNull);
    });

    test('dismissal persists across service instances', () async {
      await insertCompletedSession(3);
      // Dismiss via first instance.
      await makeService().dismissDigest();
      // A new instance using the same prefs should also see the dismissal.
      expect(await makeService().getDigest(), isNull);
    });

    test('dismissal expires after 7 days and digest resurfaces', () async {
      await insertCompletedSession(3);

      // Simulate a dismissal timestamp 8 days in the past.
      final oldTimestamp = DateTime.now()
          .toUtc()
          .subtract(const Duration(days: 8))
          .millisecondsSinceEpoch;
      SharedPreferences.setMockInitialValues({
        'weekly_digest_dismissed_at': oldTimestamp,
      });
      final freshPrefs = await SharedPreferences.getInstance();

      final result = await WeeklyDigestService(
        sessionDao,
        freshPrefs,
      ).getDigest();
      expect(result, isNotNull);
    });
  });
}
