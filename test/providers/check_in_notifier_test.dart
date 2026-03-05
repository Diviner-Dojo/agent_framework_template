// ===========================================================================
// file: test/providers/check_in_notifier_test.dart
// purpose: Unit tests for CheckInNotifier — startCheckIn, cancelCheckIn,
//   recordAnswer, flagParseError, and auto-save on last answer.
//
// Uses ProviderContainer with databaseProvider overridden by an in-memory DB
// so all real DAOs and services wire up without any mocking overhead.
// Voice methods (speakCurrentQuestion, handleVoiceAnswer) are tested separately
// via integration tests because they require TTS + orchestrator.
//
// See: SPEC-20260302-ADHD Phase 1 Task 4, ADR-0032.
// ===========================================================================

import 'package:drift/native.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';
import 'package:agentic_journal/providers/database_provider.dart';
import 'package:agentic_journal/providers/questionnaire_providers.dart';

void main() {
  late AppDatabase db;
  late SessionDao sessionDao;

  setUp(() {
    db = AppDatabase.forTesting(NativeDatabase.memory());
    sessionDao = SessionDao(db);
  });

  tearDown(() async {
    await db.close();
  });

  /// Build a ProviderContainer with the in-memory DB injected.
  ProviderContainer makeContainer() {
    final container = ProviderContainer(
      overrides: [databaseProvider.overrideWithValue(db)],
    );
    addTearDown(container.dispose);
    return container;
  }

  // ---------------------------------------------------------------------------
  // startCheckIn
  // ---------------------------------------------------------------------------

  group('CheckInNotifier.startCheckIn', () {
    test('sets isActive and loads 6 default items', () async {
      final container = makeContainer();
      await container.read(checkInProvider.notifier).startCheckIn();

      final state = container.read(checkInProvider);
      expect(state.isActive, isTrue);
      expect(state.items, hasLength(6));
    });

    test('resets currentStepIndex to 0 and fills answers with null', () async {
      final container = makeContainer();
      await container.read(checkInProvider.notifier).startCheckIn();

      final state = container.read(checkInProvider);
      expect(state.currentStepIndex, 0);
      expect(state.answers, hasLength(6));
      expect(state.answers, everyElement(isNull));
    });

    test('loads template with 1-10 scale', () async {
      final container = makeContainer();
      await container.read(checkInProvider.notifier).startCheckIn();

      final state = container.read(checkInProvider);
      expect(state.template, isNotNull);
      expect(state.template!.scaleMin, 1);
      expect(state.template!.scaleMax, 10);
    });

    test('is idempotent — second call does not duplicate items', () async {
      final container = makeContainer();
      final notifier = container.read(checkInProvider.notifier);
      await notifier.startCheckIn();
      await notifier.startCheckIn();

      final state = container.read(checkInProvider);
      expect(state.items, hasLength(6));
    });

    test('currentItem is the first question after start', () async {
      final container = makeContainer();
      await container.read(checkInProvider.notifier).startCheckIn();

      final state = container.read(checkInProvider);
      expect(state.currentItem, isNotNull);
      expect(state.currentItem!.questionText, isNotEmpty);
    });
  });

  // ---------------------------------------------------------------------------
  // cancelCheckIn
  // ---------------------------------------------------------------------------

  group('CheckInNotifier.cancelCheckIn', () {
    test('resets to initial inactive state', () async {
      final container = makeContainer();
      final notifier = container.read(checkInProvider.notifier);
      await notifier.startCheckIn();
      notifier.cancelCheckIn();

      final state = container.read(checkInProvider);
      expect(state.isActive, isFalse);
      expect(state.items, isEmpty);
      expect(state.answers, isEmpty);
      expect(state.currentStepIndex, 0);
    });

    test('cancelCheckIn on inactive state is a no-op', () {
      final container = makeContainer();
      container.read(checkInProvider.notifier).cancelCheckIn();

      final state = container.read(checkInProvider);
      expect(state.isActive, isFalse);
    });
  });

  // ---------------------------------------------------------------------------
  // recordAnswer
  // ---------------------------------------------------------------------------

  group('CheckInNotifier.recordAnswer', () {
    test('records value and advances step', () async {
      final container = makeContainer();
      await sessionDao.createSession('s1', DateTime.utc(2026, 3, 3), 'UTC');
      await container.read(checkInProvider.notifier).startCheckIn();

      await container
          .read(checkInProvider.notifier)
          .recordAnswer(sessionId: 's1', value: 7);

      final state = container.read(checkInProvider);
      expect(state.currentStepIndex, 1);
      expect(state.answers[0], 7);
    });

    test('records null for skipped item and advances step', () async {
      final container = makeContainer();
      await sessionDao.createSession('s1', DateTime.utc(2026, 3, 3), 'UTC');
      await container.read(checkInProvider.notifier).startCheckIn();

      await container
          .read(checkInProvider.notifier)
          .recordAnswer(sessionId: 's1', value: null);

      final state = container.read(checkInProvider);
      expect(state.currentStepIndex, 1);
      expect(state.answers[0], isNull);
    });

    test('is a no-op when not active', () async {
      final container = makeContainer();
      // Not started — state is inactive.
      await container
          .read(checkInProvider.notifier)
          .recordAnswer(sessionId: 'x', value: 5);

      final state = container.read(checkInProvider);
      expect(state.isActive, isFalse);
      expect(state.currentStepIndex, 0);
    });

    test('saves after last item — sets isSaved and compositeScore', () async {
      final container = makeContainer();
      await sessionDao.createSession('s1', DateTime.utc(2026, 3, 3), 'UTC');
      await container.read(checkInProvider.notifier).startCheckIn();

      final notifier = container.read(checkInProvider.notifier);
      for (var i = 0; i < 6; i++) {
        await notifier.recordAnswer(sessionId: 's1', value: 7);
      }

      final state = container.read(checkInProvider);
      expect(state.isSaved, isTrue);
      expect(state.compositeScore, isNotNull);
      expect(state.isComplete, isTrue);
    });

    test('all-skipped — does not save, sets inactive', () async {
      final container = makeContainer();
      await sessionDao.createSession('s1', DateTime.utc(2026, 3, 3), 'UTC');
      await container.read(checkInProvider.notifier).startCheckIn();

      final notifier = container.read(checkInProvider.notifier);
      for (var i = 0; i < 6; i++) {
        await notifier.recordAnswer(sessionId: 's1', value: null);
      }

      final state = container.read(checkInProvider);
      expect(state.isSaved, isFalse);
      expect(state.compositeScore, isNull);
      expect(state.isActive, isFalse);
    });

    test('mixed answers — saves with non-null compositeScore', () async {
      final container = makeContainer();
      await sessionDao.createSession('s1', DateTime.utc(2026, 3, 3), 'UTC');
      await container.read(checkInProvider.notifier).startCheckIn();

      final notifier = container.read(checkInProvider.notifier);
      // Answer 3, skip 3.
      for (var i = 0; i < 3; i++) {
        await notifier.recordAnswer(sessionId: 's1', value: 8);
      }
      for (var i = 0; i < 3; i++) {
        await notifier.recordAnswer(sessionId: 's1', value: null);
      }

      final state = container.read(checkInProvider);
      expect(state.isSaved, isTrue);
      expect(state.compositeScore, isNotNull);
    });

    test('second session uses its own data', () async {
      final container = makeContainer();
      await sessionDao.createSession('s1', DateTime.utc(2026, 3, 3), 'UTC');
      await sessionDao.createSession('s2', DateTime.utc(2026, 3, 3), 'UTC');

      await container.read(checkInProvider.notifier).startCheckIn();
      final notifier = container.read(checkInProvider.notifier);
      for (var i = 0; i < 6; i++) {
        await notifier.recordAnswer(sessionId: 's2', value: 5);
      }

      expect(container.read(checkInProvider).isSaved, isTrue);
    });
  });

  // ---------------------------------------------------------------------------
  // flagParseError
  // ---------------------------------------------------------------------------

  group('CheckInNotifier.flagParseError', () {
    test('sets lastParseError', () async {
      final container = makeContainer();
      await container.read(checkInProvider.notifier).startCheckIn();
      container.read(checkInProvider.notifier).flagParseError('Bad input');

      expect(container.read(checkInProvider).lastParseError, 'Bad input');
    });

    test('recordAnswer clears lastParseError', () async {
      final container = makeContainer();
      await sessionDao.createSession('s1', DateTime.utc(2026, 3, 3), 'UTC');
      await container.read(checkInProvider.notifier).startCheckIn();
      container.read(checkInProvider.notifier).flagParseError('Bad input');

      await container
          .read(checkInProvider.notifier)
          .recordAnswer(sessionId: 's1', value: 5);

      expect(container.read(checkInProvider).lastParseError, isNull);
    });

    test('flagParseError on inactive state is a no-op (does not throw)', () {
      final container = makeContainer();
      // No startCheckIn — isActive = false.
      expect(
        () => container.read(checkInProvider.notifier).flagParseError('x'),
        returnsNormally,
      );
    });
  });

  // ---------------------------------------------------------------------------
  // activeCheckInItemsProvider
  // ---------------------------------------------------------------------------

  group('activeCheckInItemsProvider', () {
    test('emits empty list when no default template exists', () async {
      final container = makeContainer();
      final items = await container.read(activeCheckInItemsProvider.future);
      expect(items, isEmpty);
    });

    test('emits items after default template is seeded', () async {
      final container = makeContainer();
      // Seed the default template via startCheckIn.
      await container.read(checkInProvider.notifier).startCheckIn();

      final items = await container.read(activeCheckInItemsProvider.future);
      expect(items, hasLength(6));
    });
  });

  // ---------------------------------------------------------------------------
  // Voice method early-return guards (no TTS triggered)
  // ---------------------------------------------------------------------------

  group('CheckInNotifier voice method guards', () {
    test('handleVoiceAnswer is a no-op when not active', () async {
      final container = makeContainer();
      // Not started — template is null and isActive is false.
      // The method returns at the first guard without reading TTS provider.
      await container
          .read(checkInProvider.notifier)
          .handleVoiceAnswer(sessionId: 'x', rawText: '7');
      // State unchanged.
      expect(container.read(checkInProvider).isActive, isFalse);
    });

    test('speakCurrentQuestion is a no-op when no current item', () async {
      final container = makeContainer();
      // Not started — currentItem is null (items list is empty).
      // The method returns at the guard without reading TTS provider.
      await container.read(checkInProvider.notifier).speakCurrentQuestion();
      expect(container.read(checkInProvider).isActive, isFalse);
    });
  });
}
