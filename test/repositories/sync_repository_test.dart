import 'package:flutter_test/flutter_test.dart';
import 'package:drift/drift.dart' hide isNull, isNotNull;
import 'package:drift/native.dart';
import 'package:agentic_journal/config/environment.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/calendar_event_dao.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';
import 'package:agentic_journal/database/daos/message_dao.dart';
import 'package:agentic_journal/repositories/sync_repository.dart';
import 'package:agentic_journal/services/supabase_service.dart';
import 'package:supabase_flutter/supabase_flutter.dart' show PostgrestException;

/// A mock SupabaseService that reports as authenticated but has no real client.
///
/// This allows testing the authenticated code paths in SyncRepository without
/// requiring actual Supabase initialization. Since [client] returns null,
/// `uploadSession` returns early (no-op), so sessions get marked as SYNCED
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

/// A SyncRepository subclass that overrides [uploadSession] for testing.
///
/// Tracks upload calls and can be configured to throw on specific session IDs,
/// enabling tests for partial failure, exception paths, and upload invocation
/// without requiring a real Supabase client.
class _TestSyncRepository extends SyncRepository {
  final List<String> uploadedSessionIds = [];
  final Set<String> failOnSessionIds;

  /// When set, failed sessions throw this exception instead of a generic one.
  /// Used for E16 fatal sync error classification tests.
  final Exception Function(String sessionId)? exceptionFactory;

  _TestSyncRepository({
    required super.supabaseService,
    required super.sessionDao,
    required super.messageDao,
    this.failOnSessionIds = const {},
    this.exceptionFactory,
  });

  @override
  Future<void> uploadSession(JournalSession session) async {
    if (failOnSessionIds.contains(session.sessionId)) {
      throw exceptionFactory?.call(session.sessionId) ??
          Exception('Simulated upload failure for ${session.sessionId}');
    }
    uploadedSessionIds.add(session.sessionId);
  }
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

  group('SyncRepository - upload invocation via _TestSyncRepository', () {
    late _TestSyncRepository syncRepo;

    setUp(() {
      syncRepo = _TestSyncRepository(
        supabaseService: _FakeAuthenticatedSupabaseService(),
        sessionDao: sessionDao,
        messageDao: messageDao,
      );
    });

    test(
      'syncPendingSessions invokes uploadSession for each pending session',
      () async {
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
        expect(syncRepo.uploadedSessionIds, ['session-1', 'session-2']);

        // Both sessions marked SYNCED.
        final s1 = await sessionDao.getSessionById('session-1');
        final s2 = await sessionDao.getSessionById('session-2');
        expect(s1!.syncStatus, 'SYNCED');
        expect(s2!.syncStatus, 'SYNCED');
      },
    );

    test('syncSession invokes uploadSession for a single session', () async {
      await sessionDao.createSession(
        'session-1',
        DateTime.utc(2026, 2, 20),
        'UTC',
      );

      await syncRepo.syncSession('session-1');

      expect(syncRepo.uploadedSessionIds, ['session-1']);
      final session = await sessionDao.getSessionById('session-1');
      expect(session!.syncStatus, 'SYNCED');
    });

    test('partial failure: first session syncs, second throws', () async {
      final repo = _TestSyncRepository(
        supabaseService: _FakeAuthenticatedSupabaseService(),
        sessionDao: sessionDao,
        messageDao: messageDao,
        failOnSessionIds: {'session-2'},
      );

      // session-1 is older — will be synced first (ordered by startTime ASC).
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

      final result = await repo.syncPendingSessions();

      expect(result.syncedCount, 1);
      expect(result.failedCount, 1);
      expect(result.hasFailures, true);
      expect(result.errors, hasLength(1));
      expect(result.errors.first, contains('session-2'));

      // session-1 should be SYNCED, session-2 should be FAILED.
      final s1 = await sessionDao.getSessionById('session-1');
      final s2 = await sessionDao.getSessionById('session-2');
      expect(s1!.syncStatus, 'SYNCED');
      expect(s2!.syncStatus, 'FAILED');
    });

    test('syncSession marks session as FAILED when upload throws', () async {
      final repo = _TestSyncRepository(
        supabaseService: _FakeAuthenticatedSupabaseService(),
        sessionDao: sessionDao,
        messageDao: messageDao,
        failOnSessionIds: {'session-1'},
      );

      await sessionDao.createSession(
        'session-1',
        DateTime.utc(2026, 2, 20),
        'UTC',
      );

      await repo.syncSession('session-1');

      final session = await sessionDao.getSessionById('session-1');
      expect(session!.syncStatus, 'FAILED');
      expect(session.lastSyncAttempt, isNotNull);
    });

    test('all sessions fail: result reflects total failures', () async {
      final repo = _TestSyncRepository(
        supabaseService: _FakeAuthenticatedSupabaseService(),
        sessionDao: sessionDao,
        messageDao: messageDao,
        failOnSessionIds: {'session-1', 'session-2'},
      );

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

      final result = await repo.syncPendingSessions();

      expect(result.syncedCount, 0);
      expect(result.failedCount, 2);
      expect(result.errors, hasLength(2));
    });

    test('FAILED sessions are retried on subsequent sync', () async {
      final repo = _TestSyncRepository(
        supabaseService: _FakeAuthenticatedSupabaseService(),
        sessionDao: sessionDao,
        messageDao: messageDao,
        failOnSessionIds: {'session-1'},
      );

      await sessionDao.createSession(
        'session-1',
        DateTime.utc(2026, 2, 20),
        'UTC',
      );

      // First sync: fails.
      await repo.syncPendingSessions();
      final s1 = await sessionDao.getSessionById('session-1');
      expect(s1!.syncStatus, 'FAILED');

      // Now create a repo that succeeds.
      final retryRepo = _TestSyncRepository(
        supabaseService: _FakeAuthenticatedSupabaseService(),
        sessionDao: sessionDao,
        messageDao: messageDao,
      );

      // Second sync: FAILED session is retried and succeeds.
      final result = await retryRepo.syncPendingSessions();
      expect(result.syncedCount, 1);
      expect(result.failedCount, 0);

      final s1After = await sessionDao.getSessionById('session-1');
      expect(s1After!.syncStatus, 'SYNCED');
    });
  });

