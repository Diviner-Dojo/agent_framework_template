import 'package:flutter_test/flutter_test.dart';
import 'package:drift/native.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';
import 'package:agentic_journal/database/daos/message_dao.dart';

void main() {
  late AppDatabase database;
  late SessionDao sessionDao;
  late MessageDao messageDao;

  setUp(() async {
    database = AppDatabase.forTesting(NativeDatabase.memory());
    sessionDao = SessionDao(database);
    messageDao = MessageDao(database);

    // Create a session for messages to reference (FK constraint).
    await sessionDao.createSession(
      'session-a',
      DateTime.utc(2026, 2, 19, 10, 0),
      'UTC',
    );
    await sessionDao.createSession(
      'session-b',
      DateTime.utc(2026, 2, 19, 11, 0),
      'UTC',
    );
  });

  tearDown(() async {
    await database.close();
  });

  group('insertMessage + getMessagesForSession', () {
    test('round-trip: inserted message can be retrieved', () async {
      final ts = DateTime.utc(2026, 2, 19, 10, 1);
      await messageDao.insertMessage('msg-1', 'session-a', 'USER', 'Hello', ts);

      final messages = await messageDao.getMessagesForSession('session-a');
      expect(messages.length, 1);
      expect(messages[0].messageId, 'msg-1');
      expect(messages[0].sessionId, 'session-a');
      expect(messages[0].role, 'USER');
      expect(messages[0].content, 'Hello');
      expect(messages[0].timestamp, ts);
      expect(messages[0].inputMethod, 'TEXT');
    });

    test('messages are ordered by timestamp ascending', () async {
      final t1 = DateTime.utc(2026, 2, 19, 10, 1);
      final t2 = DateTime.utc(2026, 2, 19, 10, 2);
      final t3 = DateTime.utc(2026, 2, 19, 10, 3);

      // Insert out of order.
      await messageDao.insertMessage('msg-3', 'session-a', 'USER', 'Third', t3);
      await messageDao.insertMessage('msg-1', 'session-a', 'USER', 'First', t1);
      await messageDao.insertMessage(
        'msg-2',
        'session-a',
        'ASSISTANT',
        'Second',
        t2,
      );

      final messages = await messageDao.getMessagesForSession('session-a');
      expect(messages.length, 3);
      expect(messages[0].content, 'First');
      expect(messages[1].content, 'Second');
      expect(messages[2].content, 'Third');
    });
  });

  group('cross-session isolation', () {
    test(
      'getMessagesForSession only returns messages for that session',
      () async {
        final ts = DateTime.utc(2026, 2, 19, 10, 1);
        await messageDao.insertMessage(
          'msg-a1',
          'session-a',
          'USER',
          'Message A',
          ts,
        );
        await messageDao.insertMessage(
          'msg-b1',
          'session-b',
          'USER',
          'Message B',
          ts,
        );

        final messagesA = await messageDao.getMessagesForSession('session-a');
        expect(messagesA.length, 1);
        expect(messagesA[0].content, 'Message A');

        final messagesB = await messageDao.getMessagesForSession('session-b');
        expect(messagesB.length, 1);
        expect(messagesB[0].content, 'Message B');
      },
    );
  });

  group('updateMessageContent', () {
    test('updates content and leaves other fields unchanged', () async {
      final ts = DateTime.utc(2026, 2, 19, 10, 1);
      await messageDao.insertMessage(
        'msg-edit',
        'session-a',
        'USER',
        'Shawn helped me today.',
        ts,
      );

      await messageDao.updateMessageContent(
        'msg-edit',
        'Sean helped me today.',
      );

      final messages = await messageDao.getMessagesForSession('session-a');
      expect(messages.length, 1);
      expect(messages.first.content, 'Sean helped me today.');
      expect(messages.first.role, 'USER');
      expect(messages.first.timestamp, ts);
    });

    test('updating a non-existent messageId is a no-op', () async {
      // Should not throw — drift update with no matching rows is silent.
      await expectLater(
        messageDao.updateMessageContent('ghost-id', 'new content'),
        completes,
      );
    });
  });

  group('getMessageCount', () {
    test('returns 0 for session with no messages', () async {
      final count = await messageDao.getMessageCount('session-a');
      expect(count, 0);
    });

    test('returns correct count after multiple inserts', () async {
      final ts = DateTime.utc(2026, 2, 19, 10, 1);
      await messageDao.insertMessage('m1', 'session-a', 'USER', 'One', ts);
      await messageDao.insertMessage('m2', 'session-a', 'ASSISTANT', 'Two', ts);
      await messageDao.insertMessage('m3', 'session-a', 'USER', 'Three', ts);

      final count = await messageDao.getMessageCount('session-a');
      expect(count, 3);
    });

    test('counts are isolated per session', () async {
      final ts = DateTime.utc(2026, 2, 19, 10, 1);
      await messageDao.insertMessage('m1', 'session-a', 'USER', 'One', ts);
      await messageDao.insertMessage('m2', 'session-a', 'USER', 'Two', ts);
      await messageDao.insertMessage('m3', 'session-b', 'USER', 'Three', ts);

      expect(await messageDao.getMessageCount('session-a'), 2);
      expect(await messageDao.getMessageCount('session-b'), 1);
    });
  });
}
