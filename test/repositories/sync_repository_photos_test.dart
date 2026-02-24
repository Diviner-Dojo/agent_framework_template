import 'dart:io';

import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/config/environment.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/message_dao.dart';
import 'package:agentic_journal/database/daos/photo_dao.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';
import 'package:agentic_journal/repositories/sync_repository.dart';
import 'package:agentic_journal/services/photo_service.dart';
import 'package:agentic_journal/services/supabase_service.dart';

/// Unauthenticated Supabase service for testing no-op paths.
class _FakeUnauthenticatedSupabaseService extends SupabaseService {
  _FakeUnauthenticatedSupabaseService()
    : super(
        environment: const Environment.custom(
          supabaseUrl: '',
          supabaseAnonKey: '',
        ),
      );
}

/// Authenticated Supabase service for testing upload paths.
/// Client returns null (no real Supabase).
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

/// Exercises the SyncResult data class.
void _syncResultTests() {
  group('SyncResult', () {
    test('hasFailures returns false when no failures', () {
      const result = SyncResult(syncedCount: 3, failedCount: 0);
      expect(result.hasFailures, false);
    });

    test('hasFailures returns true when failures exist', () {
      const result = SyncResult(
        syncedCount: 1,
        failedCount: 2,
        errors: ['Error 1', 'Error 2'],
      );
      expect(result.hasFailures, true);
    });

    test('defaults to zero counts and empty errors', () {
      const result = SyncResult();
      expect(result.syncedCount, 0);
      expect(result.failedCount, 0);
      expect(result.errors, isEmpty);
      expect(result.hasFailures, false);
    });
  });
}

