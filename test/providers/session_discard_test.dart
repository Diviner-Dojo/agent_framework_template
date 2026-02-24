import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:drift/native.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:agentic_journal/database/app_database.dart';
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
    container = ProviderContainer(
      overrides: [
        databaseProvider.overrideWithValue(database),
        agentRepositoryProvider.overrideWithValue(AgentRepository()),
        sharedPreferencesProvider.overrideWithValue(prefs),
      ],
    );
  });

  tearDown(() async {
    container.dispose();
    await database.close();
  });

  group('SessionNotifier.discardSession', () {
    test('clears state and deletes session from DB', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      final sessionId = await notifier.startSession();

      // Verify session exists.
      final sessionDao = container.read(sessionDaoProvider);
      expect(await sessionDao.getSessionById(sessionId), isNotNull);

      // Discard.
      await notifier.discardSession();

      // State should be cleared.
      final state = container.read(sessionNotifierProvider);
      expect(state.activeSessionId, isNull);
      expect(state.followUpCount, 0);

      // activeSessionIdProvider should be null.
      expect(container.read(activeSessionIdProvider), isNull);

      // Session should be gone from DB.
      expect(await sessionDao.getSessionById(sessionId), isNull);
    });

    test('deletes messages along with session', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      final sessionId = await notifier.startSession();

      // Send a user message to create more messages.
      await notifier.sendMessage('I feel happy today');

      final messageDao = container.read(messageDaoProvider);
      final messagesBefore = await messageDao.getMessagesForSession(sessionId);
      expect(messagesBefore.length, greaterThan(1));

      // Discard.
      await notifier.discardSession();

      // Messages should be gone.
      final messagesAfter = await messageDao.getMessagesForSession(sessionId);
      expect(messagesAfter, isEmpty);
    });

    test('no-op when no active session', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);

      // Should not throw.
      await notifier.discardSession();

      final state = container.read(sessionNotifierProvider);
      expect(state.activeSessionId, isNull);
    });
  });

  group('wasAutoDiscardedProvider', () {
    test('defaults to false', () {
      expect(container.read(wasAutoDiscardedProvider), false);
    });

    test('can be set and read', () {
      container.read(wasAutoDiscardedProvider.notifier).state = true;
      expect(container.read(wasAutoDiscardedProvider), true);
    });
  });
}
