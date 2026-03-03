// ===========================================================================
// file: test/database/questionnaire_dao_test.dart
// purpose: Unit tests for QuestionnaireDao — CRUD, system-default guard,
//          atomic saveCheckInResponse, N+1-free getAllResponsesForSession.
//
// All tests use an in-memory drift database (AppDatabase.forTesting).
// See: SPEC-20260302-ADHD Phase 1 Task 1, ADR-0032.
// ===========================================================================

import 'package:drift/drift.dart' hide isNull, isNotNull;
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/questionnaire_dao.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';

void main() {
  late AppDatabase db;
  late QuestionnaireDao dao;
  late SessionDao sessionDao;

  setUp(() async {
    db = AppDatabase.forTesting(NativeDatabase.memory());
    dao = QuestionnaireDao(db);
    sessionDao = SessionDao(db);
    await sessionDao.createSession('session1', DateTime.utc(2026, 3, 3), 'UTC');
  });

  tearDown(() async {
    await db.close();
  });

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  QuestionnaireTemplatesCompanion makeTemplate({
    String name = 'Test Template',
    bool isSystemDefault = false,
    int scaleMin = 1,
    int scaleMax = 10,
  }) {
    return QuestionnaireTemplatesCompanion(
      name: Value(name),
      isSystemDefault: Value(isSystemDefault),
      scaleMin: Value(scaleMin),
      scaleMax: Value(scaleMax),
    );
  }

  QuestionnaireItemsCompanion makeItem({
    required int templateId,
    String questionText = 'How are you?',
    int sortOrder = 0,
    bool isReversed = false,
    bool isActive = true,
  }) {
    return QuestionnaireItemsCompanion(
      templateId: Value(templateId),
      questionText: Value(questionText),
      sortOrder: Value(sortOrder),
      isReversed: Value(isReversed),
      isActive: Value(isActive),
    );
  }

  // ---------------------------------------------------------------------------
  // QuestionnaireTemplates
  // ---------------------------------------------------------------------------

  group('QuestionnaireTemplates', () {
    test('insertTemplate returns auto-generated id', () async {
      final id = await dao.insertTemplate(makeTemplate());
      expect(id, greaterThan(0));
    });

    test('getTemplateById returns inserted template', () async {
      final id = await dao.insertTemplate(makeTemplate(name: 'My Template'));
      final template = await dao.getTemplateById(id);
      expect(template, isNotNull);
      expect(template!.name, 'My Template');
    });

    test('getTemplateById returns null for missing id', () async {
      final template = await dao.getTemplateById(99999);
      expect(template, isNull);
    });

    test('getActiveDefaultTemplate returns system default', () async {
      await dao.insertTemplate(makeTemplate(isSystemDefault: true));
      final template = await dao.getActiveDefaultTemplate();
      expect(template, isNotNull);
      expect(template!.isSystemDefault, isTrue);
      expect(template.isActive, isTrue);
    });

    test('getActiveDefaultTemplate returns null when none exists', () async {
      final template = await dao.getActiveDefaultTemplate();
      expect(template, isNull);
    });

    test('deleteTemplate is no-op for system defaults', () async {
      final id = await dao.insertTemplate(makeTemplate(isSystemDefault: true));
      final deleted = await dao.deleteTemplate(id);
      expect(deleted, 0); // must not delete
      final template = await dao.getTemplateById(id);
      expect(template, isNotNull);
    });

    test('deleteTemplate removes non-system templates', () async {
      final id = await dao.insertTemplate(makeTemplate(isSystemDefault: false));
      final deleted = await dao.deleteTemplate(id);
      expect(deleted, 1);
      final template = await dao.getTemplateById(id);
      expect(template, isNull);
    });

    test('updateTemplate updates fields', () async {
      final id = await dao.insertTemplate(makeTemplate(name: 'Old Name'));
      await dao.updateTemplate(
        id,
        const QuestionnaireTemplatesCompanion(name: Value('New Name')),
      );
      final template = await dao.getTemplateById(id);
      expect(template!.name, 'New Name');
    });
  });

  // ---------------------------------------------------------------------------
  // QuestionnaireItems
  // ---------------------------------------------------------------------------

  group('QuestionnaireItems', () {
    late int templateId;

    setUp(() async {
      templateId = await dao.insertTemplate(makeTemplate());
    });

    test('insertItem returns auto-generated id', () async {
      final id = await dao.insertItem(makeItem(templateId: templateId));
      expect(id, greaterThan(0));
    });

    test(
      'getActiveItemsForTemplate returns items ordered by sortOrder',
      () async {
        await dao.insertItem(
          makeItem(templateId: templateId, questionText: 'Q2', sortOrder: 1),
        );
        await dao.insertItem(
          makeItem(templateId: templateId, questionText: 'Q1', sortOrder: 0),
        );
        await dao.insertItem(
          makeItem(templateId: templateId, questionText: 'Q3', sortOrder: 2),
        );

        final items = await dao.getActiveItemsForTemplate(templateId);
        expect(items.map((i) => i.questionText).toList(), ['Q1', 'Q2', 'Q3']);
      },
    );

    test('getActiveItemsForTemplate excludes inactive items', () async {
      await dao.insertItem(
        makeItem(
          templateId: templateId,
          questionText: 'Active',
          isActive: true,
        ),
      );
      await dao.insertItem(
        makeItem(
          templateId: templateId,
          questionText: 'Inactive',
          isActive: false,
        ),
      );

      final items = await dao.getActiveItemsForTemplate(templateId);
      expect(items, hasLength(1));
      expect(items.first.questionText, 'Active');
    });

    test('updateItem persists isActive change', () async {
      final id = await dao.insertItem(
        makeItem(templateId: templateId, isActive: true),
      );
      await dao.updateItem(
        id,
        const QuestionnaireItemsCompanion(isActive: Value(false)),
      );
      final items = await dao.getActiveItemsForTemplate(templateId);
      expect(items, isEmpty);
    });

    test('deleteItem removes the item', () async {
      final id = await dao.insertItem(makeItem(templateId: templateId));
      await dao.deleteItem(id);
      final items = await dao.getActiveItemsForTemplate(templateId);
      expect(items, isEmpty);
    });
  });

  // ---------------------------------------------------------------------------
  // saveCheckInResponse — atomic transaction
  // ---------------------------------------------------------------------------

  group('saveCheckInResponse', () {
    late int templateId;
    late int itemId;

    setUp(() async {
      templateId = await dao.insertTemplate(makeTemplate());
      itemId = await dao.insertItem(makeItem(templateId: templateId));
    });

    test('inserts response and answers atomically', () async {
      final responseId = await dao.saveCheckInResponse(
        response: CheckInResponsesCompanion(
          sessionId: const Value('session1'),
          templateId: Value(templateId),
          completedAt: Value(DateTime.utc(2026, 3, 3)),
          compositeScore: const Value(75.0),
          syncStatus: const Value('PENDING'),
        ),
        answers: [
          CheckInAnswersCompanion(itemId: Value(itemId), value: const Value(8)),
        ],
      );
      expect(responseId, greaterThan(0));

      final result = await dao.getResponseForSession('session1');
      expect(result, isNotNull);
      expect(result!.response.compositeScore, 75.0);
      expect(result.answers, hasLength(1));
      expect(result.answers.first.value, 8);
    });

    test('saves skipped item as null value', () async {
      await dao.saveCheckInResponse(
        response: CheckInResponsesCompanion(
          sessionId: const Value('session1'),
          templateId: Value(templateId),
          completedAt: Value(DateTime.utc(2026, 3, 3)),
          syncStatus: const Value('PENDING'),
        ),
        answers: [
          CheckInAnswersCompanion(
            itemId: Value(itemId),
            value: const Value(null),
          ),
        ],
      );

      final result = await dao.getResponseForSession('session1');
      expect(result!.answers.first.value, isNull);
    });

    test('getResponseForSession returns null for unknown session', () async {
      final result = await dao.getResponseForSession('unknown_session');
      expect(result, isNull);
    });
  });

  // ---------------------------------------------------------------------------
  // getAllResponsesForSession — N+1-free IN-clause query
  // ---------------------------------------------------------------------------

  group('getAllResponsesForSession', () {
    late int templateId;
    late int itemId;

    setUp(() async {
      templateId = await dao.insertTemplate(makeTemplate());
      itemId = await dao.insertItem(makeItem(templateId: templateId));
    });

    test('returns multiple responses for same session', () async {
      for (var i = 1; i <= 3; i++) {
        await dao.saveCheckInResponse(
          response: CheckInResponsesCompanion(
            sessionId: const Value('session1'),
            templateId: Value(templateId),
            completedAt: Value(DateTime.utc(2026, 3, i)),
            syncStatus: const Value('PENDING'),
          ),
          answers: [
            CheckInAnswersCompanion(itemId: Value(itemId), value: Value(i * 2)),
          ],
        );
      }

      final results = await dao.getAllResponsesForSession('session1');
      expect(results, hasLength(3));
      // Verify answers are correctly associated.
      expect(results.every((r) => r.answers.isNotEmpty), isTrue);
    });

    test('returns empty list for unknown session', () async {
      final results = await dao.getAllResponsesForSession('no_such_session');
      expect(results, isEmpty);
    });
  });
}
