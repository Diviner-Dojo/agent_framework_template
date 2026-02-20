import 'package:flutter_test/flutter_test.dart';
import 'package:drift/native.dart';
import 'package:agentic_journal/config/environment.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';
import 'package:agentic_journal/database/daos/message_dao.dart';
import 'package:agentic_journal/repositories/sync_repository.dart';
import 'package:agentic_journal/services/supabase_service.dart';

/// A mock SupabaseService that reports as authenticated but has no real client.
///
/// This allows testing the authenticated code paths in SyncRepository without
/// requiring actual Supabase initialization. Since [client] returns null,
/// `_uploadSession` returns early (no-op), so sessions get marked as SYNCED
/// without actually uploading.
class _FakeAuthenticatedSupabaseService extends SupabaseService {
  _FakeAuthenticatedSupabaseService()
    : super(
        environment: const Environment.custom(
          supabaseUrl: '',
          supabaseAnonKey: '',
        ),
      );

  @override
  bool get isAuthenticated => true;
}

void main() {
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

  group('SyncRepository - unauthenticated', () {
    late SyncRepository syncRepo;

    setUp(() {
      // Unconfigured environment — simulates no Supabase setup.
      final supabaseService = SupabaseService(
        environment: const Environment.custom(
          supabaseUrl: '',
          supabaseAnonKey: '',
        ),
      );
      syncRepo = SyncRepository(
        supabaseService: supabaseService,
        sessionDao: sessionDao,
        messageDao: messageDao,
      );
    });

    test(
      'syncPendingSessions returns empty result when not authenticated',
      () async {
        await sessionDao.createSession(
          'session-1',
          DateTime.utc(2026, 2, 20),
          'UTC',
        );

        final result = await syncRepo.syncPendingSessions();
        expect(result.syncedCount, 0);
        expect(result.failedCount, 0);
        expect(result.hasFailures, false);
      },
    );

    test('syncSession is no-op when not authenticated', () async {
      await sessionDao.createSession(
        'session-1',
        DateTime.utc(2026, 2, 20),
        'UTC',
      );

      // Should not throw.
      await syncRepo.syncSession('session-1');

      // Session should still be PENDING.
      final session = await sessionDao.getSessionById('session-1');
      expect(session!.syncStatus, 'PENDING');
    });
  });

  group('SyncRepository - authenticated (no real client)', () {
    late SyncRepository syncRepo;

    setUp(() {
      syncRepo = SyncRepository(
        supabaseService: _FakeAuthenticatedSupabaseService(),
        sessionDao: sessionDao,
        messageDao: messageDao,
      );
    });

    test(
      'syncPendingSessions returns empty result when no sessions to sync',
      () async {
        final result = await syncRepo.syncPendingSessions();
        expect(result.syncedCount, 0);
        expect(result.failedCount, 0);
        expect(result.errors, isEmpty);
      },
    );

    test(
      'syncPendingSessions marks sessions as SYNCED when upload is no-op',
      () async {
        // Create two PENDING sessions.
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

        final result = await syncRepo.syncPendingSessions();
        expect(result.syncedCount, 2);
        expect(result.failedCount, 0);
        expect(result.hasFailures, false);

        // Verify sessions are now SYNCED in the database.
        final s1 = await sessionDao.getSessionById('session-1');
        final s2 = await sessionDao.getSessionById('session-2');
        expect(s1!.syncStatus, 'SYNCED');
        expect(s2!.syncStatus, 'SYNCED');
      },
    );

    test('syncPendingSessions skips already-synced sessions', () async {
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
      await sessionDao.createSession(
        'session-2',
        DateTime.utc(2026, 2, 20, 1),
        'UTC',
      );

      final result = await syncRepo.syncPendingSessions();
      // Only session-2 should be synced (session-1 was already SYNCED).
      expect(result.syncedCount, 1);
      expect(result.failedCount, 0);
    });

    test('syncSession marks a single session as SYNCED', () async {
      await sessionDao.createSession(
        'session-1',
        DateTime.utc(2026, 2, 20),
        'UTC',
      );

      await syncRepo.syncSession('session-1');

      final session = await sessionDao.getSessionById('session-1');
      expect(session!.syncStatus, 'SYNCED');
    });

    test('syncSession is no-op for non-existent session', () async {
      // Should not throw.
      await syncRepo.syncSession('non-existent-id');
    });
  });

  group('SyncResult', () {
    test('hasFailures is true when failedCount > 0', () {
      const result = SyncResult(syncedCount: 1, failedCount: 1);
      expect(result.hasFailures, true);
    });

    test('hasFailures is false when failedCount is 0', () {
      const result = SyncResult(syncedCount: 2, failedCount: 0);
      expect(result.hasFailures, false);
    });

    test('default constructor has zero counts', () {
      const result = SyncResult();
      expect(result.syncedCount, 0);
      expect(result.failedCount, 0);
      expect(result.errors, isEmpty);
    });

    test('errors list captures failure messages', () {
      const result = SyncResult(
        syncedCount: 0,
        failedCount: 2,
        errors: ['Session a: timeout', 'Session b: network error'],
      );
      expect(result.errors, hasLength(2));
      expect(result.errors.first, contains('timeout'));
    });
  });
}
