import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:drift/native.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/photo_dao.dart';
import 'package:agentic_journal/providers/database_provider.dart';
import 'package:agentic_journal/providers/photo_providers.dart';

void main() {
  late AppDatabase database;
  late ProviderContainer container;

  setUp(() {
    database = AppDatabase.forTesting(NativeDatabase.memory());
    container = ProviderContainer(
      overrides: [databaseProvider.overrideWithValue(database)],
    );
  });

  tearDown(() async {
    container.dispose();
    await database.close();
  });

  group('photoDaoProvider', () {
    test('provides a PhotoDao instance', () {
      final photoDao = container.read(photoDaoProvider);
      expect(photoDao, isA<PhotoDao>());
    });
  });

  group('sessionPhotosProvider', () {
    test('emits photos for a specific session', () async {
      final sessionDao = container.read(sessionDaoProvider);
      final photoDao = container.read(photoDaoProvider);

      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 24), 'UTC');
      await photoDao.insertPhoto(
        photoId: 'p1',
        sessionId: 's1',
        localPath: 'photos/s1/p1.jpg',
        timestamp: DateTime.utc(2026, 2, 24, 10, 0),
      );

      // Read the stream provider's current value.
      final photosAsync = await container.read(
        sessionPhotosProvider('s1').future,
      );
      expect(photosAsync.length, 1);
      expect(photosAsync[0].photoId, 'p1');
    });

    test('returns empty for session with no photos', () async {
      final sessionDao = container.read(sessionDaoProvider);
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 24), 'UTC');

      final photos = await container.read(sessionPhotosProvider('s1').future);
      expect(photos, isEmpty);
    });
  });

  group('allPhotosProvider', () {
    test('emits all photos ordered newest first', () async {
      final sessionDao = container.read(sessionDaoProvider);
      final photoDao = container.read(photoDaoProvider);

      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 24), 'UTC');
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

      final photos = await container.read(allPhotosProvider.future);
      expect(photos.length, 2);
      expect(photos[0].photoId, 'p2'); // Newest first.
    });
  });

  group('photoCountProvider', () {
    test('returns correct count', () async {
      final sessionDao = container.read(sessionDaoProvider);
      final photoDao = container.read(photoDaoProvider);

      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 24), 'UTC');
      await photoDao.insertPhoto(
        photoId: 'p1',
        sessionId: 's1',
        localPath: 'photos/s1/p1.jpg',
        timestamp: DateTime.utc(2026, 2, 24, 10, 0),
      );

      final count = await container.read(photoCountProvider.future);
      expect(count, 1);
    });
  });

  group('photoStorageInfoProvider', () {
    test('returns combined count and size', () async {
      final sessionDao = container.read(sessionDaoProvider);
      final photoDao = container.read(photoDaoProvider);

      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 24), 'UTC');
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

      final info = await container.read(photoStorageInfoProvider.future);
      expect(info.count, 2);
      expect(info.totalSizeBytes, 300000);
    });
  });

  group('PhotoStorageInfo.formattedSize', () {
    test('formats bytes', () {
      const info = PhotoStorageInfo(count: 1, totalSizeBytes: 500);
      expect(info.formattedSize, '500 B');
    });

    test('formats kilobytes', () {
      const info = PhotoStorageInfo(count: 1, totalSizeBytes: 5120);
      expect(info.formattedSize, '5.0 KB');
    });

    test('formats megabytes', () {
      const info = PhotoStorageInfo(count: 1, totalSizeBytes: 5242880);
      expect(info.formattedSize, '5.0 MB');
    });
  });

  group('cascade delete with photos', () {
    test(
      'deleteSessionCascade removes photos, messages, and session',
      () async {
        final sessionDao = container.read(sessionDaoProvider);
        final messageDao = container.read(messageDaoProvider);
        final photoDao = container.read(photoDaoProvider);

        await sessionDao.createSession('s1', DateTime.utc(2026, 2, 24), 'UTC');
        await messageDao.insertMessage(
          'm1',
          's1',
          'USER',
          'Hello',
          DateTime.utc(2026, 2, 24, 10, 0),
        );
        await photoDao.insertPhoto(
          photoId: 'p1',
          sessionId: 's1',
          localPath: 'photos/s1/p1.jpg',
          timestamp: DateTime.utc(2026, 2, 24, 10, 0),
        );

        await sessionDao.deleteSessionCascade(
          messageDao,
          's1',
          photoDao: photoDao,
        );

        expect(await sessionDao.getSessionById('s1'), isNull);
        expect(await messageDao.getMessagesForSession('s1'), isEmpty);
        expect(await photoDao.getPhotosForSession('s1'), isEmpty);
      },
    );

    test(
      'deleteAllCascade removes all photos, messages, and sessions',
      () async {
        final sessionDao = container.read(sessionDaoProvider);
        final messageDao = container.read(messageDaoProvider);
        final photoDao = container.read(photoDaoProvider);

        await sessionDao.createSession('s1', DateTime.utc(2026, 2, 24), 'UTC');
        await photoDao.insertPhoto(
          photoId: 'p1',
          sessionId: 's1',
          localPath: 'photos/s1/p1.jpg',
          timestamp: DateTime.utc(2026, 2, 24, 10, 0),
        );

        await sessionDao.deleteAllCascade(messageDao, photoDao: photoDao);

        expect(await sessionDao.getAllSessionsByDate(), isEmpty);
        expect(await photoDao.getPhotoCount(), 0);
      },
    );

    test(
      'deleteSessionCascade works without photoDao (backward compatible)',
      () async {
        final sessionDao = container.read(sessionDaoProvider);
        final messageDao = container.read(messageDaoProvider);

        await sessionDao.createSession('s1', DateTime.utc(2026, 2, 24), 'UTC');
        await messageDao.insertMessage(
          'm1',
          's1',
          'USER',
          'Hello',
          DateTime.utc(2026, 2, 24, 10, 0),
        );

        // Call without photoDao — should still work.
        await sessionDao.deleteSessionCascade(messageDao, 's1');

        expect(await sessionDao.getSessionById('s1'), isNull);
        expect(await messageDao.getMessagesForSession('s1'), isEmpty);
      },
    );
  });
}
