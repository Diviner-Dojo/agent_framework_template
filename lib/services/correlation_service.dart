// ===========================================================================
// file: lib/services/correlation_service.dart
// purpose: Statistical analysis for Pulse Check-In trend view (Phase 4E).
//
// Provides:
//   - Pearson correlation between check-in dimension pairs
//   - Rolling averages over configurable day windows (7/14/30)
//   - Algorithmic narrative with epistemic humility framing (ADHD-safe)
//
// All methods are pure functions — no state, no I/O, testable without
// mocking. Accepts pre-aggregated daily data from CheckInTrendProvider.
//
// ADHD Clinical UX compliance (SPEC-20260302):
//   - Correlations framed as "possible relationship" — never causal
//   - No "best day" / "worst day" language
//   - Missing-data warnings when sample size < 7
//   - Correlations only surfaced when r ≥ 0.4 AND n ≥ 5 paired points
//
// See: SPEC-20260302-adhd-informed-feature-roadmap.md Phase 4E, ADR-0032
// ===========================================================================

import 'dart:math';

/// One day's averaged values across all active check-in dimensions.
///
/// Values are raw (not normalized) — normalization is applied per
/// computation by the service methods that need it.
class DailyItemValues {
  /// The local date this average represents.
  final DateTime date;

  /// Map of questionnaire item id → average normalized value [0.0, 1.0].
  ///
  /// Normalized using the template's scaleMin/scaleMax so that dimensions
  /// with different scale bounds (e.g., 1-5 vs 1-10) are comparable.
  /// Null if no answers were recorded for this item on this day.
  final Map<int, double?> values;

  const DailyItemValues({required this.date, required this.values});
}

/// Rolling average for a single item over a specific window.
class RollingPoint {
  /// The date of the most-recent day included in this window.
  final DateTime date;

  /// The rolling average value [0.0, 1.0], null if fewer than 2 data
  /// points exist in the window.
  final double? value;

  const RollingPoint({required this.date, required this.value});
}

/// Pairwise correlation result for two check-in dimensions.
class DimensionCorrelation {
  /// Item ID of the first dimension.
  final int itemIdA;

  /// Item ID of the second dimension.
  final int itemIdB;

  /// Pearson r coefficient in [-1.0, 1.0].
  /// Null when fewer than [_kMinPairedPoints] paired observations exist.
  final double? r;

  /// Number of days both dimensions had a recorded value.
  final int pairedCount;

  const DimensionCorrelation({
    required this.itemIdA,
    required this.itemIdB,
    required this.r,
    required this.pairedCount,
  });
}

/// A single plain-language insight derived from the correlation data.
class TrendInsight {
  /// The insight sentence, phrased with epistemic humility.
  final String text;

  /// Whether this insight carries a missing-data caveat.
  final bool hasMissingDataWarning;

  const TrendInsight({required this.text, this.hasMissingDataWarning = false});
}

/// Minimum paired observations required to report a correlation.
/// Below this threshold the statistic is too noisy to surface.
const int _kMinPairedPoints = 5;

/// Minimum |r| to surface a correlation in the narrative.
const double _kNarrativeThreshold = 0.4;

/// Pure-function service for check-in trend analysis.
///
/// Instantiate once (e.g., via Riverpod `Provider`) and reuse across
/// provider calls. All methods are side-effect free.
class CorrelationService {
  const CorrelationService();

  // ---------------------------------------------------------------------------
  // Pearson Correlation
  // ---------------------------------------------------------------------------

  /// Computes the Pearson correlation coefficient between [xs] and [ys].
  ///
  /// Returns null when fewer than [_kMinPairedPoints] paired values exist
  /// or when either series has zero variance (constant values).
  double? pearson(List<double> xs, List<double> ys) {
    assert(xs.length == ys.length, 'xs and ys must have the same length');
    if (xs.length < _kMinPairedPoints) return null;

    final n = xs.length;
    final xMean = xs.reduce((a, b) => a + b) / n;
    final yMean = ys.reduce((a, b) => a + b) / n;

    double numerator = 0;
    double xSumSq = 0;
    double ySumSq = 0;

    for (int i = 0; i < n; i++) {
      final xd = xs[i] - xMean;
      final yd = ys[i] - yMean;
      numerator += xd * yd;
      xSumSq += xd * xd;
      ySumSq += yd * yd;
    }

    final denominator = sqrt(xSumSq * ySumSq);
    if (denominator < 1e-10) return null; // zero variance in one series
    return (numerator / denominator).clamp(-1.0, 1.0);
  }

  // ---------------------------------------------------------------------------
  // Correlation Matrix
  // ---------------------------------------------------------------------------

  /// Computes pairwise Pearson correlations for all pairs of [itemIds].
  ///
  /// For each pair (A, B), collects days where both A and B have a non-null
  /// value and computes Pearson r on those paired observations.
  ///
  /// Returns one [DimensionCorrelation] per unique ordered pair (A < B).
  List<DimensionCorrelation> correlationMatrix(
    List<DailyItemValues> days,
    List<int> itemIds,
  ) {
    final results = <DimensionCorrelation>[];
    for (int i = 0; i < itemIds.length; i++) {
      for (int j = i + 1; j < itemIds.length; j++) {
        final idA = itemIds[i];
        final idB = itemIds[j];

        final xs = <double>[];
        final ys = <double>[];
        for (final day in days) {
          final va = day.values[idA];
          final vb = day.values[idB];
          if (va != null && vb != null) {
            xs.add(va);
            ys.add(vb);
          }
        }

        results.add(
          DimensionCorrelation(
            itemIdA: idA,
            itemIdB: idB,
            r: pearson(xs, ys),
            pairedCount: xs.length,
          ),
        );
      }
    }
    return results;
  }