void main() {
  _syncResultTests();
  late AppDatabase database;
  late SessionDao sessionDao;
  late MessageDao messageDao;
  late PhotoDao photoDao;

  setUp(() {
    database = AppDatabase.forTesting(NativeDatabase.memory());
    sessionDao = SessionDao(database);
    messageDao = MessageDao(database);
    photoDao = PhotoDao(database);
  });

  tearDown(() async {
    await database.close();
  });

  group('SyncRepository photo sync - unauthenticated', () {
    late SyncRepository syncRepo;

    setUp(() {
      syncRepo = SyncRepository(
        supabaseService: _FakeUnauthenticatedSupabaseService(),
        sessionDao: sessionDao,
        messageDao: messageDao,
        photoDao: photoDao,
      );
    });

    test(
      'uploadSessionPhotos returns empty result when not authenticated',
      () async {
        await sessionDao.createSession(
          'session-1',
          DateTime.utc(2026, 2, 24),
          'UTC',
        );
        await photoDao.insertPhoto(
          photoId: 'photo-1',
          sessionId: 'session-1',
          localPath: '/fake/path.jpg',
          timestamp: DateTime.utc(2026, 2, 24),
        );

        final result = await syncRepo.uploadSessionPhotos('session-1');
        expect(result.syncedCount, 0);
        expect(result.failedCount, 0);
      },
    );

    test(
      'syncPendingPhotos returns empty result when not authenticated',
      () async {
        await sessionDao.createSession(
          'session-1',
          DateTime.utc(2026, 2, 24),
          'UTC',
        );
        await photoDao.insertPhoto(
          photoId: 'photo-1',
          sessionId: 'session-1',
          localPath: '/fake/path.jpg',
          timestamp: DateTime.utc(2026, 2, 24),
        );

        final result = await syncRepo.syncPendingPhotos();
        expect(result.syncedCount, 0);
        expect(result.failedCount, 0);
      },
    );
  });

  group('SyncRepository photo sync - no PhotoDao', () {
    late SyncRepository syncRepo;

    setUp(() {
      syncRepo = SyncRepository(
        supabaseService: _FakeAuthenticatedSupabaseService(),
        sessionDao: sessionDao,
        messageDao: messageDao,
        // No photoDao
      );
    });

    test('uploadSessionPhotos returns empty result without PhotoDao', () async {
      final result = await syncRepo.uploadSessionPhotos('session-1');
      expect(result.syncedCount, 0);
      expect(result.failedCount, 0);
    });

    test('syncPendingPhotos returns empty result without PhotoDao', () async {
      final result = await syncRepo.syncPendingPhotos();
      expect(result.syncedCount, 0);
      expect(result.failedCount, 0);
    });
  });

  group('SyncRepository photo sync - authenticated (no real client)', () {
    late SyncRepository syncRepo;

    setUp(() {
      syncRepo = SyncRepository(
        supabaseService: _FakeAuthenticatedSupabaseService(),
        sessionDao: sessionDao,
        messageDao: messageDao,
        photoDao: photoDao,
      );
    });

    test(
      'uploadSessionPhotos returns empty result when no photos for session',
      () async {
        await sessionDao.createSession(
          'session-1',
          DateTime.utc(2026, 2, 24),
          'UTC',
        );

        final result = await syncRepo.uploadSessionPhotos('session-1');
        expect(result.syncedCount, 0);
        expect(result.failedCount, 0);
      },
    );

    test('uploadSessionPhotos skips already-synced photos', () async {
      await sessionDao.createSession(
        'session-1',
        DateTime.utc(2026, 2, 24),
        'UTC',
      );
      await photoDao.insertPhoto(
        photoId: 'photo-1',
        sessionId: 'session-1',
        localPath: '/fake/path.jpg',
        timestamp: DateTime.utc(2026, 2, 24),
      );
      await photoDao.updateSyncStatus('photo-1', 'SYNCED');

      final result = await syncRepo.uploadSessionPhotos('session-1');
      expect(result.syncedCount, 0);
      expect(result.failedCount, 0);
    });

    test(
      'syncPendingPhotos returns empty result when no photos to sync',
      () async {
        final result = await syncRepo.syncPendingPhotos();
        expect(result.syncedCount, 0);
        expect(result.failedCount, 0);
      },
    );
  });

  group('PhotoDao integration for sync', () {
    test('getPhotosToSync returns PENDING and FAILED photos', () async {
      await sessionDao.createSession(
        'session-1',
        DateTime.utc(2026, 2, 24),
        'UTC',
      );

      await photoDao.insertPhoto(
        photoId: 'photo-pending',
        sessionId: 'session-1',
        localPath: '/path/pending.jpg',
        timestamp: DateTime.utc(2026, 2, 24),
      );
      await photoDao.insertPhoto(
        photoId: 'photo-synced',
        sessionId: 'session-1',
        localPath: '/path/synced.jpg',
        timestamp: DateTime.utc(2026, 2, 24, 1),
      );
      await photoDao.updateSyncStatus('photo-synced', 'SYNCED');

      await photoDao.insertPhoto(
        photoId: 'photo-failed',
        sessionId: 'session-1',
        localPath: '/path/failed.jpg',
        timestamp: DateTime.utc(2026, 2, 24, 2),
      );
      await photoDao.updateSyncStatus('photo-failed', 'FAILED');

      final toSync = await photoDao.getPhotosToSync();
      expect(toSync, hasLength(2));
      expect(toSync.map((p) => p.photoId).toSet(), {
        'photo-pending',
        'photo-failed',
      });
    });

    test('updateCloudUrl sets the cloud URL', () async {
      await sessionDao.createSession(
        'session-1',
        DateTime.utc(2026, 2, 24),
        'UTC',
      );
      await photoDao.insertPhoto(
        photoId: 'photo-1',
        sessionId: 'session-1',
        localPath: '/path/photo.jpg',
        timestamp: DateTime.utc(2026, 2, 24),
      );

      await photoDao.updateCloudUrl(
        'photo-1',
        'https://storage.example.com/photo-1.jpg',
      );

      final photo = await photoDao.getPhotoById('photo-1');
      expect(photo!.cloudUrl, 'https://storage.example.com/photo-1.jpg');
    });
  });

  group('PhotoService file operations', () {
    test(
      'deletePhotoFile is no-op when platform bindings unavailable',
      () async {
        final tempDir = Directory.systemTemp.createTempSync('sync_photos_test');
        addTearDown(() => tempDir.deleteSync(recursive: true));

        final tempFile = File('${tempDir.path}/test.jpg');
        tempFile.writeAsBytesSync([0xFF, 0xD8, 0xFF, 0xE0]);
        expect(tempFile.existsSync(), true);

        final service = PhotoService();
        // Without platform bindings, deletePhotoFile refuses to delete (safe).
        await service.deletePhotoFile(tempFile.path);

        // File should still exist — path confinement cannot determine the
        // photos directory without bindings, so it refuses to delete.
        expect(tempFile.existsSync(), true);
      },
    );

    test('deletePhotoFile is no-op for nonexistent file', () async {
      final service = PhotoService();
      // Should not throw even without bindings.
      await service.deletePhotoFile('/nonexistent/path.jpg');
    });
  });
}
