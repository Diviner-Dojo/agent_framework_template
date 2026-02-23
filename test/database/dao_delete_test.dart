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
  });

  tearDown(() async {
    await database.close();
  });

  group('SessionDao.deleteSession', () {
    test('deletes an existing session and returns 1', () async {
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 23), 'UTC');

      final deleted = await sessionDao.deleteSession('s1');
      expect(deleted, 1);

      final result = await sessionDao.getSessionById('s1');
      expect(result, isNull);
    });

    test('returns 0 for non-existent session', () async {
      final deleted = await sessionDao.deleteSession('does-not-exist');
      expect(deleted, 0);
    });

    test('does not affect other sessions', () async {
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 23), 'UTC');
      await sessionDao.createSession('s2', DateTime.utc(2026, 2, 24), 'UTC');

      await sessionDao.deleteSession('s1');

      final s1 = await sessionDao.getSessionById('s1');
      final s2 = await sessionDao.getSessionById('s2');
      expect(s1, isNull);
      expect(s2, isNotNull);
    });
  });

  group('SessionDao.deleteAllSessions', () {
    test('deletes all sessions and returns count', () async {
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 23), 'UTC');
      await sessionDao.createSession('s2', DateTime.utc(2026, 2, 24), 'UTC');

      final deleted = await sessionDao.deleteAllSessions();
      expect(deleted, 2);

      final remaining = await sessionDao.getAllSessionsByDate();
      expect(remaining, isEmpty);
    });

    test('returns 0 when no sessions exist', () async {
      final deleted = await sessionDao.deleteAllSessions();
      expect(deleted, 0);
    });
  });

  group('MessageDao.deleteMessagesBySession', () {
    test('deletes all messages for a session', () async {
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 23), 'UTC');
      await messageDao.insertMessage(
        'm1',
        's1',
        'ASSISTANT',
        'Hello',
        DateTime.utc(2026, 2, 23, 10, 0),
      );
      await messageDao.insertMessage(
        'm2',
        's1',
        'USER',
        'Hi there',
        DateTime.utc(2026, 2, 23, 10, 1),
      );

      final deleted = await messageDao.deleteMessagesBySession('s1');
      expect(deleted, 2);

      final remaining = await messageDao.getMessagesForSession('s1');
      expect(remaining, isEmpty);
    });

    test('does not affect messages in other sessions', () async {
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 23), 'UTC');
      await sessionDao.createSession('s2', DateTime.utc(2026, 2, 24), 'UTC');
      await messageDao.insertMessage(
        'm1',
        's1',
        'USER',
        'Message in s1',
        DateTime.utc(2026, 2, 23, 10, 0),
      );
      await messageDao.insertMessage(
        'm2',
        's2',
        'USER',
        'Message in s2',
        DateTime.utc(2026, 2, 24, 10, 0),
      );

      await messageDao.deleteMessagesBySession('s1');

      final s1Messages = await messageDao.getMessagesForSession('s1');
      final s2Messages = await messageDao.getMessagesForSession('s2');
      expect(s1Messages, isEmpty);
      expect(s2Messages.length, 1);
    });

    test('returns 0 for non-existent session', () async {
      final deleted = await messageDao.deleteMessagesBySession('no-such');
      expect(deleted, 0);
    });
  });

  group('MessageDao.deleteAllMessages', () {
    test('deletes all messages across all sessions', () async {
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 23), 'UTC');
      await sessionDao.createSession('s2', DateTime.utc(2026, 2, 24), 'UTC');
      await messageDao.insertMessage(
        'm1',
        's1',
        'USER',
        'Msg 1',
        DateTime.utc(2026, 2, 23, 10, 0),
      );
      await messageDao.insertMessage(
        'm2',
        's2',
        'USER',
        'Msg 2',
        DateTime.utc(2026, 2, 24, 10, 0),
      );

      final deleted = await messageDao.deleteAllMessages();
      expect(deleted, 2);
    });

    test('returns 0 when no messages exist', () async {
      final deleted = await messageDao.deleteAllMessages();
      expect(deleted, 0);
    });
  });

  group('MessageDao.getMessageCountByRole', () {
    test('counts USER messages only', () async {
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 23), 'UTC');
      await messageDao.insertMessage(
        'm1',
        's1',
        'ASSISTANT',
        'Hello',
        DateTime.utc(2026, 2, 23, 10, 0),
      );
      await messageDao.insertMessage(
        'm2',
        's1',
        'USER',
        'Hi',
        DateTime.utc(2026, 2, 23, 10, 1),
      );
      await messageDao.insertMessage(
        'm3',
        's1',
        'USER',
        'I feel good',
        DateTime.utc(2026, 2, 23, 10, 2),
      );

      final userCount = await messageDao.getMessageCountByRole('s1', 'USER');
      expect(userCount, 2);

      final assistantCount = await messageDao.getMessageCountByRole(
        's1',
        'ASSISTANT',
      );
      expect(assistantCount, 1);
    });

    test('returns 0 when no messages of that role exist', () async {
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 23), 'UTC');
      await messageDao.insertMessage(
        'm1',
        's1',
        'ASSISTANT',
        'Hello',
        DateTime.utc(2026, 2, 23, 10, 0),
      );

      final count = await messageDao.getMessageCountByRole('s1', 'USER');
      expect(count, 0);
    });

    test('returns 0 for non-existent session', () async {
      final count = await messageDao.getMessageCountByRole('no-such', 'USER');
      expect(count, 0);
    });
  });

  group('cascade delete (application-level)', () {
    test('messages first, then session — correct order', () async {
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 23), 'UTC');
      await messageDao.insertMessage(
        'm1',
        's1',
        'ASSISTANT',
        'Hello',
        DateTime.utc(2026, 2, 23, 10, 0),
      );
      await messageDao.insertMessage(
        'm2',
        's1',
        'USER',
        'Hi',
        DateTime.utc(2026, 2, 23, 10, 1),
      );

      // Correct cascade order: messages first, then session.
      final messagesDeleted = await messageDao.deleteMessagesBySession('s1');
      final sessionDeleted = await sessionDao.deleteSession('s1');

      expect(messagesDeleted, 2);
      expect(sessionDeleted, 1);

      // Both should be gone.
      expect(await messageDao.getMessagesForSession('s1'), isEmpty);
      expect(await sessionDao.getSessionById('s1'), isNull);
    });
  });
}
