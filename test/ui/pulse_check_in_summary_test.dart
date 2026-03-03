// ===========================================================================
// file: test/ui/pulse_check_in_summary_test.dart
// purpose: Widget tests for PulseCheckInSummary — compact check-in card.
//
// Tests that the card renders score, item scores, and the ADHD closing
// confirmation. PulseCheckInSummary is a pure StatelessWidget with no
// providers, so it can be tested directly.
//
// See: SPEC-20260302-ADHD Phase 1 Task 7.
// ===========================================================================

import 'package:drift/drift.dart' hide isNull, isNotNull;
import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/questionnaire_dao.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';
import 'package:agentic_journal/ui/widgets/pulse_check_in_summary.dart';

void main() {
  late AppDatabase db;
  late QuestionnaireDao dao;
  late SessionDao sessionDao;

  setUp(() {
    db = AppDatabase.forTesting(NativeDatabase.memory());
    dao = QuestionnaireDao(db);
    sessionDao = SessionDao(db);
  });

  tearDown(() async {
    await db.close();
  });

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  Future<(CheckInResponseWithAnswers, List<QuestionnaireItem>)> buildTestData({
    double? compositeScore,
    List<int?> values = const [8, 6, 3],
  }) async {
    await sessionDao.createSession('s1', DateTime.utc(2026, 3, 3), 'UTC');

    final templateId = await dao.insertTemplate(
      const QuestionnaireTemplatesCompanion(
        name: Value('Test Template'),
        scaleMin: Value(1),
        scaleMax: Value(10),
      ),
    );

    final itemIds = <int>[];
    final questions = ['Mood', 'Energy', 'Anxiety'];
    for (var i = 0; i < questions.length; i++) {
      final id = await dao.insertItem(
        QuestionnaireItemsCompanion(
          templateId: Value(templateId),
          questionText: Value(questions[i]),
          sortOrder: Value(i),
          isReversed: Value(i == 2), // Anxiety is reversed
        ),
      );
      itemIds.add(id);
    }

    final items = await dao.getActiveItemsForTemplate(templateId);

    final answers = [
      for (var i = 0; i < itemIds.length; i++)
        CheckInAnswersCompanion(
          itemId: Value(itemIds[i]),
          value: Value(i < values.length ? values[i] : null),
        ),
    ];

    await dao.saveCheckInResponse(
      response: CheckInResponsesCompanion(
        sessionId: const Value('s1'),
        templateId: Value(templateId),
        completedAt: Value(DateTime.utc(2026, 3, 3)),
        compositeScore: Value(compositeScore),
        syncStatus: const Value('PENDING'),
      ),
      answers: answers,
    );

    final result = await dao.getResponseForSession('s1');
    return (result!, items);
  }

  Widget buildWidget(
    CheckInResponseWithAnswers responseWithAnswers,
    List<QuestionnaireItem> items,
  ) {
    return MaterialApp(
      home: Scaffold(
        body: PulseCheckInSummary(
          responseWithAnswers: responseWithAnswers,
          items: items,
        ),
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Tests
  // ---------------------------------------------------------------------------

  testWidgets('renders "Pulse Check-In" header', (tester) async {
    final (data, items) = await buildTestData(compositeScore: 68.5);
    await tester.pumpWidget(buildWidget(data, items));
    expect(find.text('Pulse Check-In'), findsOneWidget);
  });

  testWidgets('renders composite score when present', (tester) async {
    final (data, items) = await buildTestData(compositeScore: 68.5);
    await tester.pumpWidget(buildWidget(data, items));
    expect(find.text('69/100'), findsOneWidget); // toStringAsFixed(0)
  });

  testWidgets('does not render score label when compositeScore is null', (
    tester,
  ) async {
    final (data, items) = await buildTestData();
    await tester.pumpWidget(buildWidget(data, items));
    expect(find.textContaining('/100'), findsNothing);
  });

  testWidgets('renders question text for each item', (tester) async {
    final (data, items) = await buildTestData(compositeScore: 75.0);
    await tester.pumpWidget(buildWidget(data, items));
    expect(find.text('Mood'), findsOneWidget);
    expect(find.text('Energy'), findsOneWidget);
    expect(find.text('Anxiety'), findsOneWidget);
  });

  testWidgets('renders answer values for answered items', (tester) async {
    final (data, items) = await buildTestData(
      compositeScore: 75.0,
      values: [8, 6, 3],
    );
    await tester.pumpWidget(buildWidget(data, items));
    expect(find.text('8'), findsOneWidget);
    expect(find.text('6'), findsOneWidget);
    expect(find.text('3'), findsOneWidget);
  });

  testWidgets('renders dash for skipped items', (tester) async {
    final (data, items) = await buildTestData(
      compositeScore: null,
      values: [8, null, 3],
    );
    await tester.pumpWidget(buildWidget(data, items));
    expect(find.text('—'), findsOneWidget);
  });

  testWidgets('renders ADHD closing confirmation', (tester) async {
    final (data, items) = await buildTestData(compositeScore: 70.0);
    await tester.pumpWidget(buildWidget(data, items));
    expect(find.text("Saved. That's enough."), findsOneWidget);
  });

  testWidgets('renders without error when items list is empty', (tester) async {
    await sessionDao.createSession('s2', DateTime.utc(2026, 3, 3), 'UTC');
    final templateId = await dao.insertTemplate(
      const QuestionnaireTemplatesCompanion(
        name: Value('Empty'),
        scaleMin: Value(1),
        scaleMax: Value(10),
      ),
    );
    await dao.saveCheckInResponse(
      response: CheckInResponsesCompanion(
        sessionId: const Value('s2'),
        templateId: Value(templateId),
        completedAt: Value(DateTime.utc(2026, 3, 3)),
        syncStatus: const Value('PENDING'),
      ),
      answers: [],
    );
    final result = await dao.getResponseForSession('s2');
    await tester.pumpWidget(buildWidget(result!, []));
    expect(find.text('Pulse Check-In'), findsOneWidget);
    expect(find.text("Saved. That's enough."), findsOneWidget);
  });
}
