// ===========================================================================
// file: test/services/checkin_score_service_test.dart
// purpose: Unit tests for CheckInScoreService composite score formula.
//
// Covers all edge cases from SPEC-20260302-ADHD §Design Decisions and
// the acceptance criteria verification values.
// ===========================================================================

import 'package:flutter_test/flutter_test.dart';
import 'package:drift/drift.dart' hide isNull, isNotNull;
import 'package:drift/native.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/services/checkin_score_service.dart';

void main() {
  late AppDatabase db;
  late CheckInScoreService service;

  setUp(() {
    service = const CheckInScoreService();
    db = AppDatabase.forTesting(NativeDatabase.memory());
  });

  tearDown(() async {
    await db.close();
  });

  // ---------------------------------------------------------------------------
  // Helpers — build QuestionnaireItem rows inline
  // ---------------------------------------------------------------------------

  Future<QuestionnaireItem> makeItem({
    required bool isReversed,
    String questionText = 'Q',
  }) async {
    // Insert a template to satisfy FK.
    final templateId = await db
        .into(db.questionnaireTemplates)
        .insert(
          const QuestionnaireTemplatesCompanion(
            name: Value('T'),
            scaleMin: Value(1),
            scaleMax: Value(10),
          ),
        );
    final itemId = await db
        .into(db.questionnaireItems)
        .insert(
          QuestionnaireItemsCompanion(
            templateId: Value(templateId),
            questionText: Value(questionText),
            isReversed: Value(isReversed),
          ),
        );
    return (db.select(
      db.questionnaireItems,
    )..where((i) => i.id.equals(itemId))).getSingle();
  }

  // ---------------------------------------------------------------------------
  // Acceptance criteria from spec
  // ---------------------------------------------------------------------------

  group('acceptance criteria', () {
    test('[8,6,3,7,5,9] with Q3 reversed on 1-10 scale → 68.5', () async {
      final items = await Future.wait([
        makeItem(isReversed: false), // Q1
        makeItem(isReversed: false), // Q2
        makeItem(isReversed: true), // Q3 — anxiety, reversed
        makeItem(isReversed: false), // Q4
        makeItem(isReversed: false), // Q5
        makeItem(isReversed: false), // Q6
      ]);
      final values = [8, 6, 3, 7, 5, 9];
      // Q3 scored: 10 + 1 - 3 = 8. Mean = (8+6+8+7+5+9)/6 = 43/6 ≈ 7.167
      // Score = (7.167 - 1) / 9 * 100 ≈ 68.5
      final score = service.computeScore(
        items: items,
        values: values,
        scaleMin: 1,
        scaleMax: 10,
      );
      expect(score, closeTo(68.5, 0.2));
    });

    test('all answered 1 → 0.0', () async {
      final items = await Future.wait([
        makeItem(isReversed: false),
        makeItem(isReversed: false),
      ]);
      final score = service.computeScore(
        items: items,
        values: [1, 1],
        scaleMin: 1,
        scaleMax: 10,
      );
      expect(score, closeTo(0.0, 0.001));
    });

    test('all answered 10 → 100.0', () async {
      final items = await Future.wait([
        makeItem(isReversed: false),
        makeItem(isReversed: false),
      ]);
      final score = service.computeScore(
        items: items,
        values: [10, 10],
        scaleMin: 1,
        scaleMax: 10,
      );
      expect(score, closeTo(100.0, 0.001));
    });

    test('empty items list → null', () {
      final score = service.computeScore(
        items: [],
        values: [],
        scaleMin: 1,
        scaleMax: 10,
      );
      expect(score, isNull);
    });

    test('all items skipped (all null values) → null', () async {
      final items = await Future.wait([
        makeItem(isReversed: false),
        makeItem(isReversed: false),
      ]);
      final score = service.computeScore(
        items: items,
        values: [null, null],
        scaleMin: 1,
        scaleMax: 10,
      );
      expect(score, isNull);
    });
  });

  // ---------------------------------------------------------------------------
  // Edge cases
  // ---------------------------------------------------------------------------

  group('edge cases', () {
    test('single answered item — formula holds', () async {
      final items = [await makeItem(isReversed: false)];
      // value=5, scale 1-10: (5 - 1) / 9 * 100 ≈ 44.4
      final score = service.computeScore(
        items: items,
        values: [5],
        scaleMin: 1,
        scaleMax: 10,
      );
      expect(score, closeTo(44.4, 0.2));
    });

    test('partial completion: denominator uses answered items only', () async {
      final items = await Future.wait([
        makeItem(isReversed: false), // answered
        makeItem(isReversed: false), // skipped
        makeItem(isReversed: false), // answered
      ]);
      // Only items 0 and 2 answered with [10, 10].
      // Mean of answered = 10. Score = (10-1)/9*100 = 100.
      final score = service.computeScore(
        items: items,
        values: [10, null, 10],
        scaleMin: 1,
        scaleMax: 10,
      );
      expect(score, closeTo(100.0, 0.001));
    });

    test('degenerate scale (min == max) → null', () async {
      final items = [await makeItem(isReversed: false)];
      final score = service.computeScore(
        items: items,
        values: [5],
        scaleMin: 5,
        scaleMax: 5,
      );
      expect(score, isNull);
    });

    test(
      'reverse scoring: scaleMax + scaleMin - rawValue (not +1 shortcut)',
      () async {
        // On 0-10 scale: reversed value of 3 = 10 + 0 - 3 = 7.
        final items = [await makeItem(isReversed: true)];
        final score = service.computeScore(
          items: items,
          values: [3],
          scaleMin: 0,
          scaleMax: 10,
        );
        // Scored = 7. (7 - 0) / 10 * 100 = 70.
        expect(score, closeTo(70.0, 0.001));
      },
    );

    test('computeScoreFromPairs matches computeScore', () async {
      final items = await Future.wait([
        makeItem(isReversed: false),
        makeItem(isReversed: true),
      ]);
      const values = [8, 3];

      final score1 = service.computeScore(
        items: items,
        values: values,
        scaleMin: 1,
        scaleMax: 10,
      );
      final score2 = service.computeScoreFromPairs(
        answers: [(isReversed: false, value: 8), (isReversed: true, value: 3)],
        scaleMin: 1,
        scaleMax: 10,
      );
      expect(score1, closeTo(score2!, 0.001));
    });
  });
}