  group('buildEventUpsertMap', () {
    test('includes all calendar event fields', () {
      final now = DateTime.utc(2026, 2, 25, 12, 0);
      final event = CalendarEvent(
        eventId: 'evt-1',
        sessionId: 'session-1',
        title: 'Team meeting',
        startTime: now,
        endTime: now.add(const Duration(hours: 1)),
        googleEventId: 'google-123',
        status: EventStatus.confirmed,
        syncStatus: EventSyncStatus.pending,
        rawUserMessage: 'Schedule a team meeting at noon',
        createdAt: now,
        updatedAt: now,
      );

      final map = SyncRepository.buildEventUpsertMap(event, 'user-abc');

      expect(map['event_id'], 'evt-1');
      expect(map['session_id'], 'session-1');
      expect(map['user_id'], 'user-abc');
      expect(map['title'], 'Team meeting');
      expect(map['start_time'], now.toIso8601String());
      expect(
        map['end_time'],
        now.add(const Duration(hours: 1)).toIso8601String(),
      );
      expect(map['google_event_id'], 'google-123');
      expect(map['status'], EventStatus.confirmed);
      expect(map['sync_status'], 'SYNCED');
      expect(map['raw_user_message'], 'Schedule a team meeting at noon');
      expect(map['created_at'], now.toIso8601String());
      expect(map['updated_at'], isNotNull);
    });

    test('handles nullable end_time and google_event_id', () {
      final now = DateTime.utc(2026, 2, 25, 12, 0);
      final event = CalendarEvent(
        eventId: 'evt-2',
        sessionId: 'session-1',
        title: 'Reminder: take meds',
        startTime: now,
        status: EventStatus.pendingCreate,
        syncStatus: EventSyncStatus.pending,
        createdAt: now,
        updatedAt: now,
      );

      final map = SyncRepository.buildEventUpsertMap(event, 'user-abc');

      expect(map['end_time'], isNull);
      expect(map['google_event_id'], isNull);
      expect(map['raw_user_message'], isNull);
    });
  });

