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

  group('getSessionsToSync', () {
    test('returns PENDING sessions', () async {
      await sessionDao.createSession(
        'session-1',
        DateTime.utc(2026, 2, 20, 10, 0),
        'UTC',
      );

      final result = await sessionDao.getSessionsToSync();
      expect(result.length, 1);
      expect(result[0].sessionId, 'session-1');
      expect(result[0].syncStatus, 'PENDING');
    });

    test('returns FAILED sessions', () async {
      await sessionDao.createSession(
        'session-1',
        DateTime.utc(2026, 2, 20, 10, 0),
        'UTC',
      );
      await sessionDao.updateSyncStatus(
        'session-1',
        'FAILED',
        DateTime.utc(2026, 2, 20, 11, 0),
      );

      final result = await sessionDao.getSessionsToSync();
      expect(result.length, 1);
      expect(result[0].syncStatus, 'FAILED');
    });

    test('excludes SYNCED sessions', () async {
      await sessionDao.createSession(
        'session-1',
        DateTime.utc(2026, 2, 20, 10, 0),
        'UTC',
      );
      await sessionDao.updateSyncStatus(
        'session-1',
        'SYNCED',
        DateTime.utc(2026, 2, 20, 11, 0),
      );

      final result = await sessionDao.getSessionsToSync();
      expect(result, isEmpty);
    });

    test('returns sessions ordered oldest first', () async {
      await sessionDao.createSession(
        'session-new',
        DateTime.utc(2026, 2, 20),
        'UTC',
      );
      await sessionDao.createSession(
        'session-old',
        DateTime.utc(2026, 2, 19),
        'UTC',
      );

      final result = await sessionDao.getSessionsToSync();
      expect(result.length, 2);
      expect(result[0].sessionId, 'session-old');
      expect(result[1].sessionId, 'session-new');
    });

    test('returns empty list when no sessions need sync', () async {
      final result = await sessionDao.getSessionsToSync();
      expect(result, isEmpty);
    });
  });

  group('updateSyncStatus', () {
    test('updates syncStatus and lastSyncAttempt', () async {
      await sessionDao.createSession(
        'session-1',
        DateTime.utc(2026, 2, 20),
        'UTC',
      );

      final syncTime = DateTime.utc(2026, 2, 20, 12, 0);
      await sessionDao.updateSyncStatus('session-1', 'SYNCED', syncTime);

      final result = await sessionDao.getSessionById('session-1');
      expect(result, isNotNull);
      expect(result!.syncStatus, 'SYNCED');
      expect(result.lastSyncAttempt, syncTime);
    });

    test('updates to FAILED status', () async {
      await sessionDao.createSession(
        'session-1',
        DateTime.utc(2026, 2, 20),
        'UTC',
      );

      final failTime = DateTime.utc(2026, 2, 20, 12, 30);
      await sessionDao.updateSyncStatus('session-1', 'FAILED', failTime);

      final result = await sessionDao.getSessionById('session-1');
      expect(result!.syncStatus, 'FAILED');
      expect(result.lastSyncAttempt, failTime);
    });

    test('does not throw for non-existent session', () async {
      // Should silently update 0 rows, not throw.
      await sessionDao.updateSyncStatus(
        'non-existent',
        'SYNCED',
        DateTime.utc(2026, 2, 20),
      );

      final result = await sessionDao.getAllSessionsByDate();
      expect(result, isEmpty);
    });
  });

  group('watchPendingSyncCount', () {
    test('emits 0 when no pending sessions', () async {
      final stream = sessionDao.watchPendingSyncCount();
      await expectLater(stream, emits(0));
    });

    test('emits count of PENDING sessions', () async {
      await sessionDao.createSession(
        'session-1',
        DateTime.utc(2026, 2, 20),
        'UTC',
      );
      await sessionDao.createSession(
        'session-2',
        DateTime.utc(2026, 2, 20, 1),
        'UTC',
      );

      final stream = sessionDao.watchPendingSyncCount();
      await expectLater(stream, emits(2));
    });

    test('includes FAILED sessions in count', () async {
      await sessionDao.createSession(
        'session-1',
        DateTime.utc(2026, 2, 20),
        'UTC',
      );
      await sessionDao.updateSyncStatus(
        'session-1',
        'FAILED',
        DateTime.utc(2026, 2, 20),
      );

      final stream = sessionDao.watchPendingSyncCount();
      await expectLater(stream, emits(1));
    });

    test('excludes SYNCED sessions from count', () async {
      await sessionDao.createSession(
        'session-1',
        DateTime.utc(2026, 2, 20),
        'UTC',
      );
      await sessionDao.updateSyncStatus(
        'session-1',
        'SYNCED',
        DateTime.utc(2026, 2, 20),
      );

      final stream = sessionDao.watchPendingSyncCount();
      await expectLater(stream, emits(0));
    });
  });
}
