// ===========================================================================
// file: lib/providers/check_in_trend_provider.dart
// purpose: Riverpod providers for Phase 4E Check-In Trend Analysis.
//
// Providers:
//   correlationServiceProvider — const CorrelationService singleton
//   checkInTrendProvider       — derives DailyItemValues + CheckInTrendData
//                                from the existing checkInHistoryProvider
//
// Data flow:
//   checkInHistoryProvider (List<CheckInHistoryEntry>)
//     → normalize per-day item values to [0, 1]
//     → compute correlation matrix + rolling averages + narrative
//     → yield CheckInTrendData
//
// Design notes:
//   - Uses ref.watch(checkInHistoryProvider) to auto-react to new check-ins
//   - All heavy computation is pure Dart (no async I/O) — runs synchronously
//     on each emission
//   - Normalization uses scaleMin/scaleMax from the CheckInHistoryEntry to
//     handle templates with different answer scales
//
// ADHD Clinical UX:
//   - Missing days are represented as null values, never as zeros
//   - Narrative uses epistemic humility framing (see CorrelationService)
//
// See: lib/services/correlation_service.dart, SPEC-20260302 Phase 4E
// ===========================================================================

import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/questionnaire_providers.dart';
import '../services/correlation_service.dart';

/// Singleton [CorrelationService] — pure, stateless, shared.
final correlationServiceProvider = Provider<CorrelationService>(
  (_) => const CorrelationService(),
);

/// Aggregated trend analysis data derived from check-in history.
///
/// Computed from [checkInHistoryProvider] on every new emission (i.e.,
/// every time a new check-in is recorded). All heavy math runs in the
/// `StreamProvider` body so the UI receives ready-to-display data.
class CheckInTrendData {
  /// Sorted chronological daily averages (oldest → newest), normalized [0,1].
  final List<DailyItemValues> days;

  /// Pairwise Pearson correlations for all active item pairs.
  final List<DimensionCorrelation> correlations;

  /// Item id → display-label mapping for all active items.
  final Map<int, String> itemText;

  /// Ordered list of active item IDs (for consistent heatmap column order).
  final List<int> itemIds;

  /// Plain-language insights with epistemic humility framing.
  final List<TrendInsight> insights;

  /// Whether there are enough data points to compute meaningful trends.
  ///
  /// True when [days.length] >= 2.
  bool get hasSufficientData => days.length >= 2;

  const CheckInTrendData({
    required this.days,
    required this.correlations,
    required this.itemText,
    required this.itemIds,
    required this.insights,
  });

  /// Empty state returned before the first check-in exists.
  static const empty = CheckInTrendData(
    days: [],
    correlations: [],
    itemText: {},
    itemIds: [],
    insights: [],
  );
}

/// Streams [CheckInTrendData] derived from [checkInHistoryProvider].
///
/// Normalization converts raw integer answers to [0.0, 1.0] using each
/// entry's [CheckInHistoryEntry.scaleMin] and [CheckInHistoryEntry.scaleMax].
/// Days with no answers for a dimension produce null values (not 0).
///
/// Correlation and rolling average computation happens synchronously on
/// each list emission — no additional async work.
///
/// Uses [ref.listen] + [StreamController] rather than [async*] with the
/// deprecated `.stream` property (removed in Riverpod 3.0).
final checkInTrendProvider = StreamProvider<CheckInTrendData>((ref) {
  final correlationSvc = ref.read(correlationServiceProvider);
  final controller = StreamController<CheckInTrendData>();

  // Compute trend data for one emission of checkInHistoryProvider.
  CheckInTrendData compute(List<CheckInHistoryEntry> entries) {
    if (entries.isEmpty) return CheckInTrendData.empty;

    // Collect item labels from all entries.
    final itemText = <int, String>{};
    for (final entry in entries) {
      itemText.addAll(entry.itemText);
    }
    final itemIds = itemText.keys.toList()..sort();

    // Group entries by local calendar date, computing per-item daily averages.
    // Normalization: (rawValue - scaleMin) / (scaleMax - scaleMin).
    final byDay = <String, _DayAccumulator>{};
    for (final entry in entries) {
      final local = entry.response.completedAt.toLocal();
      final dayKey =
          '${local.year}-'
          '${local.month.toString().padLeft(2, '0')}-'
          '${local.day.toString().padLeft(2, '0')}';
      // Normalize to midnight local time for DST-safe rolling-window cutoff.
      final midnight = DateTime(local.year, local.month, local.day);
      byDay.putIfAbsent(dayKey, () => _DayAccumulator(date: midnight));

      for (final answer in entry.answers) {
        if (answer.value == null) continue;
        // Apply reverse-scoring before normalization so that reverse-scored
        // dimensions (e.g., Anxiety: isReversed=true) are semantically aligned
        // with forward-scored dimensions for correlation analysis.
        // This mirrors the formula used in CheckInScoreService.
        final isReversed = entry.itemIsReversed[answer.itemId] ?? false;
        final rawValue = isReversed
            ? (entry.scaleMax + entry.scaleMin - answer.value!).toDouble()
            : answer.value!.toDouble();
        final normalized = CorrelationService.normalizeAnswer(
          value: rawValue,
          scaleMin: entry.scaleMin.toDouble(),
          scaleMax: entry.scaleMax.toDouble(),
        );
        byDay[dayKey]!.addValue(answer.itemId, normalized);
      }
    }

    // Build sorted DailyItemValues list (oldest first).
    final sortedKeys = byDay.keys.toList()..sort();
    final days = sortedKeys.map((k) => byDay[k]!.toDailyItemValues()).toList();

    // Compute correlation matrix.
    final correlations = correlationSvc.correlationMatrix(days, itemIds);

    // Generate narrative insights.
    final insights = correlationSvc.generateInsights(
      correlations: correlations,
      itemText: itemText,
      totalDays: days.length,
    );

    return CheckInTrendData(
      days: days,
      correlations: correlations,
      itemText: itemText,
      itemIds: itemIds,
      insights: insights,
    );
  }

  // Listen to checkInHistoryProvider and re-compute on every emission.
  // fireImmediately: true ensures the initial value is pushed immediately.
  ref.listen<AsyncValue<List<CheckInHistoryEntry>>>(checkInHistoryProvider, (
    _,
    next,
  ) {
    next.whenData((entries) {
      if (!controller.isClosed) {
        controller.add(compute(entries));
      }
    });
  }, fireImmediately: true);

  ref.onDispose(controller.close);
  return controller.stream;
});

// ---------------------------------------------------------------------------
// Internal helper: accumulates normalized values for one calendar day.
// ---------------------------------------------------------------------------

class _DayAccumulator {
  final DateTime date;
  final Map<int, List<double>> _values = {};

  _DayAccumulator({required this.date});

  void addValue(int itemId, double normalizedValue) {
    _values.putIfAbsent(itemId, () => []).add(normalizedValue);
  }

  DailyItemValues toDailyItemValues() {
    final averages = <int, double?>{};
    for (final entry in _values.entries) {
      final vals = entry.value;
      averages[entry.key] = vals.isEmpty
          ? null
          : vals.reduce((a, b) => a + b) / vals.length;
    }
    return DailyItemValues(date: date, values: averages);
  }
}