  // ---------------------------------------------------------------------------
  // Rolling Averages
  // ---------------------------------------------------------------------------

  /// Computes rolling averages for [itemId] over a [windowDays] window.
  ///
  /// For each day in [days], looks back [windowDays] calendar days and
  /// averages all non-null values found in that window (inclusive of the
  /// anchor day). Returns null for a point when fewer than 2 values exist
  /// in the window.
  List<RollingPoint> rollingAverages({
    required List<DailyItemValues> days,
    required int itemId,
    required int windowDays,
  }) {
    // Guard: caller must pass days sorted oldest-first (ascending by date).
    // Violated sort order causes the backward-walk cutoff to break early,
    // silently excluding days that should be inside the window.
    assert(() {
      for (int i = 1; i < days.length; i++) {
        if (days[i].date.isBefore(days[i - 1].date)) return false;
      }
      return true;
    }(), 'rollingAverages: days must be sorted oldest-first (ascending)');

    final result = <RollingPoint>[];
    for (int i = 0; i < days.length; i++) {
      final anchor = days[i].date;
      final cutoff = anchor.subtract(Duration(days: windowDays - 1));

      // Collect values in [cutoff, anchor] window.
      final windowValues = <double>[];
      for (int k = i; k >= 0; k--) {
        if (days[k].date.isBefore(cutoff)) break;
        final v = days[k].values[itemId];
        if (v != null) windowValues.add(v);
      }

      final avg = windowValues.length < 2
          ? null
          : windowValues.reduce((a, b) => a + b) / windowValues.length;

      result.add(RollingPoint(date: anchor, value: avg));
    }
    return result;
  }

  // ---------------------------------------------------------------------------
  // Narrative Generation (Algorithmic, ADHD-safe)
  // ---------------------------------------------------------------------------

  /// Generates plain-language insights from [correlations] and [itemText].
  ///
  /// Only correlations with |r| ≥ [_kNarrativeThreshold] and sufficient
  /// paired data are surfaced. Framing is epistemic: "possible relationship"
  /// language, no causal claims, no evaluative labels.
  ///
  /// Returns an empty list when there is insufficient data.
  List<TrendInsight> generateInsights({
    required List<DimensionCorrelation> correlations,
    required Map<int, String> itemText,
    required int totalDays,
  }) {
    final insights = <TrendInsight>[];

    // Low-data warning — surface as a soft advisory.
    if (totalDays < 7) {
      insights.add(
        const TrendInsight(
          text:
              'More check-ins will reveal patterns. Come back after a few more sessions.',
          hasMissingDataWarning: true,
        ),
      );
      return insights;
    }

    // Surface notable correlations.
    final notable = correlations.where(
      (c) =>
          c.r != null &&
          c.r!.abs() >= _kNarrativeThreshold &&
          c.pairedCount >= _kMinPairedPoints,
    );

    // Sort by absolute correlation strength (strongest first).
    final sorted = notable.toList()
      ..sort((a, b) => b.r!.abs().compareTo(a.r!.abs()));

    // Cap at 3 insights to avoid overwhelm.
    for (final corr in sorted.take(3)) {
      final nameA = _shortLabel(itemText[corr.itemIdA] ?? 'Dimension A');
      final nameB = _shortLabel(itemText[corr.itemIdB] ?? 'Dimension B');
      final direction = corr.r! > 0
          ? 'move together'
          : 'move in opposite directions';
      final strength = corr.r!.abs() >= 0.7 ? 'often' : 'sometimes';

      insights.add(
        TrendInsight(
          text:
              'Your $nameA and $nameB scores $strength $direction — '
              'possible relationship (${corr.pairedCount} shared days).',
          hasMissingDataWarning: corr.pairedCount < 10,
        ),
      );
    }

    if (insights.isEmpty) {
      insights.add(
        const TrendInsight(
          text:
              'No strong patterns detected yet. Patterns emerge over time — '
              'keep checking in.',
        ),
      );
    }

    return insights;
  }

  // ---------------------------------------------------------------------------
  // Normalization
  // ---------------------------------------------------------------------------

  /// Normalizes a raw answer value to [0.0, 1.0] using the template scale.
  ///
  /// Returns 0.5 when [scaleMin] == [scaleMax] (degenerate scale — no
  /// division-by-zero). Clamps out-of-range values to [0.0, 1.0] to guard
  /// against malformed entries.
  static double normalizeAnswer({
    required double value,
    required double scaleMin,
    required double scaleMax,
  }) {
    final range = scaleMax - scaleMin;
    if (range <= 0) return 0.5;
    return ((value - scaleMin) / range).clamp(0.0, 1.0);
  }

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  /// Shortens a question-text label for use in narrative prose.
  ///
  /// Takes the first word (or up to 12 characters), lowercased.
  String _shortLabel(String questionText) {
    final words = questionText.trim().split(RegExp(r'\s+'));
    // Remove leading "How is your" / "How well did you" preamble if present.
    final filtered = words.where(
      (w) => !{
        'how',
        'is',
        'your',
        'well',
        'did',
        'you',
        'rate',
      }.contains(w.toLowerCase()),
    );
    final label = filtered.isEmpty ? questionText : filtered.first;
    return label.length > 12 ? label.substring(0, 12) : label;
  }
}
