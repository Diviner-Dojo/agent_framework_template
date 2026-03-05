// ===========================================================================
// file: test/providers/check_in_trend_provider_test.dart
// purpose: Unit tests for CheckInTrendData + checkInTrendProvider logic.
//
// Tests cover:
//   - CheckInTrendData.empty has correct sentinel values
//   - CheckInTrendData.hasSufficientData boundary (days.length >= 2)
//   - Provider yields CheckInTrendData.empty when history is empty
//   - Provider yields populated data with correct itemIds sort order
//   - Provider normalizes answers to [0.0, 1.0] using scaleMin/scaleMax
//
// See: lib/providers/check_in_trend_provider.dart, SPEC-20260302 Phase 4E
// ===========================================================================

import 'package:drift/native.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/providers/check_in_trend_provider.dart';
import 'package:agentic_journal/providers/database_provider.dart';
import 'package:agentic_journal/providers/onboarding_providers.dart';
import 'package:agentic_journal/providers/questionnaire_providers.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/repositories/agent_repository.dart';
import 'package:agentic_journal/services/correlation_service.dart';

void main() {
  // --------------------------------------------------------------------------
  // CheckInTrendData model unit tests
  // --------------------------------------------------------------------------

  group('CheckInTrendData', () {
    test('empty sentinel has zero-length collections', () {
      const d = CheckInTrendData.empty;
      expect(d.days, isEmpty);
      expect(d.correlations, isEmpty);
      expect(d.itemText, isEmpty);
      expect(d.itemIds, isEmpty);
      expect(d.insights, isEmpty);
    });

    test('hasSufficientData is false when days is empty', () {
      expect(CheckInTrendData.empty.hasSufficientData, isFalse);
    });

    test('hasSufficientData is false with exactly 1 day', () {
      final d = CheckInTrendData(
        days: [DailyItemValues(date: DateTime(2026, 3, 1), values: const {})],
        correlations: const [],
        itemText: const {},
        itemIds: const [],
        insights: const [],
      );
      expect(d.hasSufficientData, isFalse);
    });

    test('hasSufficientData is true with 2 days', () {
      final d = CheckInTrendData(
        days: [
          DailyItemValues(date: DateTime(2026, 3, 1), values: const {}),
          DailyItemValues(date: DateTime(2026, 3, 2), values: const {}),
        ],
        correlations: const [],
        itemText: const {},
        itemIds: const [],
        insights: const [],
      );
      expect(d.hasSufficientData, isTrue);
    });
  });

  // --------------------------------------------------------------------------
  // Provider integration tests (real in-memory database)
  // --------------------------------------------------------------------------

  group('checkInTrendProvider', () {
    late AppDatabase database;
    late SharedPreferences prefs;

    setUp(() async {
      database = AppDatabase.forTesting(NativeDatabase.memory());
      SharedPreferences.setMockInitialValues({});
      prefs = await SharedPreferences.getInstance();
    });

    tearDown(() async {
      await database.close();
    });

    ProviderContainer makeContainer() => ProviderContainer(
      overrides: [
        sharedPreferencesProvider.overrideWithValue(prefs),
        databaseProvider.overrideWithValue(database),
        agentRepositoryProvider.overrideWithValue(AgentRepository()),
        deviceTimezoneProvider.overrideWith((ref) async => 'America/New_York'),
      ],
    );

    test('yields empty when no check-in history exists', () async {
      final container = makeContainer();
      addTearDown(container.dispose);

      final value = await container
          .read(checkInTrendProvider.future)
          .timeout(const Duration(seconds: 5));

      expect(value.days, isEmpty);
      expect(value.hasSufficientData, isFalse);
    });

    test('itemIds are sorted ascending after one check-in session', () async {
      final container = makeContainer();
      addTearDown(container.dispose);

      // Save one check-in with default template items.
      final sessionNotifier = container.read(sessionNotifierProvider.notifier);
      await sessionNotifier.startSession(journalingMode: 'pulse_check_in');
      final sessionId = container
          .read(sessionNotifierProvider)
          .activeSessionId!;
      final checkInNotifier = container.read(checkInProvider.notifier);
      await checkInNotifier.startCheckIn();
      final items = container.read(checkInProvider).items;
      for (var i = 0; i < items.length; i++) {
        await checkInNotifier.recordAnswer(sessionId: sessionId, value: 5);
      }

      final value = await container
          .read(checkInTrendProvider.future)
          .timeout(const Duration(seconds: 5));

      expect(value.itemIds, isNotEmpty);
      // itemIds must be in ascending sorted order.
      final sorted = List<int>.from(value.itemIds)..sort();
      expect(value.itemIds, equals(sorted));
    });

    test(
      'normalized daily values are in [0.0, 1.0] for default 1-10 scale',
      () async {
        final container = makeContainer();
        addTearDown(container.dispose);

        // Answer all items with value 7 (middle of a 1-10 scale).
        final sessionNotifier = container.read(
          sessionNotifierProvider.notifier,
        );
        await sessionNotifier.startSession(journalingMode: 'pulse_check_in');
        final sessionId = container
            .read(sessionNotifierProvider)
            .activeSessionId!;
        final checkInNotifier = container.read(checkInProvider.notifier);
        await checkInNotifier.startCheckIn();
        final items = container.read(checkInProvider).items;
        for (var i = 0; i < items.length; i++) {
          await checkInNotifier.recordAnswer(sessionId: sessionId, value: 7);
        }

        final value = await container
            .read(checkInTrendProvider.future)
            .timeout(const Duration(seconds: 5));

        // All daily item values must be normalized to [0.0, 1.0].
        for (final day in value.days) {
          for (final v in day.values.values) {
            if (v != null) {
              expect(v, greaterThanOrEqualTo(0.0));
              expect(v, lessThanOrEqualTo(1.0));
            }
          }
        }
      },
    );

    // Regression: reverse-scored items (e.g. Anxiety, isReversed=true) must be
    // re-reversed before normalization so that correlation directions are
    // semantically correct. Without this fix, anxiety=10 (worst) normalized to
    // 1.0, making it indistinguishable from a forward-scored maximum-good value.
    // Bug found: REV-20260304-094234 (independent-perspective blocking finding).
    test(
      'reverse-scored items are re-reversed before normalization (regression)',
      () async {
        final container = makeContainer();
        addTearDown(container.dispose);

        // Answer all items with the maximum raw value (10).
        // For forward-scored items (Mood, Energy, Focus, Emotions, Sleep):
        //   normalized = (10 - 1) / (10 - 1) = 1.0   (best possible)
        // For reverse-scored items (Anxiety, isReversed=true):
        //   reversed = scaleMax + scaleMin - raw = 10 + 1 - 10 = 1
        //   normalized = (1 - 1) / (10 - 1) = 0.0   (worst possible wellness)
        // Pre-fix bug: anxiety would also normalize to 1.0 without reversal.
        final sessionNotifier = container.read(
          sessionNotifierProvider.notifier,
        );
        await sessionNotifier.startSession(journalingMode: 'pulse_check_in');
        final sessionId = container
            .read(sessionNotifierProvider)
            .activeSessionId!;
        final checkInNotifier = container.read(checkInProvider.notifier);
        await checkInNotifier.startCheckIn();
        final items = container.read(checkInProvider).items;
        for (var i = 0; i < items.length; i++) {
          // Answer every item with raw value 10 (scale max).
          await checkInNotifier.recordAnswer(sessionId: sessionId, value: 10);
        }

        final value = await container
            .read(checkInTrendProvider.future)
            .timeout(const Duration(seconds: 5));

        expect(value.days, isNotEmpty);
        final day = value.days.first;

        // Find the Anxiety item ID (isReversed=true in questionnaire_defaults).
        // Check that its normalized value is 0.0 (worst wellness), not 1.0.
        final histEntry = container
            .read(checkInHistoryProvider)
            .maybeWhen(
              data: (entries) => entries.isNotEmpty ? entries.first : null,
              orElse: () => null,
            );
        if (histEntry != null) {
          final reversedItemIds = histEntry.itemIsReversed.entries
              .where((e) => e.value)
              .map((e) => e.key)
              .toList();

          for (final itemId in reversedItemIds) {
            final normalizedValue = day.values[itemId];
            if (normalizedValue != null) {
              // Reversed item with raw=10 should normalize to 0.0 (worst wellness).
              expect(
                normalizedValue,
                closeTo(0.0, 1e-6),
                reason:
                    'Reverse-scored item $itemId with raw=10 should normalize '
                    'to 0.0 (worst wellness), not 1.0',
              );
            }
          }
        }
      },
    );
  });
}
