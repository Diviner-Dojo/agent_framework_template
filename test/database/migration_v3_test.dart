import 'package:flutter_test/flutter_test.dart';
import 'package:drift/native.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/message_dao.dart';
import 'package:agentic_journal/database/daos/photo_dao.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';

void main() {
  group('Schema v3 migration', () {
    test('new database has photos table and photoId on messages', () async {
      final database = AppDatabase.forTesting(NativeDatabase.memory());
      final sessionDao = SessionDao(database);
      final messageDao = MessageDao(database);
      final photoDao = PhotoDao(database);

      // Create a session, message with photoId, and a photo record.
      final now = DateTime.utc(2026, 2, 24, 10, 0);
      await sessionDao.createSession('test-session', now, 'UTC');

      await photoDao.insertPhoto(
        photoId: 'photo-1',
        sessionId: 'test-session',
        localPath: 'photos/test-session/photo-1.jpg',
        timestamp: now,
        messageId: 'msg-photo',
        width: 1024,
        height: 768,
        fileSizeBytes: 150000,
      );

      await messageDao.insertMessage(
        'msg-photo',
        'test-session',
        'USER',
        '[Photo]',
        now,
        inputMethod: 'PHOTO',
        photoId: 'photo-1',
      );

      // Verify photo was created correctly.
      final photo = await photoDao.getPhotoById('photo-1');
      expect(photo, isNotNull);
      expect(photo!.sessionId, 'test-session');
      expect(photo.localPath, 'photos/test-session/photo-1.jpg');
      expect(photo.messageId, 'msg-photo');
      expect(photo.width, 1024);
      expect(photo.height, 768);
      expect(photo.fileSizeBytes, 150000);
      expect(photo.syncStatus, 'PENDING');
      expect(photo.cloudUrl, isNull);
      expect(photo.description, isNull);

      // Verify message has photoId.
      final messages = await messageDao.getMessagesForSession('test-session');
      expect(messages.length, 1);
      expect(messages[0].photoId, 'photo-1');
      expect(messages[0].inputMethod, 'PHOTO');

      await database.close();
    });

    test(
      'v2 data survives upgrade to v3 (simulated via fresh insert)',
      () async {
        final database = AppDatabase.forTesting(NativeDatabase.memory());
        final sessionDao = SessionDao(database);
        final messageDao = MessageDao(database);

        // Create pre-existing v2 data (session + message without photoId).
        final start = DateTime.utc(2026, 1, 15, 8, 0);
        await sessionDao.createSession('old-session', start, 'America/Denver');
        await messageDao.insertMessage(
          'msg-1',
          'old-session',
          'USER',
          'Hello world',
          start,
        );

        // Verify v2 fields are intact.
        final session = await sessionDao.getSessionById('old-session');
        expect(session, isNotNull);
        expect(session!.startTime, start);
        expect(session.isResumed, false);
        expect(session.resumeCount, 0);

        // Verify message has null photoId (v3 column default).
        final messages = await messageDao.getMessagesForSession('old-session');
        expect(messages.length, 1);
        expect(messages[0].photoId, isNull);

        await database.close();
      },
    );

    test('schemaVersion is 5', () async {
      final database = AppDatabase.forTesting(NativeDatabase.memory());
      expect(database.schemaVersion, 5);
      await database.close();
    });

    test('photos table supports CRUD operations', () async {
      final database = AppDatabase.forTesting(NativeDatabase.memory());
      final sessionDao = SessionDao(database);
      final photoDao = PhotoDao(database);

      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 24), 'UTC');

      // Insert.
      await photoDao.insertPhoto(
        photoId: 'p1',
        sessionId: 's1',
        localPath: 'photos/s1/p1.jpg',
        timestamp: DateTime.utc(2026, 2, 24, 10, 0),
      );

      // Read.
      final photo = await photoDao.getPhotoById('p1');
      expect(photo, isNotNull);

      // Update.
      await photoDao.updateDescription('p1', 'A nice photo');
      final updated = await photoDao.getPhotoById('p1');
      expect(updated!.description, 'A nice photo');

      // Delete.
      final deleted = await photoDao.deletePhoto('p1');
      expect(deleted, 1);
      expect(await photoDao.getPhotoById('p1'), isNull);

      await database.close();
    });
  });
}
