import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:drift/native.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/models/agent_response.dart';
import 'package:agentic_journal/providers/database_provider.dart';
import 'package:agentic_journal/providers/onboarding_providers.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/repositories/agent_repository.dart';

void main() {
  late ProviderContainer container;
  late AppDatabase database;

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    database = AppDatabase.forTesting(NativeDatabase.memory());

    // Create an AgentRepository with journal-only mode ON.
    final journalOnlyAgent = AgentRepository();
    journalOnlyAgent.setJournalOnlyMode(true);

    container = ProviderContainer(
      overrides: [
        databaseProvider.overrideWithValue(database),
        agentRepositoryProvider.overrideWithValue(journalOnlyAgent),
        sharedPreferencesProvider.overrideWithValue(prefs),
        deviceTimezoneProvider.overrideWith((ref) async => 'America/New_York'),
      ],
    );
  });

  tearDown(() async {
    container.dispose();
    await database.close();
  });

  group('Journal-only mode', () {
    test('startSession saves minimal greeting in journal-only mode', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);

      final sessionId = await notifier.startSession();
      expect(sessionId, isNotEmpty);

      // Should have saved a minimal "Session started." ASSISTANT message.
      final messageDao = container.read(messageDaoProvider);
      final messages = await messageDao.getMessagesForSession(sessionId);
      expect(messages.length, 1);
      expect(messages.first.role, 'ASSISTANT');
      expect(messages.first.content, 'Session started.');
    });

    test('sendMessage skips follow-up in journal-only mode', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);

      await notifier.startSession();
      await notifier.sendMessage('I had a great day today');

      final sessionId = container.read(sessionNotifierProvider).activeSessionId;
      expect(sessionId, isNotNull);

      // Should have: greeting + user message, NO follow-up.
      final messageDao = container.read(messageDaoProvider);
      final messages = await messageDao.getMessagesForSession(sessionId!);
      expect(messages.length, 2); // greeting + user message
      expect(messages[0].role, 'ASSISTANT'); // greeting
      expect(messages[1].role, 'USER');

      // No isWaitingForAgent should have been set (no async agent call).
      expect(
        container.read(sessionNotifierProvider).isWaitingForAgent,
        isFalse,
      );
    });

    test(
      'sendMessage skips intent classification in journal-only mode',
      () async {
        final notifier = container.read(sessionNotifierProvider.notifier);

        await notifier.startSession();
        // A query that would normally trigger recall.
        await notifier.sendMessage('When did I last talk about work?');

        // Should NOT have a pending recall query.
        expect(
          container.read(sessionNotifierProvider).pendingRecallQuery,
          isNull,
        );
      },
    );

    test('endSession uses Layer A summary in journal-only mode', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);

      await notifier.startSession();
      await notifier.sendMessage('Had a productive day at work.');
      await notifier.endSession();

      final state = container.read(sessionNotifierProvider);
      expect(state.isClosingComplete, isTrue);

      // Verify the session was saved with a Layer A summary.
      final sessionId = state.activeSessionId;
      expect(sessionId, isNotNull);

      final sessionDao = container.read(sessionDaoProvider);
      final session = await sessionDao.getSessionById(sessionId!);
      expect(session, isNotNull);
      expect(session!.summary, isNotNull);
      expect(session.summary, contains('Had a productive day at work.'));

      // Metadata should be null (Layer A doesn't produce it).
      expect(session.moodTags, isNull);
      expect(session.people, isNull);
      expect(session.topicTags, isNull);
    });

    test(
      'multiple messages are saved without follow-ups in journal-only mode',
      () async {
        final notifier = container.read(sessionNotifierProvider.notifier);

        await notifier.startSession();
        await notifier.sendMessage('First thought for today.');
        await notifier.sendMessage('Second thought.');
        await notifier.sendMessage('Third thought.');

        final sessionId = container
            .read(sessionNotifierProvider)
            .activeSessionId;
        final messageDao = container.read(messageDaoProvider);
        final messages = await messageDao.getMessagesForSession(sessionId!);

        // greeting + 3 user messages, NO follow-ups.
        expect(messages.length, 4);
        expect(messages[0].role, 'ASSISTANT');
        expect(messages[1].role, 'USER');
        expect(messages[2].role, 'USER');
        expect(messages[3].role, 'USER');
      },
    );
  });

  group('AgentRepository journal-only mode methods', () {
    late AgentRepository agent;

    setUp(() {
      agent = AgentRepository();
      agent.setJournalOnlyMode(true);
    });

    test('getGreeting returns minimal message', () async {
      final response = await agent.getGreeting(
        now: DateTime(2026, 2, 23, 10, 0),
      );
      expect(response.content, 'Session started.');
      expect(response.layer, AgentLayer.ruleBasedLocal);
    });

    test('getFollowUp always returns null', () async {
      final response = await agent.getFollowUp(
        latestUserMessage: 'I feel stressed',
        conversationHistory: [],
        followUpCount: 0,
      );
      expect(response, isNull);
    });

    test('generateSummary uses Layer A', () async {
      final response = await agent.generateSummary(
        userMessages: ['Had a good day. Weather was nice.'],
      );
      expect(response.content, 'Had a good day.');
      expect(response.layer, AgentLayer.ruleBasedLocal);
      expect(response.metadata, isNull);
    });

    test('getResumeGreeting returns minimal message', () async {
      final response = await agent.getResumeGreeting();
      expect(response.content, 'Session resumed.');
      expect(response.layer, AgentLayer.ruleBasedLocal);
    });
  });
}