  group('SyncRepository - calendar event sync', () {
    late AppDatabase database;
    late SessionDao sessionDao;
    late MessageDao messageDao;
    late CalendarEventDao calendarEventDao;

    setUp(() {
      database = AppDatabase.forTesting(NativeDatabase.memory());
      sessionDao = SessionDao(database);
      messageDao = MessageDao(database);
      calendarEventDao = CalendarEventDao(database);
    });

    tearDown(() async {
      await database.close();
    });

    test(
      'syncPendingCalendarEvents returns empty when not authenticated',
      () async {
        final syncRepo = SyncRepository(
          supabaseService: SupabaseService(
            environment: const Environment.custom(
              supabaseUrl: '',
              supabaseAnonKey: '',
            ),
          ),
          sessionDao: sessionDao,
          messageDao: messageDao,
          calendarEventDao: calendarEventDao,
        );

        final result = await syncRepo.syncPendingCalendarEvents();
        expect(result.syncedCount, 0);
        expect(result.failedCount, 0);
      },
    );

    test(
      'syncPendingCalendarEvents returns empty when no dao provided',
      () async {
        final syncRepo = SyncRepository(
          supabaseService: _FakeAuthenticatedSupabaseService(),
          sessionDao: sessionDao,
          messageDao: messageDao,
          // No calendarEventDao
        );

        final result = await syncRepo.syncPendingCalendarEvents();
        expect(result.syncedCount, 0);
        expect(result.failedCount, 0);
      },
    );

    test(
      'syncPendingCalendarEvents returns empty when no events to sync',
      () async {
        final syncRepo = SyncRepository(
          supabaseService: _FakeAuthenticatedSupabaseService(),
          sessionDao: sessionDao,
          messageDao: messageDao,
          calendarEventDao: calendarEventDao,
        );

        final result = await syncRepo.syncPendingCalendarEvents();
        expect(result.syncedCount, 0);
        expect(result.failedCount, 0);
      },
    );

    test('getEventsToSync only returns CONFIRMED+PENDING events', () async {
      // Create a session first (FK constraint).
      await sessionDao.createSession(
        'session-1',
        DateTime.utc(2026, 2, 25),
        'UTC',
      );

      final now = DateTime.utc(2026, 2, 25, 12, 0);

      // CONFIRMED + PENDING → should be included.
      await calendarEventDao.insertEvent(
        CalendarEventsCompanion(
          eventId: const Value('evt-1'),
          sessionId: const Value('session-1'),
          title: const Value('Sync me'),
          startTime: Value(now),
          status: const Value(EventStatus.confirmed),
          syncStatus: const Value(EventSyncStatus.pending),
          createdAt: Value(now),
          updatedAt: Value(now),
        ),
      );

      // PENDING_CREATE + PENDING → should NOT be included (not confirmed yet).
      await calendarEventDao.insertEvent(
        CalendarEventsCompanion(
          eventId: const Value('evt-2'),
          sessionId: const Value('session-1'),
          title: const Value('Not ready'),
          startTime: Value(now),
          status: const Value(EventStatus.pendingCreate),
          syncStatus: const Value(EventSyncStatus.pending),
          createdAt: Value(now),
          updatedAt: Value(now),
        ),
      );

      // CONFIRMED + SYNCED → should NOT be included (already synced).
      await calendarEventDao.insertEvent(
        CalendarEventsCompanion(
          eventId: const Value('evt-3'),
          sessionId: const Value('session-1'),
          title: const Value('Already synced'),
          startTime: Value(now),
          status: const Value(EventStatus.confirmed),
          syncStatus: const Value(EventSyncStatus.synced),
          createdAt: Value(now),
          updatedAt: Value(now),
        ),
      );

      final toSync = await calendarEventDao.getEventsToSync();
      expect(toSync, hasLength(1));
      expect(toSync.first.eventId, 'evt-1');
    });
  });

