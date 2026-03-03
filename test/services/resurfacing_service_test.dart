// ===========================================================================
// file: test/services/resurfacing_service_test.dart
// purpose: Unit tests for ResurfacingService.
//
// Covers:
//   - Returns null when no sessions exist
//   - Returns null when all sessions are too recent (<4 days)
//   - Returns null for quick_mood_tap sessions
//   - Returns null for sessions without a summary
//   - Returns a session in the ~7-day window
//   - Returns a session in the ~30-day window
//   - Returns a session in the ~90-day window
//   - Excluded sessions are not returned after skipSession()
//   - skipSession() persists across service instance creation
// ===========================================================================

import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';
import 'package:agentic_journal/services/resurfacing_service.dart';

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

  ResurfacingService makeService() => ResurfacingService(sessionDao, prefs);

  // Helper: insert a completed session [daysAgo] days in the past with summary.
  Future<String> insertCompletedSession(int daysAgo, {String? summary}) async {
    final id = 'session-$daysAgo-${DateTime.now().microsecondsSinceEpoch}';
    final startTime = DateTime.now().toUtc().subtract(Duration(days: daysAgo));
    await sessionDao.createSession(id, startTime, 'UTC');
    await sessionDao.endSession(
      id,
      startTime,
      summary: summary ?? 'Session from $daysAgo days ago.',
    );
    return id;
  }

  group('pickResurfacedSession', () {
    test('returns null when no sessions exist', () async {
      final result = await makeService().pickResurfacedSession();
      expect(result, isNull);
    });

    test('returns null when only very recent sessions exist', () async {
      // Sessions within 4 days are outside all windows (centers-radius = 4).
      await insertCompletedSession(1);
      await insertCompletedSession(2);

      final result = await makeService().pickResurfacedSession();
      expect(result, isNull);
    });

    test('returns a session from the ~7-day window', () async {
      final id = await insertCompletedSession(7);

      final result = await makeService().pickResurfacedSession();
      expect(result, isNotNull);
      expect(result!.sessionId, id);
    });

    test('returns a session from the ~30-day window', () async {
      final id = await insertCompletedSession(30);

      final result = await makeService().pickResurfacedSession();
      expect(result, isNotNull);
      expect(result!.sessionId, id);
    });

    test('returns a session from the ~90-day window', () async {
      final id = await insertCompletedSession(90);

      final result = await makeService().pickResurfacedSession();
      expect(result, isNotNull);
      expect(result!.sessionId, id);
    });

    test('returns null when session has no summary', () async {
      final id = 'no-summary';
      final startTime = DateTime.now().toUtc().subtract(
        const Duration(days: 7),
      );
      await sessionDao.createSession(id, startTime, 'UTC');
      await sessionDao.endSession(id, startTime); // no summary

      final result = await makeService().pickResurfacedSession();
      expect(result, isNull);
    });

    test('excludes quick_mood_tap sessions', () async {
      final id = 'qmt';
      final startTime = DateTime.now().toUtc().subtract(
        const Duration(days: 7),
      );
      await sessionDao.createQuickMoodSession(
        id,
        startTime,
        'UTC',
        'Mood: 😐 Neutral',
      );

      final result = await makeService().pickResurfacedSession();
      expect(result, isNull);
    });

    test('returns null for incomplete session (endTime is null)', () async {
      // B-2: the endTime != null eligibility check must exclude sessions that
      // were started but never completed.
      final id = 'incomplete';
      final startTime = DateTime.now().toUtc().subtract(
        const Duration(days: 7),
      );
      await sessionDao.createSession(id, startTime, 'UTC');
      // No endSession() call — endTime remains null.

      final result = await makeService().pickResurfacedSession();
      expect(result, isNull);
    });

    test('returns null when session summary is empty string', () async {
      // B-3: the summary?.isNotEmpty check must exclude sessions whose summary
      // was explicitly set to '' (distinct from null).
      final id = 'empty-summary';
      final startTime = DateTime.now().toUtc().subtract(
        const Duration(days: 7),
      );
      await sessionDao.createSession(id, startTime, 'UTC');
      await sessionDao.endSession(id, startTime, summary: '');

      final result = await makeService().pickResurfacedSession();
      expect(result, isNull);
    });

    test(
      'returns exactly one session when sessions exist in multiple windows',
      () async {
        // Confirms the single-result cardinality contract: even with sessions
        // in all three windows, exactly one is returned.
        final id7 = await insertCompletedSession(7);
        final id30 = await insertCompletedSession(30);
        final id90 = await insertCompletedSession(90);

        final result = await makeService().pickResurfacedSession();
        expect(result, isNotNull);
        expect(
          [id7, id30, id90],
          contains(result!.sessionId),
          reason: 'returned session must be one of the three inserted',
        );
      },
    );

    test(
      'returns null for sessions outside all windows (15 days ago)',
      () async {
        await insertCompletedSession(15); // outside 7±3 and 30±3 windows

        // 15 is outside window [4-10] and [27-33] and [87-93].
        // It sits between windows. Should return null.
        final result = await makeService().pickResurfacedSession();
        // 15 days is outside window 7±3=[4-10] and outside 30±3=[27-33].
        // Actually 15 is between windows — so null is expected.
        expect(result, isNull);
      },
    );
  });

  group('skipSession', () {
    test('excluded session is not returned after skip', () async {
      final id = await insertCompletedSession(7);

      // Verify it's returnable before skip.
      expect(await makeService().pickResurfacedSession(), isNotNull);

      // Skip it.
      final service = makeService();
      await service.skipSession(id);

      // Should no longer be returned.
      final result = await makeService().pickResurfacedSession();
      expect(result, isNull);
    });

    test('exclusion persists across service instances', () async {
      final id = await insertCompletedSession(7);

      // Skip via first instance.
      await makeService().skipSession(id);

      // New instance using same prefs should also exclude it.
      final result = await makeService().pickResurfacedSession();
      expect(result, isNull);
    });

    test('skipping one session still surfaces another if available', () async {
      final id1 = await insertCompletedSession(7);
      final id2 = await insertCompletedSession(8); // also in 7±3 window

      // Skip id1.
      await makeService().skipSession(id1);

      // id2 should still surface.
      final result = await makeService().pickResurfacedSession();
      expect(result, isNotNull);
      expect(result!.sessionId, id2);
    });
  });
}
