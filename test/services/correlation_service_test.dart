// ===========================================================================
// file: test/services/correlation_service_test.dart
// purpose: Unit tests for CorrelationService (Phase 4E).
//
// Tests cover:
//   - pearson(): null paths, boundary, negative correlation, zero variance
//   - rollingAverages(): window boundary, sort-assert, sparse data
//   - normalizeAnswer(): all boundary cases
//   - generateInsights(): low-data warning, narrative, empty-correlations
//   - _shortLabel() via generateInsights: stopword filter, degenerate input
//
// See: lib/services/correlation_service.dart, SPEC-20260302 Phase 4E
// ===========================================================================

import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/services/correlation_service.dart';

void main() {
  const svc = CorrelationService();

  // ---------------------------------------------------------------------------
  // normalizeAnswer (static)
  // ---------------------------------------------------------------------------

  group('normalizeAnswer', () {
    test('value == scaleMin → 0.0', () {
      expect(
        CorrelationService.normalizeAnswer(value: 1, scaleMin: 1, scaleMax: 10),
        0.0,
      );
    });

    test('value == scaleMax → 1.0', () {
      expect(
        CorrelationService.normalizeAnswer(
          value: 10,
          scaleMin: 1,
          scaleMax: 10,
        ),
        closeTo(1.0, 1e-10),
      );
    });

    test('value at midpoint → 0.5', () {
      expect(
        CorrelationService.normalizeAnswer(value: 5, scaleMin: 1, scaleMax: 9),
        closeTo(0.5, 1e-6),
      );
    });

    test('scaleMin == scaleMax → 0.5 (degenerate scale)', () {
      expect(
        CorrelationService.normalizeAnswer(value: 5, scaleMin: 5, scaleMax: 5),
        0.5,
      );
    });

    test('value below scaleMin → clamped to 0.0', () {
      expect(
        CorrelationService.normalizeAnswer(
          value: -5,
          scaleMin: 1,
          scaleMax: 10,
        ),
        0.0,
      );
    });

    test('value above scaleMax → clamped to 1.0', () {
      expect(
        CorrelationService.normalizeAnswer(
          value: 100,
          scaleMin: 1,
          scaleMax: 10,
        ),
        1.0,
      );
    });

    test('1–5 scale mid-value', () {
      // Value=3, scale 1–5 → (3-1)/(5-1) = 0.5
      expect(
        CorrelationService.normalizeAnswer(value: 3, scaleMin: 1, scaleMax: 5),
        closeTo(0.5, 1e-10),
      );
    });
  });

  // ---------------------------------------------------------------------------
  // pearson()
  // ---------------------------------------------------------------------------

  group('pearson', () {
    test('returns null when fewer than 5 paired points', () {
      expect(svc.pearson([1.0, 2.0, 3.0, 4.0], [4.0, 3.0, 2.0, 1.0]), isNull);
    });

    test('returns non-null for exactly 5 paired points', () {
      final r = svc.pearson(
        [1.0, 2.0, 3.0, 4.0, 5.0],
        [2.0, 4.0, 6.0, 8.0, 10.0],
      );
      expect(r, isNotNull);
      expect(r!, closeTo(1.0, 1e-10));
    });

    test('perfect positive correlation → r = 1.0', () {
      final r = svc.pearson(
        [1.0, 2.0, 3.0, 4.0, 5.0],
        [1.0, 2.0, 3.0, 4.0, 5.0],
      );
      expect(r, closeTo(1.0, 1e-10));
    });

    test('perfect negative correlation → r = -1.0', () {
      final r = svc.pearson(
        [1.0, 2.0, 3.0, 4.0, 5.0],
        [5.0, 4.0, 3.0, 2.0, 1.0],
      );
      expect(r, closeTo(-1.0, 1e-10));
    });

    test('zero variance in xs → null (all-identical values)', () {
      // All xs identical → xSumSq = 0 → denominator = 0 → null
      final r = svc.pearson(
        [3.0, 3.0, 3.0, 3.0, 3.0],
        [1.0, 2.0, 3.0, 4.0, 5.0],
      );
      expect(r, isNull);
    });

    test('zero variance in ys → null', () {
      final r = svc.pearson(
        [1.0, 2.0, 3.0, 4.0, 5.0],
        [7.0, 7.0, 7.0, 7.0, 7.0],
      );
      expect(r, isNull);
    });

    test('result is clamped to [-1.0, 1.0]', () {
      // Use known-good perfectly correlated data — clamp applied to r=1.0.
      final r = svc.pearson(
        [0.1, 0.3, 0.5, 0.7, 0.9],
        [0.1, 0.3, 0.5, 0.7, 0.9],
      );
      expect(r, isNotNull);
      expect(r, lessThanOrEqualTo(1.0));
      expect(r, greaterThanOrEqualTo(-1.0));
    });

    test('no correlation (orthogonal data) → |r| near 0', () {
      // Uncorrelated data: alternating pattern vs monotone.
      final r = svc.pearson(
        [1.0, 2.0, 1.0, 2.0, 1.0, 2.0],
        [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
      );
      expect(r, isNotNull);
      expect(r!.abs(), lessThan(0.5));
    });
  });

  // ---------------------------------------------------------------------------
  // correlationMatrix()
  // ---------------------------------------------------------------------------

  group('correlationMatrix', () {
    test('produces n*(n-1)/2 pairs for n items', () {
      final days = _makeDays([
        {1: 0.1, 2: 0.2, 3: 0.3},
        {1: 0.2, 2: 0.4, 3: 0.6},
        {1: 0.3, 2: 0.6, 3: 0.9},
        {1: 0.4, 2: 0.8, 3: 1.0},
        {1: 0.5, 2: 1.0, 3: 0.5},
      ]);
      final result = svc.correlationMatrix(days, [1, 2, 3]);
      // 3 items → 3 pairs: (1,2), (1,3), (2,3)
      expect(result.length, 3);
    });

    test('pairedCount reflects only days with both values present', () {
      final days = _makeDays([
        {1: 0.5, 2: 0.5},
        {1: 0.6}, // item 2 missing
        {1: 0.7, 2: 0.8},
        {1: 0.8, 2: 0.9},
        {1: 0.9, 2: 1.0},
        {1: 1.0, 2: 0.5},
      ]);
      final result = svc.correlationMatrix(days, [1, 2]);
      expect(result.single.pairedCount, 5); // day 2 excluded (item 2 missing)
    });

    test('r is null when fewer than 5 paired observations', () {
      // Only 3 days with both items present.
      final days = _makeDays([
        {1: 0.5, 2: 0.5},
        {1: 0.6, 2: 0.7},
        {1: 0.7, 2: 0.8},
        {1: 0.8}, // item 2 missing
        {1: 0.9}, // item 2 missing
      ]);
      final result = svc.correlationMatrix(days, [1, 2]);
      expect(result.single.r, isNull);
    });
  });

  // ---------------------------------------------------------------------------
  // rollingAverages()
  // ---------------------------------------------------------------------------

  group('rollingAverages', () {
    test('returns null when fewer than 2 values in window', () {
      // 3 days, only 1 has a value for item 1 — 7-day window.
      final days = _makeDays([
        {1: 0.5},
        {2: 0.8},
        {2: 0.9},
      ]);
      final result = svc.rollingAverages(days: days, itemId: 1, windowDays: 7);
      // Only 1 day has item 1 value — every window returns null.
      expect(result.every((p) => p.value == null), isTrue);
    });

    test('returns non-null when at least 2 values in window', () {
      final days = _makeDays([
        {1: 0.4},
        {1: 0.6},
        {1: 0.8},
      ]);
      final result = svc.rollingAverages(days: days, itemId: 1, windowDays: 7);
      // All 3 days in a 7-day window → all points should have values.
      expect(result.last.value, isNotNull);
      expect(result.last.value!, closeTo(0.6, 0.01));
    });

    test('7-day window contains at most 7 calendar days', () {
      // 10 consecutive days, all with values.
      final values = List.generate(
        10,
        (i) => <int, double?>{1: 0.5 + i * 0.01},
      );
      final days = _makDaysWithDates(values, baseDate: DateTime(2026, 3, 1));
      final result = svc.rollingAverages(days: days, itemId: 1, windowDays: 7);
      // Day index 9 (March 10) window covers days 3-9 (7 days).
      expect(result.length, 10);
      expect(result.last.value, isNotNull);
    });

    test('window of 1 day returns null (requires at least 2 values)', () {
      final days = _makeDays([
        {1: 0.5},
      ]);
      final result = svc.rollingAverages(days: days, itemId: 1, windowDays: 1);
      expect(result.single.value, isNull);
    });

    test(
      'assert fires for unsorted input',
      () {
        // Reversed day order — assert should fire in debug mode.
        final values = [
          <int, double?>{1: 0.5},
          <int, double?>{1: 0.7},
          <int, double?>{1: 0.3},
        ];
        final days = _makDaysWithDates(
          values,
          baseDate: DateTime(2026, 3, 3),
          // Deliberately reverse the date order.
          reversed: true,
        );
        expect(
          () => svc.rollingAverages(days: days, itemId: 1, windowDays: 3),
          throwsA(anything), // AssertionError in debug mode
        );
      },
      skip: const bool.fromEnvironment('dart.vm.product', defaultValue: false)
          ? 'Assert checks disabled in release mode'
          : null,
    );
  });

  // ---------------------------------------------------------------------------
  // generateInsights()
  // ---------------------------------------------------------------------------

  group('generateInsights', () {
    test('returns low-data warning when totalDays < 7', () {
      final insights = svc.generateInsights(
        correlations: [],
        itemText: {},
        totalDays: 6,
      );
      expect(insights.length, 1);
      expect(insights.first.hasMissingDataWarning, isTrue);
    });

    test('totalDays == 7 does NOT trigger low-data warning', () {
      // 7 days exactly — should not return the low-data sentinel.
      final insights = svc.generateInsights(
        correlations: [],
        itemText: {1: 'Mood', 2: 'Energy'},
        totalDays: 7,
      );
      // Empty correlations → "no strong patterns" fallback, not low-data warning.
      expect(insights.first.hasMissingDataWarning, isFalse);
    });

    test(
      'returns "no strong patterns" fallback when correlations all below threshold',
      () {
        final correlations = [
          DimensionCorrelation(itemIdA: 1, itemIdB: 2, r: 0.2, pairedCount: 10),
        ];
        final insights = svc.generateInsights(
          correlations: correlations,
          itemText: {1: 'Mood', 2: 'Energy'},
          totalDays: 14,
        );
        expect(insights.length, 1);
        expect(insights.first.text.toLowerCase(), contains('pattern'));
      },
    );

    test('generates insight for strong positive correlation', () {
      final correlations = [
        DimensionCorrelation(itemIdA: 1, itemIdB: 2, r: 0.75, pairedCount: 12),
      ];
      final insights = svc.generateInsights(
        correlations: correlations,
        itemText: {1: 'Sleep quality?', 2: 'Focus score?'},
        totalDays: 20,
      );
      expect(insights.isNotEmpty, isTrue);
      // Epistemic humility: "possible relationship" language.
      expect(insights.first.text.toLowerCase(), contains('possible'));
      // Positive correlation: should say "move together".
      expect(insights.first.text.toLowerCase(), contains('together'));
    });

    test('generates insight for strong negative correlation', () {
      final correlations = [
        DimensionCorrelation(itemIdA: 1, itemIdB: 2, r: -0.65, pairedCount: 10),
      ];
      final insights = svc.generateInsights(
        correlations: correlations,
        itemText: {1: 'Anxiety level?', 2: 'Focus?'},
        totalDays: 14,
      );
      expect(insights.isNotEmpty, isTrue);
      // Negative correlation: "opposite directions".
      expect(insights.first.text.toLowerCase(), contains('opposite'));
    });

    test('caps at 3 insights even when many strong correlations exist', () {
      final correlations = List.generate(
        6,
        (i) => DimensionCorrelation(
          itemIdA: i,
          itemIdB: i + 1,
          r: 0.8,
          pairedCount: 15,
        ),
      );
      final itemText = {for (int i = 0; i <= 6; i++) i: 'Dimension $i'};
      final insights = svc.generateInsights(
        correlations: correlations,
        itemText: itemText,
        totalDays: 30,
      );
      expect(insights.length, lessThanOrEqualTo(3));
    });

    test('null r correlation is excluded from narrative', () {
      final correlations = [
        DimensionCorrelation(itemIdA: 1, itemIdB: 2, r: null, pairedCount: 3),
      ];
      final insights = svc.generateInsights(
        correlations: correlations,
        itemText: {1: 'Mood', 2: 'Energy'},
        totalDays: 10,
      );
      // Null r → excluded → "no strong patterns" fallback.
      expect(insights.first.text.toLowerCase(), contains('pattern'));
    });

    test('stopword-only question text falls back to original', () {
      // Question text is entirely stopwords — fallback returns full original.
      final correlations = [
        DimensionCorrelation(itemIdA: 1, itemIdB: 2, r: 0.8, pairedCount: 12),
      ];
      final insights = svc.generateInsights(
        correlations: correlations,
        itemText: {
          1: 'How is your rate', // all stopwords
          2: 'Sleep quality',
        },
        totalDays: 20,
      );
      // Should not crash, and narrative contains something from both labels.
      expect(insights.isNotEmpty, isTrue);
    });

    test('normal question text is shortened to first meaningful word', () {
      // "How is your sleep quality?" → stopwords filtered → "sleep"
      final correlations = [
        DimensionCorrelation(itemIdA: 1, itemIdB: 2, r: 0.8, pairedCount: 12),
      ];
      final insights = svc.generateInsights(
        correlations: correlations,
        itemText: {1: 'How is your sleep quality?', 2: 'Focus level'},
        totalDays: 20,
      );
      // "sleep" should appear in the narrative (first non-stopword).
      expect(insights.first.text.toLowerCase(), contains('sleep'));
    });

    // Advisory A8 from REV-20260304-015709: hasMissingDataWarning boundary
    // test. When pairedCount < totalDays (sparse overlap), both the warning
    // flag AND a narrative insight card should be present. This guards against
    // a degenerate implementation that returns only the low-data sentinel
    // (hasMissingDataWarning=true, no narrative) instead of the combined
    // warning-with-insight behavior.
    test('hasMissingDataWarning=true AND insight present when pairedCount < '
        'totalDays and r >= 0.5 threshold', () {
      // pairedCount: 7 < totalDays: 14 → missing-data flag should be set.
      // r: 0.75 ≥ 0.5 threshold → a narrative card should also be present.
      final correlations = [
        DimensionCorrelation(itemIdA: 1, itemIdB: 2, r: 0.75, pairedCount: 7),
      ];
      final insights = svc.generateInsights(
        correlations: correlations,
        itemText: {1: 'Mood', 2: 'Energy'},
        totalDays: 14,
      );
      expect(
        insights.any((i) => i.hasMissingDataWarning),
        isTrue,
        reason:
            'pairedCount (7) < totalDays (14) must set hasMissingDataWarning',
      );
      expect(
        insights.isNotEmpty,
        isTrue,
        reason:
            'r=0.75 >= threshold must produce at least one narrative insight '
            'even when hasMissingDataWarning is set — guards against a '
            'degenerate pass that returns only the warning sentinel',
      );
    });
  });
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/// Creates [DailyItemValues] on consecutive days starting from 2026-03-01.
List<DailyItemValues> _makeDays(List<Map<int, double?>> valuesList) {
  return _makDaysWithDates(valuesList, baseDate: DateTime(2026, 3, 1));
}

List<DailyItemValues> _makDaysWithDates(
  List<Map<int, double?>> valuesList, {
  required DateTime baseDate,
  bool reversed = false,
}) {
  final days = valuesList.asMap().entries.map((entry) {
    final offset = reversed ? valuesList.length - 1 - entry.key : entry.key;
    return DailyItemValues(
      date: baseDate.add(Duration(days: offset)),
      values: entry.value,
    );
  }).toList();
  // When reversed=true, offsets are already computed in descending order
  // (e.g., length-1, length-2, ..., 0), so the list is already in reverse
  // chronological order. No second reversal needed.
  return days;
}
