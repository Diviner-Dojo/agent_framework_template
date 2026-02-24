// ===========================================================================
// file: test/providers/session_resume_test.dart
// purpose: Tests for session resume functionality (ADR-0014).
//
// Verifies:
//   - SessionDao.resumeSession sets DB flags correctly
//   - SessionNotifier.resumeSession loads messages, generates greeting
//   - Guard: cannot resume when another session is active
//   - Guard: resuming non-existent session returns null
// ===========================================================================

import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:drift/native.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';
import 'package:agentic_journal/providers/database_provider.dart';
import 'package:agentic_journal/providers/onboarding_providers.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/repositories/agent_repository.dart';

void main() {
  group('SessionDao.resumeSession', () {
    late AppDatabase database;
    late SessionDao sessionDao;

    setUp(() {
      database = AppDatabase.forTesting(NativeDatabase.memory());
      sessionDao = SessionDao(database);
    });

    tearDown(() async {
      await database.close();
    });

    test('clears endTime, sets isResumed and increments resumeCount', () async {
      final now = DateTime.now().toUtc();
      await sessionDao.createSession('resume-1', now, 'UTC');
      await sessionDao.endSession(
        'resume-1',
        now.add(const Duration(minutes: 5)),
        summary: 'Test summary',
      );

      // Verify session is ended.
      var session = await sessionDao.getSessionById('resume-1');
      expect(session!.endTime, isNotNull);
      expect(session.isResumed, false);
      expect(session.resumeCount, 0);

      // Resume.
      final updated = await sessionDao.resumeSession('resume-1');
      expect(updated, 1);

      // Verify DB flags.
      session = await sessionDao.getSessionById('resume-1');
      expect(session!.endTime, isNull);
      expect(session.isResumed, true);
      expect(session.resumeCount, 1);
      expect(session.syncStatus, 'PENDING');
    });

    test('increments resumeCount on each resume', () async {
      final now = DateTime.now().toUtc();
      await sessionDao.createSession('resume-2', now, 'UTC');

      // First resume cycle.
      await sessionDao.endSession(
        'resume-2',
        now.add(const Duration(minutes: 5)),
      );
      await sessionDao.resumeSession('resume-2');
      var session = await sessionDao.getSessionById('resume-2');
      expect(session!.resumeCount, 1);

      // Second resume cycle.
      await sessionDao.endSession(
        'resume-2',
        now.add(const Duration(minutes: 10)),
      );
      await sessionDao.resumeSession('resume-2');
      session = await sessionDao.getSessionById('resume-2');
      expect(session!.resumeCount, 2);
    });

    test('returns 0 for non-existent session', () async {
      final result = await sessionDao.resumeSession('does-not-exist');
      expect(result, 0);
    });

    test('preserves original startTime', () async {
      final originalStart = DateTime.utc(2026, 1, 15, 10, 30);
      await sessionDao.createSession('resume-3', originalStart, 'UTC');
      await sessionDao.endSession(
        'resume-3',
        originalStart.add(const Duration(minutes: 5)),
      );

      await sessionDao.resumeSession('resume-3');

      final session = await sessionDao.getSessionById('resume-3');
      expect(session!.startTime, originalStart);
    });

    test('reverts syncStatus to PENDING', () async {
      final now = DateTime.now().toUtc();
      await sessionDao.createSession('resume-4', now, 'UTC');
      await sessionDao.endSession(
        'resume-4',
        now.add(const Duration(minutes: 5)),
      );

      // Simulate a synced session.
      await sessionDao.updateSyncStatus('resume-4', 'SYNCED', now);
      var session = await sessionDao.getSessionById('resume-4');
      expect(session!.syncStatus, 'SYNCED');

      // Resume should revert to PENDING.
      await sessionDao.resumeSession('resume-4');
      session = await sessionDao.getSessionById('resume-4');
      expect(session!.syncStatus, 'PENDING');
    });
  });

  group('SessionNotifier.resumeSession', () {
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

    test('resumes session and loads existing messages', () async {
      // Create and end a session with messages.
      final notifier = container.read(sessionNotifierProvider.notifier);
      final sessionId = await notifier.startSession();

      await notifier.sendMessage('I had a great day');
      await notifier.endSession();
      notifier.dismissSession();

      // Verify session is ended.
      final sessionDao = container.read(sessionDaoProvider);
      var session = await sessionDao.getSessionById(sessionId);
      expect(session!.endTime, isNotNull);

      // Resume.
      final result = await notifier.resumeSession(sessionId);
      expect(result, sessionId);

      // Verify notifier state.
      final state = container.read(sessionNotifierProvider);
      expect(state.activeSessionId, sessionId);
      expect(state.isWaitingForAgent, false);
      expect(state.conversationMessages, isNotEmpty);

      // The resume greeting should be in the messages.
      final messageDao = container.read(messageDaoProvider);
      final messages = await messageDao.getMessagesForSession(sessionId);
      final lastMsg = messages.last;
      expect(lastMsg.role, 'ASSISTANT');
      expect(lastMsg.content, contains('Welcome back'));
    });

    test('returns null when another session is active', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);

      // Start a session — it's now active.
      await notifier.startSession();

      // Create a second ended session to try to resume.
      final sessionDao = container.read(sessionDaoProvider);
      final now = DateTime.now().toUtc();
      await sessionDao.createSession('other-session', now, 'UTC');
      await sessionDao.endSession(
        'other-session',
        now.add(const Duration(minutes: 5)),
      );

      // Try to resume — should be blocked.
      final result = await notifier.resumeSession('other-session');
      expect(result, isNull);
    });

    test('returns null for non-existent session', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      final result = await notifier.resumeSession('does-not-exist');
      expect(result, isNull);
    });

    test('sets activeSessionIdProvider on resume', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      final sessionId = await notifier.startSession();
      await notifier.sendMessage('Test message');
      await notifier.endSession();
      notifier.dismissSession();

      expect(container.read(activeSessionIdProvider), isNull);

      await notifier.resumeSession(sessionId);
      expect(container.read(activeSessionIdProvider), sessionId);
    });

    test('restores followUpCount from existing messages', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      final sessionId = await notifier.startSession();

      // Send two user messages (creates 2 follow-up assistant messages).
      await notifier.sendMessage('I feel happy today');
      await notifier.sendMessage('Work was productive');
      await notifier.endSession();
      notifier.dismissSession();

      // After endSession, the DB has: greeting(A) + msg1(U) + followUp1(A)
      // + msg2(U) + followUp2(A) + closing(A) = 2 USER messages.
      // On resume, followUpCount = USER message count = 2.
      await notifier.resumeSession(sessionId);
      final state = container.read(sessionNotifierProvider);
      expect(state.followUpCount, 2);
    });
  });
}
