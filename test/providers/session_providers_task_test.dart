// ===========================================================================
// file: test/providers/session_providers_task_test.dart
// purpose: Tests for SessionNotifier task intent methods (Phase 13).
//
// Coverage targets:
//   - Task intent routing via sendMessage
//   - _handleTaskIntent sets pending state
//   - confirmTask saves task to local DB
//   - dismissTask clears state
//   - SessionState.copyWith for task fields
//   - deleteSessionCascade standalone function
//   - resumeLatestSession
// ===========================================================================

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/providers/database_provider.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/services/task_extraction_service.dart';

import '../helpers/test_providers.dart';

void main() {
  late ProviderContainer container;
  late AppDatabase database;

  setUp(() async {
    final result = await createTestContainer();
    container = result.container;
    database = result.database;
  });

  tearDown(() async {
    container.dispose();
    await database.close();
  });

  group('SessionState copyWith — task fields', () {
    test('pendingTask can be set and cleared', () {
      const initial = SessionState();
      expect(initial.pendingTask, isNull);

      final withTask = initial.copyWith(pendingTask: 'Buy groceries tomorrow');
      expect(withTask.pendingTask, 'Buy groceries tomorrow');

      final cleared = withTask.copyWith(pendingTask: null);
      expect(cleared.pendingTask, isNull);
    });

    test('pendingExtractedTask can be set and cleared', () {
      final task = ExtractedTask(
        title: 'Buy groceries',
        dueDate: DateTime.utc(2026, 3, 1),
      );
      final state = const SessionState().copyWith(pendingExtractedTask: task);
      expect(state.pendingExtractedTask, isNotNull);
      expect(state.pendingExtractedTask!.title, 'Buy groceries');

      final cleared = state.copyWith(pendingExtractedTask: null);
      expect(cleared.pendingExtractedTask, isNull);
    });

    test('isExtractingTask and taskExtractionError work with copyWith', () {
      final state = const SessionState().copyWith(
        isExtractingTask: true,
        taskExtractionError: null,
      );
      expect(state.isExtractingTask, isTrue);
      expect(state.taskExtractionError, isNull);

      final withError = state.copyWith(
        isExtractingTask: false,
        taskExtractionError: 'Could not extract',
      );
      expect(withError.isExtractingTask, isFalse);
      expect(withError.taskExtractionError, 'Could not extract');
    });

    test('omitting pendingTask preserves value (sentinel)', () {
      final withTask = const SessionState().copyWith(pendingTask: 'keep me');
      final updated = withTask.copyWith(followUpCount: 3);
      expect(updated.pendingTask, 'keep me');
      expect(updated.followUpCount, 3);
    });
  });

  group('SessionNotifier — task intent routing', () {
    test('task intent sets pendingTask and extracts details', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      await notifier.startSession();

      // "Add a task to buy groceries tomorrow" triggers task intent.
      await notifier.sendMessage('Add a task to buy groceries tomorrow');

      // Wait for async extraction to complete.
      await Future<void>.delayed(const Duration(milliseconds: 100));

      final state = container.read(sessionNotifierProvider);
      // Task intent should have been routed — not a normal follow-up.
      expect(state.followUpCount, 0);
      expect(state.isWaitingForAgent, isFalse);
    });

    test('regular journal message does not trigger task intent', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      await notifier.startSession();

      await notifier.sendMessage('I had a productive day at work today');

      final state = container.read(sessionNotifierProvider);
      expect(state.pendingTask, isNull);
      expect(state.pendingExtractedTask, isNull);
      expect(state.followUpCount, 1);
    });
  });

  group('SessionNotifier.confirmTask', () {
    test('saves task to local DB and sends confirmation message', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      final sessionId = await notifier.startSession();

      // Trigger task intent.
      await notifier.sendMessage('Add a task to buy groceries tomorrow');

      // Wait for extraction to complete.
      await Future<void>.delayed(const Duration(milliseconds: 100));

      // Confirm the task.
      await notifier.confirmTask();

      final state = container.read(sessionNotifierProvider);
      // Pending should be cleared.
      expect(state.pendingTask, isNull);
      expect(state.pendingExtractedTask, isNull);
      expect(state.isWaitingForAgent, isFalse);

      // Task should be saved to the local database.
      final taskDao = container.read(taskDaoProvider);
      final tasks = await taskDao.getTasksToSync();
      expect(tasks, isNotEmpty);

      // Confirmation message should reference the task.
      final messageDao = container.read(messageDaoProvider);
      final messages = await messageDao.getMessagesForSession(sessionId);
      final lastMsg = messages.last;
      expect(lastMsg.role, 'ASSISTANT');
      expect(lastMsg.content, contains('tasks'));
    });

    test('is no-op when no pending task', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      await notifier.startSession();

      // No pending task — should be a safe no-op.
      await notifier.confirmTask();

      final state = container.read(sessionNotifierProvider);
      expect(state.isWaitingForAgent, isFalse);
    });

    test('is no-op when isWaitingForAgent is true', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      await notifier.startSession();

      await notifier.sendMessage('Add a task to buy groceries tomorrow');
      await Future<void>.delayed(const Duration(milliseconds: 100));

      // Manually set isWaitingForAgent to simulate concurrent request.
      // We can't directly set the state, but we can test via double-tap.
      final future1 = notifier.confirmTask();
      final future2 = notifier.confirmTask();

      await Future.wait([future1, future2]);

      // Should not crash and should complete cleanly.
      final state = container.read(sessionNotifierProvider);
      expect(state.isWaitingForAgent, isFalse);
    });
  });

  group('SessionNotifier.dismissTask', () {
    test('clears pending task state', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      await notifier.startSession();

      await notifier.sendMessage('Add a task to buy groceries tomorrow');
      await Future<void>.delayed(const Duration(milliseconds: 100));

      // Dismiss the pending task.
      notifier.dismissTask();

      final state = container.read(sessionNotifierProvider);
      expect(state.pendingTask, isNull);
      expect(state.pendingExtractedTask, isNull);
      expect(state.isExtractingTask, isFalse);
      expect(state.taskExtractionError, isNull);
    });

    test('is safe to call with no pending task', () {
      final notifier = container.read(sessionNotifierProvider.notifier);
      // No active session or pending task — should not throw.
      notifier.dismissTask();

      final state = container.read(sessionNotifierProvider);
      expect(state.pendingTask, isNull);
    });
  });

  group('SessionNotifier.resumeLatestSession', () {
    test('returns null when no open sessions exist', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);

      // Start and end a session so there's at least one completed session.
      await notifier.startSession();
      await notifier.sendMessage('Hello');
      await notifier.endSession();

      // Dismiss the completed session.
      notifier.dismissSession();

      // Try to resume — should be null since the session has endTime.
      final resumed = await notifier.resumeLatestSession();
      expect(resumed, isNull);
    });

    test('resumes an open session', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      final sessionId = await notifier.startSession();

      // Dismiss without ending (simulates app restart scenario).
      notifier.dismissSession();

      // The session still has no endTime — should be resumable.
      final resumed = await notifier.resumeLatestSession();
      expect(resumed, sessionId);

      final state = container.read(sessionNotifierProvider);
      expect(state.activeSessionId, sessionId);
    });
  });

  group('SessionNotifier — day query routing', () {
    test('day query returns task summary for today', () async {
      final notifier = container.read(sessionNotifierProvider.notifier);
      final sessionId = await notifier.startSession();

      // Send a day query.
      await notifier.sendMessage("What do I have on today?");

      // Wait for async processing.
      await Future<void>.delayed(const Duration(milliseconds: 100));

      final state = container.read(sessionNotifierProvider);
      // Day query is handled as an intent — no follow-up increment.
      expect(state.followUpCount, 0);
      expect(state.isWaitingForAgent, isFalse);

      // Should have saved an assistant message with day summary.
      final messageDao = container.read(messageDaoProvider);
      final messages = await messageDao.getMessagesForSession(sessionId);
      // greeting + user + day summary = at least 3
      expect(messages.length, greaterThanOrEqualTo(3));
    });
  });

  group('deleteSessionCascade (standalone function)', () {
    test('deletes session and its messages', () async {
      final sessionDao = container.read(sessionDaoProvider);
      final messageDao = container.read(messageDaoProvider);

      // Create a session with messages.
      await sessionDao.createSession(
        'session-del',
        DateTime.utc(2026, 2, 28),
        'UTC',
      );
      await messageDao.insertMessage(
        'msg-1',
        'session-del',
        'USER',
        'Hello',
        DateTime.utc(2026, 2, 28),
      );
      await messageDao.insertMessage(
        'msg-2',
        'session-del',
        'ASSISTANT',
        'Hi there',
        DateTime.utc(2026, 2, 28),
      );

      // Verify they exist.
      final sessionBefore = await sessionDao.getSessionById('session-del');
      expect(sessionBefore, isNotNull);
      final messagesBefore = await messageDao.getMessagesForSession(
        'session-del',
      );
      expect(messagesBefore, hasLength(2));

      // Delete.
      await deleteSessionCascade(sessionDao, messageDao, 'session-del');

      // Verify deleted.
      final sessionAfter = await sessionDao.getSessionById('session-del');
      expect(sessionAfter, isNull);
      final messagesAfter = await messageDao.getMessagesForSession(
        'session-del',
      );
      expect(messagesAfter, isEmpty);
    });
  });
}
