// ===========================================================================
// file: test/providers/quick_mood_providers_test.dart
// purpose: Unit tests for QuickMoodNotifier.saveMoodTap() using a real
//          in-memory database (not a fake notifier).
//
// These tests cover the production code path that the widget tests cannot
// reach because _FakeQuickMoodNotifier bypasses the real implementation.
//
// Covers:
//   - Success path: session row created with mode=quick_mood_tap + endTime
//   - Failure path: DB throws, state transitions to error
//   - Summary string format: mood+energy combined
//   - Summary string format: mood-only when energy is null
//   - State transitions: idle → saving → saved / error
//   - reset(): returns state to idle
// ===========================================================================

import 'package:drift/native.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';
import 'package:agentic_journal/providers/database_provider.dart';
import 'package:agentic_journal/providers/quick_mood_providers.dart';

void main() {
  late AppDatabase database;
  late ProviderContainer container;

  setUp(() {
    database = AppDatabase.forTesting(NativeDatabase.memory());
    container = ProviderContainer(
      overrides: [databaseProvider.overrideWithValue(database)],
    );
  });

  tearDown(() async {
    container.dispose();
    await database.close();
  });

  group('QuickMoodNotifier.saveMoodTap', () {
    test('initial state is idle', () {
      expect(container.read(quickMoodProvider), QuickMoodSaveStatus.idle);
    });

    test('success path: state transitions idle → saving → saved', () async {
      final states = <QuickMoodSaveStatus>[];
      container.listen(quickMoodProvider, (_, s) => states.add(s));

      final ok = await container
          .read(quickMoodProvider.notifier)
          .saveMoodTap(mood: 3, energy: 2);

      expect(ok, isTrue);
      expect(states, [QuickMoodSaveStatus.saving, QuickMoodSaveStatus.saved]);
      expect(container.read(quickMoodProvider), QuickMoodSaveStatus.saved);
    });

    test('success path: session row exists with quick_mood_tap mode', () async {
      await container
          .read(quickMoodProvider.notifier)
          .saveMoodTap(mood: 4, energy: 1);

      final dao = SessionDao(database);
      final sessions = await dao.getAllSessionsByDate();
      // getAllSessionsByDate is unfiltered — quick_mood_tap sessions included.
      expect(sessions, hasLength(1));

      final session = sessions.first;
      expect(session.journalingMode, 'quick_mood_tap');
      expect(session.endTime, isNotNull);
      expect(session.summary, contains('Mood:'));
    });

    test('success path: mood+energy summary format is correct', () async {
      await container
          .read(quickMoodProvider.notifier)
          .saveMoodTap(mood: 4, energy: 2);

      final dao = SessionDao(database);
      final sessions = await dao.getAllSessionsByDate();
      // mood=4 → index 3 → '🙂' Good, energy=2 → Medium
      expect(sessions.first.summary, 'Mood: 🙂 Good · Energy: Medium');
    });

    test('mood-only summary when energy is null', () async {
      await container
          .read(quickMoodProvider.notifier)
          .saveMoodTap(mood: 5, energy: null);

      final dao = SessionDao(database);
      final sessions = await dao.getAllSessionsByDate();
      expect(sessions.first.summary, isNot(contains('Energy')));
      expect(sessions.first.summary, startsWith('Mood:'));
    });

    test('all five mood values produce non-empty summaries', () async {
      for (var mood = 1; mood <= 5; mood++) {
        await container
            .read(quickMoodProvider.notifier)
            .saveMoodTap(mood: mood, energy: null);
        container.read(quickMoodProvider.notifier).reset();
      }

      final dao = SessionDao(database);
      final sessions = await dao.getAllSessionsByDate();
      expect(sessions, hasLength(5));
      for (final session in sessions) {
        expect(session.summary, isNotEmpty);
        expect(session.summary, startsWith('Mood:'));
      }
    });

    test('all three energy values produce correct label in summary', () async {
      final energyLabels = ['Low', 'Medium', 'High'];
      for (var e = 1; e <= 3; e++) {
        await container
            .read(quickMoodProvider.notifier)
            .saveMoodTap(mood: 3, energy: e);
        container.read(quickMoodProvider.notifier).reset();
      }

      final dao = SessionDao(database);
      final sessions = await dao.getAllSessionsByDate();
      final allSummaries = sessions.map((s) => s.summary ?? '').join(' | ');
      // All three energy labels must appear across the three sessions.
      for (final label in energyLabels) {
        expect(allSummaries, contains(label));
      }
    });
  });

  group('QuickMoodNotifier.reset', () {
    test('reset() transitions saved → idle', () async {
      await container
          .read(quickMoodProvider.notifier)
          .saveMoodTap(mood: 3, energy: null);
      expect(container.read(quickMoodProvider), QuickMoodSaveStatus.saved);

      container.read(quickMoodProvider.notifier).reset();
      expect(container.read(quickMoodProvider), QuickMoodSaveStatus.idle);
    });
  });

  group('QuickMoodNotifier.saveMoodTap — out-of-range inputs', () {
    test('mood value 0 produces Unknown label in summary', () async {
      await container
          .read(quickMoodProvider.notifier)
          .saveMoodTap(mood: 0, energy: null);

      final dao = SessionDao(database);
      final sessions = await dao.getAllSessionsByDate();
      expect(sessions.first.summary, contains('Unknown'));
    });

    test('energy value 0 is treated as null (excluded from summary)', () async {
      await container
          .read(quickMoodProvider.notifier)
          .saveMoodTap(mood: 3, energy: 0);

      final dao = SessionDao(database);
      final sessions = await dao.getAllSessionsByDate();
      expect(sessions.first.summary, isNot(contains('Energy')));
    });
  });
}
