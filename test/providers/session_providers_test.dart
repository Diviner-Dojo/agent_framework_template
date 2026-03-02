// ===========================================================================
// file: test/providers/session_providers_test.dart
// purpose: Regression tests for bug-fix sprint (Voice UX + Task + TTS).
//
// Covers:
//   - Fix 2: Journal-only mode runs task intents, skips AI follow-up only
//   - Fix 4: endSession() with no user messages deletes session from DB
// ===========================================================================

@Tags(['regression'])
library;

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
  // =========================================================================
  // Fix 2 regression: task intent fires in journal-only mode
  // =========================================================================

  group('Fix 2 — journal-only mode: task intent handled, no AI follow-up', () {
    late ProviderContainer container;
    late AppDatabase database;

    setUp(() async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      database = AppDatabase.forTesting(NativeDatabase.memory());

      final journalOnlyAgent = AgentRepository();
      journalOnlyAgent.setJournalOnlyMode(true);

      container = ProviderContainer(
        overrides: [
          databaseProvider.overrideWithValue(database),
          agentRepositoryProvider.overrideWithValue(journalOnlyAgent),
          sharedPreferencesProvider.overrideWithValue(prefs),
          deviceTimezoneProvider.overrideWith(
            (ref) async => 'America/New_York',
          ),
        ],
      );
    });

    tearDown(() async {
      container.dispose();
      await database.close();
    });

    // regression: in journal-only mode, task intents were silently dropped
    // because the journalOnlyMode guard fired before intent routing.
    // Fix 2 moves the guard to after _routeByIntent() so task handling runs.
    test('task-intent message in journal-only mode sets pendingTask and '
        'does NOT generate AI follow-up', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      await notifier.startSession();

      await notifier.sendMessage('Add a task to call Mom tomorrow');

      final state = container.read(sessionNotifierProvider);

      // Task handling ran — pendingTask is non-null.
      expect(
        state.pendingTask,
        isNotNull,
        reason: 'task intent must be handled even in journal-only mode',
      );

      // No AI conversational follow-up was triggered.
      expect(
        state.isWaitingForAgent,
        isFalse,
        reason: 'journal-only mode must not trigger AI follow-up',
      );
    });
  });

  // =========================================================================
  // Bug 3 regression: "goodbye" skipped in journal-only mode
  // =========================================================================

  group('Bug 3 — goodbye in journal-only mode ends session', () {
    late ProviderContainer container;
    late AppDatabase database;

    setUp(() async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      database = AppDatabase.forTesting(NativeDatabase.memory());

      final journalOnlyAgent = AgentRepository();
      journalOnlyAgent.setJournalOnlyMode(true);

      container = ProviderContainer(
        overrides: [
          databaseProvider.overrideWithValue(database),
          agentRepositoryProvider.overrideWithValue(journalOnlyAgent),
          sharedPreferencesProvider.overrideWithValue(prefs),
          deviceTimezoneProvider.overrideWith(
            (ref) async => 'America/New_York',
          ),
        ],
      );
    });

    tearDown(() async {
      container.dispose();
      await database.close();
    });

    // regression: shouldEndSession() was called AFTER the journalOnlyMode
    // guard, so "goodbye" was silently ignored in journal-only mode.
    // Fix B1 moves shouldEndSession() above the guard so it runs first.
    test('goodbye in journal-only mode ends the session', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      await notifier.startSession();

      // Send a real message first so the session is not empty.
      await notifier.sendMessage('Had a good morning run');

      expect(
        container.read(sessionNotifierProvider).activeSessionId,
        isNotNull,
        reason: 'session must be active before goodbye',
      );

      // Saying goodbye should end the session even in journal-only mode.
      await notifier.sendMessage('goodbye');

      final state = container.read(sessionNotifierProvider);

      // endSession() runs asynchronously and leaves activeSessionId set so
      // the UI can show the closing summary. The correct signal that the
      // end-session flow ran is isClosingComplete == true.
      expect(
        state.isClosingComplete,
        isTrue,
        reason: 'goodbye must trigger endSession() in journal-only mode',
      );
    });
  });

  // =========================================================================
  // Fix 4 regression: endSession() with no user messages deletes session
  // =========================================================================

  group('Fix 4 — endSession with no user messages deletes session from DB', () {
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
          deviceTimezoneProvider.overrideWith(
            (ref) async => 'America/New_York',
          ),
        ],
      );
    });

    tearDown(() async {
      container.dispose();
      await database.close();
    });

    // regression: endSession() with no USER messages used to call
    // _sessionDao.endSession() which preserved the row (status=ended,
    // no summary). Empty sessions appeared in the journal list.
    // Fix 4 replaces it with discardSession() so the row is deleted.
    test(
      'endSession with no user messages deletes session row from DB',
      () async {
        final notifier = container.read(sessionNotifierProvider.notifier);
        final sessionId = await notifier.startSession();

        final sessionDao = container.read(sessionDaoProvider);
        expect(
          await sessionDao.getSessionById(sessionId),
          isNotNull,
          reason: 'session should exist after startSession()',
        );

        // End without any user messages.
        await notifier.endSession();

        // Row must be gone.
        expect(
          await sessionDao.getSessionById(sessionId),
          isNull,
          reason: 'empty session must be deleted, not preserved in DB',
        );

        // State is cleared.
        expect(container.read(sessionNotifierProvider).activeSessionId, isNull);

        // UI notification signal is set.
        expect(container.read(wasAutoDiscardedProvider), isTrue);
      },
    );
  });
}
