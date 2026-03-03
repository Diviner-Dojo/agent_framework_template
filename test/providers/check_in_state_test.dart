// ===========================================================================
// file: test/providers/check_in_state_test.dart
// purpose: Unit tests for CheckInState — copyWith, computed getters.
//
// CheckInState is a pure immutable data class, testable without drift or
// Riverpod.
// ===========================================================================

import 'package:drift/drift.dart' hide isNull, isNotNull;
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/providers/questionnaire_providers.dart';

void main() {
  // ---------------------------------------------------------------------------
  // Helpers — build QuestionnaireItem rows using in-memory DB
  // ---------------------------------------------------------------------------

  late AppDatabase db;

  setUp(() {
    db = AppDatabase.forTesting(NativeDatabase.memory());
  });

  tearDown(() async {
    await db.close();
  });

  Future<QuestionnaireItem> makeItem({String text = 'Q'}) async {
    final tid = await db
        .into(db.questionnaireTemplates)
        .insert(
          const QuestionnaireTemplatesCompanion(
            name: Value('T'),
            scaleMin: Value(1),
            scaleMax: Value(10),
          ),
        );
    final iid = await db
        .into(db.questionnaireItems)
        .insert(
          QuestionnaireItemsCompanion(
            templateId: Value(tid),
            questionText: Value(text),
            isReversed: const Value(false),
          ),
        );
    return (db.select(
      db.questionnaireItems,
    )..where((i) => i.id.equals(iid))).getSingle();
  }

  // ---------------------------------------------------------------------------
  // CheckInState defaults
  // ---------------------------------------------------------------------------

  group('CheckInState — defaults', () {
    test('initial state is inactive with empty items', () {
      const state = CheckInState();
      expect(state.isActive, isFalse);
      expect(state.items, isEmpty);
      expect(state.answers, isEmpty);
      expect(state.currentStepIndex, 0);
      expect(state.isSaved, isFalse);
      expect(state.compositeScore, isNull);
      expect(state.lastParseError, isNull);
    });
  });

  // ---------------------------------------------------------------------------
  // copyWith
  // ---------------------------------------------------------------------------

  group('CheckInState.copyWith', () {
    test('copies without change when no arguments supplied', () async {
      final item = await makeItem();
      final state = CheckInState(
        items: [item],
        currentStepIndex: 1,
        answers: [7],
        isActive: true,
        isSaved: false,
        compositeScore: 72.0,
        lastParseError: 'oops',
      );
      final copy = state.copyWith();
      expect(copy.items, state.items);
      expect(copy.currentStepIndex, 1);
      expect(copy.answers, [7]);
      expect(copy.isActive, isTrue);
      expect(copy.isSaved, isFalse);
      expect(copy.compositeScore, 72.0);
      expect(copy.lastParseError, 'oops');
    });

    test('updates currentStepIndex', () async {
      final item = await makeItem();
      final state = CheckInState(items: [item], currentStepIndex: 0);
      final updated = state.copyWith(currentStepIndex: 1);
      expect(updated.currentStepIndex, 1);
    });

    test('updates isActive', () {
      const state = CheckInState(isActive: false);
      final updated = state.copyWith(isActive: true);
      expect(updated.isActive, isTrue);
    });

    test('updates isSaved', () {
      const state = CheckInState(isSaved: false);
      final updated = state.copyWith(isSaved: true);
      expect(updated.isSaved, isTrue);
    });

    test('clears compositeScore with null-returning closure', () {
      const state = CheckInState(compositeScore: 80.0);
      final updated = state.copyWith(compositeScore: () => null);
      expect(updated.compositeScore, isNull);
    });

    test('sets compositeScore with value-returning closure', () {
      const state = CheckInState();
      final updated = state.copyWith(compositeScore: () => 65.0);
      expect(updated.compositeScore, closeTo(65.0, 0.001));
    });

    test('clears lastParseError with null-returning closure', () {
      const state = CheckInState(lastParseError: 'parse error');
      final updated = state.copyWith(lastParseError: () => null);
      expect(updated.lastParseError, isNull);
    });

    test('sets lastParseError with value-returning closure', () {
      const state = CheckInState();
      final updated = state.copyWith(lastParseError: () => 'bad input');
      expect(updated.lastParseError, 'bad input');
    });
  });

  // ---------------------------------------------------------------------------
  // isComplete getter
  // ---------------------------------------------------------------------------

  group('CheckInState.isComplete', () {
    test('false when not active', () async {
      final item = await makeItem();
      final state = CheckInState(
        items: [item],
        currentStepIndex: 1,
        isActive: false,
      );
      expect(state.isComplete, isFalse);
    });

    test('false when active but not at summary step', () async {
      final item = await makeItem();
      final state = CheckInState(
        items: [item],
        currentStepIndex: 0,
        isActive: true,
      );
      expect(state.isComplete, isFalse);
    });

    test('true when active and currentStepIndex == items.length', () async {
      final item = await makeItem();
      final state = CheckInState(
        items: [item],
        currentStepIndex: 1, // == items.length
        isActive: true,
      );
      expect(state.isComplete, isTrue);
    });

    test('true when active and currentStepIndex > items.length', () async {
      final item = await makeItem();
      final state = CheckInState(
        items: [item],
        currentStepIndex: 5,
        isActive: true,
      );
      expect(state.isComplete, isTrue);
    });
  });

  // ---------------------------------------------------------------------------
  // currentItem getter
  // ---------------------------------------------------------------------------

  group('CheckInState.currentItem', () {
    test('returns null for empty items', () {
      const state = CheckInState();
      expect(state.currentItem, isNull);
    });

    test('returns first item when currentStepIndex is 0', () async {
      final item = await makeItem(text: 'First');
      final state = CheckInState(items: [item], currentStepIndex: 0);
      expect(state.currentItem!.questionText, 'First');
    });

    test(
      'returns null when currentStepIndex == items.length (summary step)',
      () async {
        final item = await makeItem();
        final state = CheckInState(items: [item], currentStepIndex: 1);
        expect(state.currentItem, isNull);
      },
    );
  });

  // ---------------------------------------------------------------------------
  // progressLabel getter
  // ---------------------------------------------------------------------------

  group('CheckInState.progressLabel', () {
    test('shows "1 of N" for first step', () async {
      final item = await makeItem();
      final state = CheckInState(items: [item, item], currentStepIndex: 0);
      expect(state.progressLabel, '1 of 2');
    });

    test('shows "3 of 6" for third step of six', () async {
      final items = List.generate(6, (_) async => makeItem());
      final resolved = await Future.wait(items);
      final state = CheckInState(items: resolved, currentStepIndex: 2);
      expect(state.progressLabel, '3 of 6');
    });
  });
}