  group('Fatal sync error classification (E16)', () {
    late AppDatabase fatalDb;
    late SessionDao fatalSessionDao;
    late MessageDao fatalMessageDao;

    setUp(() {
      fatalDb = AppDatabase.forTesting(NativeDatabase.memory());
      fatalSessionDao = SessionDao(fatalDb);
      fatalMessageDao = MessageDao(fatalDb);
    });

    tearDown(() async {
      await fatalDb.close();
    });

    test('PostgrestException class 22 (data exception) → FATAL', () async {
      final repo = _TestSyncRepository(
        supabaseService: _FakeAuthenticatedSupabaseService(),
        sessionDao: fatalSessionDao,
        messageDao: fatalMessageDao,
        failOnSessionIds: {'session-1'},
        exceptionFactory: (_) =>
            PostgrestException(message: 'invalid input syntax', code: '22P02'),
      );

      await fatalSessionDao.createSession(
        'session-1',
        DateTime.utc(2026, 2, 26),
        'UTC',
      );

      await repo.syncPendingSessions();

      final session = await fatalSessionDao.getSessionById('session-1');
      expect(session!.syncStatus, 'FATAL');
    });

    test(
      'PostgrestException class 23 (integrity constraint) → FATAL',
      () async {
        final repo = _TestSyncRepository(
          supabaseService: _FakeAuthenticatedSupabaseService(),
          sessionDao: fatalSessionDao,
          messageDao: fatalMessageDao,
          failOnSessionIds: {'session-1'},
          exceptionFactory: (_) => PostgrestException(
            message: 'violates foreign key constraint',
            code: '23503',
          ),
        );

        await fatalSessionDao.createSession(
          'session-1',
          DateTime.utc(2026, 2, 26),
          'UTC',
        );

        await repo.syncPendingSessions();

        final session = await fatalSessionDao.getSessionById('session-1');
        expect(session!.syncStatus, 'FATAL');
      },
    );

    test('PostgrestException 42501 (RLS violation) → FATAL', () async {
      final repo = _TestSyncRepository(
        supabaseService: _FakeAuthenticatedSupabaseService(),
        sessionDao: fatalSessionDao,
        messageDao: fatalMessageDao,
        failOnSessionIds: {'session-1'},
        exceptionFactory: (_) => PostgrestException(
          message: 'permission denied for table',
          code: '42501',
        ),
      );

      await fatalSessionDao.createSession(
        'session-1',
        DateTime.utc(2026, 2, 26),
        'UTC',
      );

      await repo.syncPendingSessions();

      final session = await fatalSessionDao.getSessionById('session-1');
      expect(session!.syncStatus, 'FATAL');
    });

    test('non-Postgrest exception → FAILED (retryable)', () async {
      final repo = _TestSyncRepository(
        supabaseService: _FakeAuthenticatedSupabaseService(),
        sessionDao: fatalSessionDao,
        messageDao: fatalMessageDao,
        failOnSessionIds: {'session-1'},
      );

      await fatalSessionDao.createSession(
        'session-1',
        DateTime.utc(2026, 2, 26),
        'UTC',
      );

      await repo.syncPendingSessions();

      final session = await fatalSessionDao.getSessionById('session-1');
      expect(session!.syncStatus, 'FAILED');
    });

    test('FATAL sessions are excluded from getSessionsToSync', () async {
      await fatalSessionDao.createSession(
        'session-1',
        DateTime.utc(2026, 2, 26),
        'UTC',
      );
      await fatalSessionDao.updateSyncStatus(
        'session-1',
        'FATAL',
        DateTime.utc(2026, 2, 26),
      );
      await fatalSessionDao.createSession(
        'session-2',
        DateTime.utc(2026, 2, 26, 1),
        'UTC',
      );

      final toSync = await fatalSessionDao.getSessionsToSync();
      expect(toSync, hasLength(1));
      expect(toSync.first.sessionId, 'session-2');
    });

    test('syncSession classifies fatal errors for single session', () async {
      final repo = _TestSyncRepository(
        supabaseService: _FakeAuthenticatedSupabaseService(),
        sessionDao: fatalSessionDao,
        messageDao: fatalMessageDao,
        failOnSessionIds: {'session-1'},
        exceptionFactory: (_) =>
            PostgrestException(message: 'data exception', code: '22003'),
      );

      await fatalSessionDao.createSession(
        'session-1',
        DateTime.utc(2026, 2, 26),
        'UTC',
      );

      await repo.syncSession('session-1');

      final session = await fatalSessionDao.getSessionById('session-1');
      expect(session!.syncStatus, 'FATAL');
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
