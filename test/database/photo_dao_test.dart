import 'package:flutter_test/flutter_test.dart';
import 'package:drift/native.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/photo_dao.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';

void main() {
  late AppDatabase database;
  late PhotoDao photoDao;
  late SessionDao sessionDao;

  setUp(() async {
    database = AppDatabase.forTesting(NativeDatabase.memory());
    photoDao = PhotoDao(database);
    sessionDao = SessionDao(database);
    // Create a session for photos to reference.
    await sessionDao.createSession('s1', DateTime.utc(2026, 2, 24), 'UTC');
  });

  tearDown(() async {
    await database.close();
  });

  group('insertPhoto and getPhotoById', () {
    test('inserts and retrieves a photo', () async {
      await photoDao.insertPhoto(
        photoId: 'p1',
        sessionId: 's1',
        localPath: 'photos/s1/p1.jpg',
        timestamp: DateTime.utc(2026, 2, 24, 10, 0),
        width: 1024,
        height: 768,
        fileSizeBytes: 150000,
      );

      final photo = await photoDao.getPhotoById('p1');
      expect(photo, isNotNull);
      expect(photo!.photoId, 'p1');
      expect(photo.sessionId, 's1');
      expect(photo.localPath, 'photos/s1/p1.jpg');
      expect(photo.width, 1024);
      expect(photo.height, 768);
      expect(photo.fileSizeBytes, 150000);
      expect(photo.syncStatus, 'PENDING');
      expect(photo.cloudUrl, isNull);
      expect(photo.description, isNull);
      expect(photo.messageId, isNull);
    });

    test('returns null for non-existent photo', () async {
      final photo = await photoDao.getPhotoById('no-such');
      expect(photo, isNull);
    });

    test('inserts photo with messageId and description', () async {
      await photoDao.insertPhoto(
        photoId: 'p2',
        sessionId: 's1',
        localPath: 'photos/s1/p2.jpg',
        timestamp: DateTime.utc(2026, 2, 24, 10, 5),
        messageId: 'msg-1',
        description: 'A sunset photo',
      );

      final photo = await photoDao.getPhotoById('p2');
      expect(photo!.messageId, 'msg-1');
      expect(photo.description, 'A sunset photo');
    });
  });

  group('getPhotosForSession', () {
    test('returns photos ordered by timestamp ascending', () async {
      await photoDao.insertPhoto(
        photoId: 'p2',
        sessionId: 's1',
        localPath: 'photos/s1/p2.jpg',
        timestamp: DateTime.utc(2026, 2, 24, 11, 0),
      );
      await photoDao.insertPhoto(
        photoId: 'p1',
        sessionId: 's1',
        localPath: 'photos/s1/p1.jpg',
        timestamp: DateTime.utc(2026, 2, 24, 10, 0),
      );

      final photos = await photoDao.getPhotosForSession('s1');
      expect(photos.length, 2);
      expect(photos[0].photoId, 'p1'); // Earlier timestamp first.
      expect(photos[1].photoId, 'p2');
    });

    test('returns empty list for session with no photos', () async {
      final photos = await photoDao.getPhotosForSession('s1');
      expect(photos, isEmpty);
    });

    test('does not return photos from other sessions', () async {
      await sessionDao.createSession('s2', DateTime.utc(2026, 2, 25), 'UTC');
      await photoDao.insertPhoto(
        photoId: 'p1',
        sessionId: 's1',
        localPath: 'photos/s1/p1.jpg',
        timestamp: DateTime.utc(2026, 2, 24, 10, 0),
      );
      await photoDao.insertPhoto(
        photoId: 'p2',
        sessionId: 's2',
        localPath: 'photos/s2/p2.jpg',
        timestamp: DateTime.utc(2026, 2, 25, 10, 0),
      );

      final photos = await photoDao.getPhotosForSession('s1');
      expect(photos.length, 1);
      expect(photos[0].photoId, 'p1');
    });
  });

  group('watchPhotosForSession', () {
    test('emits updates when photos are added', () async {
      final stream = photoDao.watchPhotosForSession('s1');

      // First emission: empty.
      expect(stream, emitsInOrder([isEmpty, hasLength(1)]));

      await photoDao.insertPhoto(
        photoId: 'p1',
        sessionId: 's1',
        localPath: 'photos/s1/p1.jpg',
        timestamp: DateTime.utc(2026, 2, 24, 10, 0),
      );
    });
  });

  group('getPhotoByMessageId', () {
    test('returns photo linked to a message', () async {
      await photoDao.insertPhoto(
        photoId: 'p1',
        sessionId: 's1',
        localPath: 'photos/s1/p1.jpg',
        timestamp: DateTime.utc(2026, 2, 24, 10, 0),
        messageId: 'msg-1',
      );

      final photo = await photoDao.getPhotoByMessageId('msg-1');
      expect(photo, isNotNull);
      expect(photo!.photoId, 'p1');
    });

    test('returns null for message with no photo', () async {
      final photo = await photoDao.getPhotoByMessageId('no-such');
      expect(photo, isNull);
    });
  });

  group('getAllPhotos', () {
    test('returns all photos ordered newest first', () async {
      await sessionDao.createSession('s2', DateTime.utc(2026, 2, 25), 'UTC');
      await photoDao.insertPhoto(
        photoId: 'p1',
        sessionId: 's1',
        localPath: 'photos/s1/p1.jpg',
        timestamp: DateTime.utc(2026, 2, 24, 10, 0),
      );
      await photoDao.insertPhoto(
        photoId: 'p2',
        sessionId: 's2',
        localPath: 'photos/s2/p2.jpg',
        timestamp: DateTime.utc(2026, 2, 25, 10, 0),
      );

      final photos = await photoDao.getAllPhotos();
      expect(photos.length, 2);
      expect(photos[0].photoId, 'p2'); // Newest first.
      expect(photos[1].photoId, 'p1');
    });
  });

  group('getPhotoCount', () {
    test('returns correct count', () async {
      expect(await photoDao.getPhotoCount(), 0);

      await photoDao.insertPhoto(
        photoId: 'p1',
        sessionId: 's1',
        localPath: 'photos/s1/p1.jpg',
        timestamp: DateTime.utc(2026, 2, 24, 10, 0),
      );
      expect(await photoDao.getPhotoCount(), 1);

      await photoDao.insertPhoto(
        photoId: 'p2',
        sessionId: 's1',
        localPath: 'photos/s1/p2.jpg',
        timestamp: DateTime.utc(2026, 2, 24, 11, 0),
      );
      expect(await photoDao.getPhotoCount(), 2);
    });
  });

  group('getTotalPhotoSize', () {
    test('returns sum of file sizes', () async {
      await photoDao.insertPhoto(
        photoId: 'p1',
        sessionId: 's1',
        localPath: 'photos/s1/p1.jpg',
        timestamp: DateTime.utc(2026, 2, 24, 10, 0),
        fileSizeBytes: 100000,
      );
      await photoDao.insertPhoto(
        photoId: 'p2',
        sessionId: 's1',
        localPath: 'photos/s1/p2.jpg',
        timestamp: DateTime.utc(2026, 2, 24, 11, 0),
        fileSizeBytes: 200000,
      );

      final totalSize = await photoDao.getTotalPhotoSize();
      expect(totalSize, 300000);
    });

    test('returns 0 when no photos exist', () async {
      final totalSize = await photoDao.getTotalPhotoSize();
      expect(totalSize, 0);
    });
  });

  group('updateDescription', () {
    test('updates the description of a photo', () async {
      await photoDao.insertPhoto(
        photoId: 'p1',
        sessionId: 's1',
        localPath: 'photos/s1/p1.jpg',
        timestamp: DateTime.utc(2026, 2, 24, 10, 0),
      );

      await photoDao.updateDescription('p1', 'My morning coffee');

      final photo = await photoDao.getPhotoById('p1');
      expect(photo!.description, 'My morning coffee');
    });
  });

  group('updateCloudUrl', () {
    test('updates the cloud URL after upload', () async {
      await photoDao.insertPhoto(
        photoId: 'p1',
        sessionId: 's1',
        localPath: 'photos/s1/p1.jpg',
        timestamp: DateTime.utc(2026, 2, 24, 10, 0),
      );

      await photoDao.updateCloudUrl('p1', 'https://storage.example.com/p1.jpg');

      final photo = await photoDao.getPhotoById('p1');
      expect(photo!.cloudUrl, 'https://storage.example.com/p1.jpg');
    });
  });

  group('updateSyncStatus', () {
    test('updates sync status', () async {
      await photoDao.insertPhoto(
        photoId: 'p1',
        sessionId: 's1',
        localPath: 'photos/s1/p1.jpg',
        timestamp: DateTime.utc(2026, 2, 24, 10, 0),
      );

      await photoDao.updateSyncStatus('p1', 'SYNCED');

      final photo = await photoDao.getPhotoById('p1');
      expect(photo!.syncStatus, 'SYNCED');
    });
  });

  group('getPhotosToSync', () {
    test('returns PENDING and FAILED photos', () async {
      await photoDao.insertPhoto(
        photoId: 'p1',
        sessionId: 's1',
        localPath: 'photos/s1/p1.jpg',
        timestamp: DateTime.utc(2026, 2, 24, 10, 0),
      );
      await photoDao.insertPhoto(
        photoId: 'p2',
        sessionId: 's1',
        localPath: 'photos/s1/p2.jpg',
        timestamp: DateTime.utc(2026, 2, 24, 11, 0),
      );
      await photoDao.insertPhoto(
        photoId: 'p3',
        sessionId: 's1',
        localPath: 'photos/s1/p3.jpg',
        timestamp: DateTime.utc(2026, 2, 24, 12, 0),
      );

      // p1 stays PENDING, p2 becomes SYNCED, p3 becomes FAILED.
      await photoDao.updateSyncStatus('p2', 'SYNCED');
      await photoDao.updateSyncStatus('p3', 'FAILED');

      final toSync = await photoDao.getPhotosToSync();
      expect(toSync.length, 2);
      expect(toSync.map((p) => p.photoId), containsAll(['p1', 'p3']));
    });
  });

  group('deletePhoto', () {
    test('deletes a single photo', () async {
      await photoDao.insertPhoto(
        photoId: 'p1',
        sessionId: 's1',
        localPath: 'photos/s1/p1.jpg',
        timestamp: DateTime.utc(2026, 2, 24, 10, 0),
      );

      final deleted = await photoDao.deletePhoto('p1');
      expect(deleted, 1);

      final photo = await photoDao.getPhotoById('p1');
      expect(photo, isNull);
    });

    test('returns 0 for non-existent photo', () async {
      final deleted = await photoDao.deletePhoto('no-such');
      expect(deleted, 0);
    });
  });

  group('deletePhotosBySession', () {
    test('deletes all photos for a session', () async {
      await photoDao.insertPhoto(
        photoId: 'p1',
        sessionId: 's1',
        localPath: 'photos/s1/p1.jpg',
        timestamp: DateTime.utc(2026, 2, 24, 10, 0),
      );
      await photoDao.insertPhoto(
        photoId: 'p2',
        sessionId: 's1',
        localPath: 'photos/s1/p2.jpg',
        timestamp: DateTime.utc(2026, 2, 24, 11, 0),
      );

      final deleted = await photoDao.deletePhotosBySession('s1');
      expect(deleted, 2);

      final remaining = await photoDao.getPhotosForSession('s1');
      expect(remaining, isEmpty);
    });

    test('does not affect photos in other sessions', () async {
      await sessionDao.createSession('s2', DateTime.utc(2026, 2, 25), 'UTC');
      await photoDao.insertPhoto(
        photoId: 'p1',
        sessionId: 's1',
        localPath: 'photos/s1/p1.jpg',
        timestamp: DateTime.utc(2026, 2, 24, 10, 0),
      );
      await photoDao.insertPhoto(
        photoId: 'p2',
        sessionId: 's2',
        localPath: 'photos/s2/p2.jpg',
        timestamp: DateTime.utc(2026, 2, 25, 10, 0),
      );

      await photoDao.deletePhotosBySession('s1');

      final s1Photos = await photoDao.getPhotosForSession('s1');
      final s2Photos = await photoDao.getPhotosForSession('s2');
      expect(s1Photos, isEmpty);
      expect(s2Photos.length, 1);
    });
  });

  group('deleteAllPhotos', () {
    test('deletes all photos across all sessions', () async {
      await sessionDao.createSession('s2', DateTime.utc(2026, 2, 25), 'UTC');
      await photoDao.insertPhoto(
        photoId: 'p1',
        sessionId: 's1',
        localPath: 'photos/s1/p1.jpg',
        timestamp: DateTime.utc(2026, 2, 24, 10, 0),
      );
      await photoDao.insertPhoto(
        photoId: 'p2',
        sessionId: 's2',
        localPath: 'photos/s2/p2.jpg',
        timestamp: DateTime.utc(2026, 2, 25, 10, 0),
      );

      final deleted = await photoDao.deleteAllPhotos();
      expect(deleted, 2);

      expect(await photoDao.getPhotoCount(), 0);
    });

    test('returns 0 when no photos exist', () async {
      final deleted = await photoDao.deleteAllPhotos();
      expect(deleted, 0);
    });
  });
}
