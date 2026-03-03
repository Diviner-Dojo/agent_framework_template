// ===========================================================================
// file: lib/services/checkin_score_service.dart
// purpose: Pure stateless computation of the Pulse Check-In composite score.
//
// This service is the canonical source for the composite score formula.
// No database access, no async, no side effects.
//
// Composite score formula:
//   1. For each answered item (non-null value):
//      scoredValue = isReversed ? (scaleMax + scaleMin - rawValue) : rawValue
//   2. mean = sum(scoredValues) / answeredCount
//   3. compositeScore = (mean - scaleMin) / (scaleMax - scaleMin) * 100
//
// Edge cases (spec §Phase 1 Design Decisions):
//   - Empty items list → null (not 0 or NaN)
//   - All values null (all skipped) → null
//   - Partial completion — denominator = answered items only, not total items
//   - Single answered item — formula holds (denominator = 1)
//
// Reverse-scoring formula: scaleMax + scaleMin - rawValue
// INVARIANT: The general formula (not the +1 shortcut) is always used.
// The +1 variant is only valid when scaleMin=1 and MUST NOT be used here.
// For 1-10 scale: 10+1-raw = 11-raw (correct). For 0-10: 10+0-raw = 10-raw.
//
// See: SPEC-20260302-ADHD §Phase 1 Design Decisions, ADR-0032 §Composite Score.
// ===========================================================================

import '../database/app_database.dart';

/// Stateless service for computing Pulse Check-In composite scores.
class CheckInScoreService {
  const CheckInScoreService();

  /// Compute the composite score for a set of check-in answers.
  ///
  /// [items] — the questionnaire items in display order.
  /// [values] — the user's answers, one per item (null = skipped). Must have
  ///   the same length as [items].
  /// [scaleMin] — minimum scale value for this template (e.g., 1).
  /// [scaleMax] — maximum scale value for this template (e.g., 10).
  ///
  /// Returns null when:
  /// - [items] is empty
  /// - all values are null (all items skipped)
  ///
  /// Returns 0.0–100.0 otherwise.
  double? computeScore({
    required List<QuestionnaireItem> items,
    required List<int?> values,
    required int scaleMin,
    required int scaleMax,
  }) {
    assert(
      items.length == values.length,
      'items and values must have equal length',
    );

    if (items.isEmpty) return null;

    final scaleRange = scaleMax - scaleMin;
    if (scaleRange <= 0) return null; // degenerate scale

    var sum = 0.0;
    var answeredCount = 0;

    for (var i = 0; i < items.length; i++) {
      final raw = values[i];
      if (raw == null) continue; // skipped — excluded from denominator

      final scored = items[i].isReversed
          ? (scaleMax + scaleMin - raw).toDouble()
          : raw.toDouble();
      sum += scored;
      answeredCount++;
    }

    if (answeredCount == 0) return null; // all items skipped

    final mean = sum / answeredCount;
    return ((mean - scaleMin) / scaleRange) * 100.0;
  }

  /// Compute using a simpler interface when items and values are already paired.
  ///
  /// [answers] — list of (isReversed, value) pairs. Value null = skipped.
  double? computeScoreFromPairs({
    required List<({bool isReversed, int? value})> answers,
    required int scaleMin,
    required int scaleMax,
  }) {
    if (answers.isEmpty) return null;

    final scaleRange = scaleMax - scaleMin;
    if (scaleRange <= 0) return null;

    var sum = 0.0;
    var answeredCount = 0;

    for (final answer in answers) {
      final raw = answer.value;
      if (raw == null) continue;

      final scored = answer.isReversed
          ? (scaleMax + scaleMin - raw).toDouble()
          : raw.toDouble();
      sum += scored;
      answeredCount++;
    }

    if (answeredCount == 0) return null;

    final mean = sum / answeredCount;
    return ((mean - scaleMin) / scaleRange) * 100.0;
  }
}
