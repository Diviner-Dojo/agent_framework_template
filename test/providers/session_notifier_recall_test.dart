import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:drift/native.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';
import 'package:agentic_journal/providers/database_provider.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/repositories/agent_repository.dart';
import 'package:agentic_journal/services/connectivity_service.dart';

void main() {
  late ProviderContainer container;
  late AppDatabase database;

  setUp(() {
    database = AppDatabase.forTesting(NativeDatabase.memory());
    container = ProviderContainer(
      overrides: [
        databaseProvider.overrideWithValue(database),
        // Layer A only: no Claude API, no sync.
        agentRepositoryProvider.overrideWithValue(AgentRepository()),
        connectivityServiceProvider.overrideWithValue(ConnectivityService()),
      ],
    );
  });

  tearDown(() async {
    container.dispose();
    await database.close();
  });

  /// Helper: create multiple completed sessions to pass the "few entries" check.
  Future<void> createPastSessions(
    SessionDao sessionDao, {
    int count = 6,
    List<String>? summaries,
  }) async {
    for (var i = 0; i < count; i++) {
      final id = 'past$i';
      await sessionDao.createSession(id, DateTime.utc(2026, 2, 1 + i), 'UTC');
      await sessionDao.endSession(
        id,
        DateTime.utc(2026, 2, 1 + i, 0, 30),
        summary: summaries != null && i < summaries.length
            ? summaries[i]
            : 'Regular day number $i',
      );
    }
  }

  group('SessionNotifier recall — intent classification routing', () {
    test('high-confidence query routes to recall (not normal follow-up)', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      final sessionId = await notifier.startSession();

      // metaQuestion "how many times" (0.45) + questionPast "have I mentioned"
      // (0.4) = 0.85 → high confidence auto-recall.
      await notifier.sendMessage(
        'How many times have I mentioned feeling stressed?',
      );

      // Should NOT set pendingRecallQuery (high confidence → auto-routed).
      final state = container.read(sessionNotifierProvider);
      expect(state.pendingRecallQuery, isNull);
      // followUpCount should NOT increment (recall, not follow-up).
      expect(state.followUpCount, 0);

      // A recall response message should have been saved in the DB.
      final messageDao = container.read(messageDaoProvider);
      final messages = await messageDao.getMessagesForSession(sessionId);
      // 1 greeting + 1 user message + 1 recall response = 3
      expect(messages.length, 3);
      expect(messages[2].role, 'ASSISTANT');
      // The message should be a recall-style response (not a follow-up question).
      // Since there's only the active session, it triggers the "no entries yet"
      // or "only have N entries" path.
      expect(
        messages[2].content,
        anyOf(
          contains("don't have any"),
          contains('only have'),
          contains("couldn't find"),
        ),
      );
    });

    test('ambiguous query sets pendingRecallQuery', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      await notifier.startSession();

      // questionPast "What did I" (0.4) + temporal "last week" (0.3) = 0.7
      // → ambiguous (between 0.5 and 0.8)
      await notifier.sendMessage('What did I say about work last week?');

      final state = container.read(sessionNotifierProvider);
      expect(state.pendingRecallQuery, isNotNull);
      expect(state.pendingRecallQuery, contains('work'));
      expect(state.pendingSearchTerms, isNotEmpty);
      // Follow-up should NOT be incremented (pending, not routed yet).
      expect(state.followUpCount, 0);
    });

    test('regular journal message does not trigger recall', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      final sessionId = await notifier.startSession();

      // Simple journaling message — no recall signals.
      await notifier.sendMessage('I had a productive day at work today');

      final state = container.read(sessionNotifierProvider);
      expect(state.pendingRecallQuery, isNull);

      // Should have normal follow-up (greeting + user + follow-up = 3).
      final messageDao = container.read(messageDaoProvider);
      final messages = await messageDao.getMessagesForSession(sessionId);
      expect(messages.length, 3);
      expect(state.followUpCount, 1);
    });
  });

  group('SessionNotifier recall — confirmRecallQuery', () {
    test('confirm clears pending and triggers recall', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      final sessionId = await notifier.startSession();

      // Trigger ambiguous intent.
      // questionPast "What did I" (0.4) + temporal "last week" (0.3) = 0.7
      await notifier.sendMessage('What did I say about exercise last week?');

      var state = container.read(sessionNotifierProvider);
      expect(state.pendingRecallQuery, isNotNull);

      // Confirm the recall.
      await notifier.confirmRecallQuery();

      state = container.read(sessionNotifierProvider);
      expect(state.pendingRecallQuery, isNull);
      expect(state.pendingSearchTerms, isEmpty);

      // Should have recall response message saved (no results since no data).
      final messageDao = container.read(messageDaoProvider);
      final messages = await messageDao.getMessagesForSession(sessionId);
      // greeting + user msg + recall response = 3
      expect(messages.length, 3);
      expect(messages[2].role, 'ASSISTANT');
    });

    test('confirm with no pending query is no-op', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      await notifier.startSession();

      // No pending query — should be a safe no-op.
      await notifier.confirmRecallQuery();

      final state = container.read(sessionNotifierProvider);
      expect(state.pendingRecallQuery, isNull);
    });
  });

  group('SessionNotifier recall — dismissRecallQuery', () {
    test('dismiss clears pending and routes to normal follow-up', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      final sessionId = await notifier.startSession();

      // Trigger ambiguous intent.
      await notifier.sendMessage('What did I say about work last week?');

      var state = container.read(sessionNotifierProvider);
      expect(state.pendingRecallQuery, isNotNull);

      // Dismiss — should route through normal journaling.
      await notifier.dismissRecallQuery();

      state = container.read(sessionNotifierProvider);
      expect(state.pendingRecallQuery, isNull);
      expect(state.pendingSearchTerms, isEmpty);

      // Should have normal follow-up message (from AgentRepository Layer A).
      final messageDao = container.read(messageDaoProvider);
      final messages = await messageDao.getMessagesForSession(sessionId);
      // greeting + user msg + follow-up = 3
      expect(messages.length, 3);
      expect(messages[2].role, 'ASSISTANT');
      expect(state.followUpCount, 1);
    });

    test('dismiss with no pending query is no-op', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      await notifier.startSession();

      await notifier.dismissRecallQuery();

      final state = container.read(sessionNotifierProvider);
      expect(state.pendingRecallQuery, isNull);
    });
  });

  group('SessionNotifier recall — no results handling', () {
    test('no completed sessions returns few-entries message', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      final sessionId = await notifier.startSession();

      // metaQuestion + questionPast = 0.85 → high confidence
      await notifier.sendMessage(
        'How often have I felt happy about traveling?',
      );

      final messageDao = container.read(messageDaoProvider);
      final messages = await messageDao.getMessagesForSession(sessionId);
      expect(messages.length, 3);
      // The active session counts as 1, so totalCount=1 < 5 → "only have"
      expect(messages[2].content, contains('only have 1 entry'));
    });

    test('few entries with no match returns count message', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      final sessionId = await notifier.startSession();

      final sessionDao = container.read(sessionDaoProvider);
      await createPastSessions(sessionDao, count: 3);

      // metaQuestion + questionPast = 0.85 → high confidence
      await notifier.sendMessage(
        'How often have I felt ecstatic about skydiving?',
      );

      final messageDao = container.read(messageDaoProvider);
      final messages = await messageDao.getMessagesForSession(sessionId);
      expect(messages.length, 3);
      // totalCount=4 (3 past + 1 active), < 5 → "only have N entries" message.
      expect(messages[2].content, contains('entries'));
    });

    test(
      'many entries with no match returns "couldn\'t find" message',
      () async {
        final notifier = container.read(sessionNotifierProvider.notifier);
        final sessionId = await notifier.startSession();

        final sessionDao = container.read(sessionDaoProvider);
        await createPastSessions(sessionDao, count: 6);

        // metaQuestion + questionPast = 0.85 → high confidence
        await notifier.sendMessage(
          'How often have I mentioned quantum physics?',
        );

        final messageDao = container.read(messageDaoProvider);
        final messages = await messageDao.getMessagesForSession(sessionId);
        expect(messages.length, 3);
        expect(messages[2].content, contains("couldn't find"));
      },
    );
  });

  group('SessionNotifier recall — offline fallback with results', () {
    test('matching entries return offline fallback with session list', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      final sessionId = await notifier.startSession();

      // Create sessions where summary contains the exact extracted search
      // phrase. For "How often did I mention work?":
      // Extracted: ["often", "mention", "work"] → joined: "often mention work"
      final sessionDao = container.read(sessionDaoProvider);
      await createPastSessions(
        sessionDao,
        count: 6,
        summaries: [
          'I often mention work at dinner',
          'Regular day number 1',
          'Regular day number 2',
          'Regular day number 3',
          'Regular day number 4',
          'Regular day number 5',
        ],
      );

      // metaQuestion "how often" (0.45) + questionPast "did I" (0.4) = 0.85
      await notifier.sendMessage('How often did I mention work?');

      final messageDao = container.read(messageDaoProvider);
      final messages = await messageDao.getMessagesForSession(sessionId);
      expect(messages.length, 3);
      // Offline fallback lists matching sessions.
      expect(messages[2].content, contains('entries about that'));
      // Should have recall metadata in entitiesJson.
      expect(messages[2].entitiesJson, isNotNull);
      expect(messages[2].entitiesJson, contains('recall'));
      expect(messages[2].entitiesJson, contains('is_offline'));
    });
  });

  group('SessionState copyWith — recall fields', () {
    test('pendingRecallQuery can be set and cleared', () {
      const initial = SessionState();
      expect(initial.pendingRecallQuery, isNull);
      expect(initial.pendingSearchTerms, isEmpty);

      final withPending = initial.copyWith(
        pendingRecallQuery: 'test query',
        pendingSearchTerms: ['test'],
      );
      expect(withPending.pendingRecallQuery, 'test query');
      expect(withPending.pendingSearchTerms, ['test']);

      // Clear pending via explicit null.
      final cleared = withPending.copyWith(
        pendingRecallQuery: null,
        pendingSearchTerms: const [],
      );
      expect(cleared.pendingRecallQuery, isNull);
      expect(cleared.pendingSearchTerms, isEmpty);
    });

    test('omitting pendingRecallQuery preserves value (sentinel)', () {
      final withQuery = const SessionState().copyWith(
        pendingRecallQuery: 'keep me',
      );
      // copyWith without pendingRecallQuery should keep the existing value.
      final updated = withQuery.copyWith(followUpCount: 5);
      expect(updated.pendingRecallQuery, 'keep me');
      expect(updated.followUpCount, 5);
    });
  });
}
