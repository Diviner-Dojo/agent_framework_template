import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:drift/native.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/providers/database_provider.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/repositories/agent_repository.dart';

void main() {
  late ProviderContainer container;
  late AppDatabase database;

  setUp(() {
    database = AppDatabase.forTesting(NativeDatabase.memory());
    container = ProviderContainer(
      overrides: [
        // Override the database provider to use in-memory DB.
        databaseProvider.overrideWithValue(database),
        // Override agent repository to Layer A only (no services).
        // Without this override, the provider tries to create ClaudeApiService
        // and ConnectivityService, which need platform plugins unavailable in tests.
        agentRepositoryProvider.overrideWithValue(AgentRepository()),
      ],
    );
  });

  tearDown(() async {
    container.dispose();
    await database.close();
  });

  group('SessionNotifier.startSession', () {
    test(
      'creates a session in the database and adds a greeting message',
      () async {
        final notifier = container.read(sessionNotifierProvider.notifier);
        final sessionId = await notifier.startSession();

        expect(sessionId, isNotEmpty);

        // Verify session was created in the DB.
        final sessionDao = container.read(sessionDaoProvider);
        final session = await sessionDao.getSessionById(sessionId);
        expect(session, isNotNull);
        expect(session!.endTime, isNull);

        // Verify greeting message was saved.
        final messageDao = container.read(messageDaoProvider);
        final messages = await messageDao.getMessagesForSession(sessionId);
        expect(messages.length, 1);
        expect(messages[0].role, 'ASSISTANT');
        expect(messages[0].content, isNotEmpty);
      },
    );

    test('updates session state with active session ID', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      final sessionId = await notifier.startSession();

      final state = container.read(sessionNotifierProvider);
      expect(state.activeSessionId, sessionId);
      expect(state.followUpCount, 0);
    });
  });

  group('SessionNotifier.sendMessage', () {
    test('adds user message and follow-up to the database', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      final sessionId = await notifier.startSession();

      await notifier.sendMessage('I feel stressed about work');

      final messageDao = container.read(messageDaoProvider);
      final messages = await messageDao.getMessagesForSession(sessionId);
      // 1 greeting + 1 user message + 1 follow-up = 3 messages.
      expect(messages.length, 3);
      expect(messages[1].role, 'USER');
      expect(messages[1].content, 'I feel stressed about work');
      expect(messages[2].role, 'ASSISTANT');
    });

    test('increments follow-up count', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      await notifier.startSession();

      await notifier.sendMessage('I feel stressed');

      final state = container.read(sessionNotifierProvider);
      expect(state.followUpCount, 1);
    });
  });

  group('SessionNotifier.endSession', () {
    test('sets end time and summary on the session record', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      final sessionId = await notifier.startSession();

      await notifier.sendMessage('Had a good day at work');
      await notifier.endSession();

      final sessionDao = container.read(sessionDaoProvider);
      final session = await sessionDao.getSessionById(sessionId);
      expect(session, isNotNull);
      expect(session!.endTime, isNotNull);
      // Summary should exist since there was a user message.
      expect(session.summary, isNotNull);
    });

    test('clears active session state', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      await notifier.startSession();
      await notifier.endSession();

      final state = container.read(sessionNotifierProvider);
      expect(state.activeSessionId, isNull);
      expect(state.followUpCount, 0);
    });
  });

  group('SessionNotifier follow-up max', () {
    test('session transitions to closing after max follow-ups', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      final sessionId = await notifier.startSession();

      // Send enough messages to hit the follow-up limit.
      // followUpCount: 0→1→2→3→4
      await notifier.sendMessage('First message'); // followUpCount becomes 1
      await notifier.sendMessage('Second message'); // followUpCount becomes 2
      await notifier.sendMessage('Third message'); // followUpCount becomes 3
      // At followUpCount 3, the agent sends a closing message.
      await notifier.sendMessage('Fourth message'); // followUpCount becomes 4
      // At followUpCount 4, shouldEndSession returns true → auto-end.
      await notifier.sendMessage('Fifth message'); // triggers end

      final state = container.read(sessionNotifierProvider);
      // Session should have ended.
      expect(state.activeSessionId, isNull);

      // Verify session has an end time.
      final sessionDao = container.read(sessionDaoProvider);
      final session = await sessionDao.getSessionById(sessionId);
      expect(session!.endTime, isNotNull);
    });
  });
}
