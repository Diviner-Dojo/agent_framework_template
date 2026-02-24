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

  group('Empty session guard', () {
    test('end empty session closes quietly and preserves in DB', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      final sessionId = await notifier.startSession();

      // Verify session was created (greeting exists, no USER messages).
      final sessionDao = container.read(sessionDaoProvider);
      expect(await sessionDao.getSessionById(sessionId), isNotNull);

      // End the empty session — should close quietly (not delete).
      await notifier.endSession();

      // wasAutoDiscardedProvider should be true (signals UI to show SnackBar).
      expect(container.read(wasAutoDiscardedProvider), true);

      // State should be cleared.
      final state = container.read(sessionNotifierProvider);
      expect(state.activeSessionId, isNull);
      expect(state.isClosingComplete, false); // Never got to closing.

      // Session should be preserved in DB with endTime set (not deleted).
      final session = await sessionDao.getSessionById(sessionId);
      expect(session, isNotNull);
      expect(session!.endTime, isNotNull);
      expect(session.summary, isNull); // No summary for empty session.
    });

    test('end session with messages follows normal flow', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      final sessionId = await notifier.startSession();

      // Send a user message so the session is not empty.
      await notifier.sendMessage('Had a great day!');

      // End the session — should NOT auto-discard.
      await notifier.endSession();

      // wasAutoDiscardedProvider should stay false.
      expect(container.read(wasAutoDiscardedProvider), false);

      // Session should still exist in DB with end time and summary.
      final sessionDao = container.read(sessionDaoProvider);
      final session = await sessionDao.getSessionById(sessionId);
      expect(session, isNotNull);
      expect(session!.endTime, isNotNull);
      expect(session.summary, isNotNull);

      // State should show closing complete (normal flow).
      final state = container.read(sessionNotifierProvider);
      expect(state.isClosingComplete, true);
    });
  });
}
