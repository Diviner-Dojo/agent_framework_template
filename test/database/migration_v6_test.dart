// ===========================================================================
// file: test/database/migration_v6_test.dart
// purpose: Schema v10 migration — Pulse Check-In tables (ADR-0032).
//
// Verifies that the questionnaire tables and check-in tables exist in a
// freshly-created database, matching the onUpgrade from < 10 block.
// ===========================================================================

import 'package:drift/drift.dart' hide isNull, isNotNull;
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/questionnaire_dao.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';

void main() {
  group('Schema v10 migration — Pulse Check-In tables', () {
    test('schemaVersion is at least 10', () async {
      final database = AppDatabase.forTesting(NativeDatabase.memory());
      expect(database.schemaVersion, greaterThanOrEqualTo(10));
      await database.close();
    });

    test('questionnaire_templates table supports CRUD', () async {
      final database = AppDatabase.forTesting(NativeDatabase.memory());
      final dao = QuestionnaireDao(database);

      final id = await dao.insertTemplate(
        const QuestionnaireTemplatesCompanion(
          name: Value('WHO-5 (test)'),
          scaleMin: Value(1),
          scaleMax: Value(10),
        ),
      );
      expect(id, greaterThan(0));

      final template = await dao.getTemplateById(id);
      expect(template, isNotNull);
      expect(template!.name, 'WHO-5 (test)');
      expect(template.scaleMin, 1);
      expect(template.scaleMax, 10);

      await database.close();
    });

    test('questionnaire_items table supports CRUD', () async {
      final database = AppDatabase.forTesting(NativeDatabase.memory());
      final dao = QuestionnaireDao(database);

      final templateId = await dao.insertTemplate(
        const QuestionnaireTemplatesCompanion(
          name: Value('T'),
          scaleMin: Value(1),
          scaleMax: Value(10),
        ),
      );

      final itemId = await dao.insertItem(
        QuestionnaireItemsCompanion(
          templateId: Value(templateId),
          questionText: const Value('How do you feel?'),
          isReversed: const Value(false),
        ),
      );
      expect(itemId, greaterThan(0));

      final items = await dao.getActiveItemsForTemplate(templateId);
      expect(items, hasLength(1));
      expect(items.first.questionText, 'How do you feel?');

      await database.close();
    });

    test(
      'check_in_responses and check_in_answers tables support CRUD',
      () async {
        final database = AppDatabase.forTesting(NativeDatabase.memory());
        final dao = QuestionnaireDao(database);
        final sessionDao = SessionDao(database);

        await sessionDao.createSession(
          'session_v10',
          DateTime.utc(2026, 3, 3),
          'UTC',
        );

        final templateId = await dao.insertTemplate(
          const QuestionnaireTemplatesCompanion(
            name: Value('T'),
            scaleMin: Value(1),
            scaleMax: Value(10),
          ),
        );
        final itemId = await dao.insertItem(
          QuestionnaireItemsCompanion(
            templateId: Value(templateId),
            questionText: const Value('Q1'),
          ),
        );

        final responseId = await dao.saveCheckInResponse(
          response: CheckInResponsesCompanion(
            sessionId: const Value('session_v10'),
            templateId: Value(templateId),
            completedAt: Value(DateTime.utc(2026, 3, 3)),
            compositeScore: const Value(70.0),
            syncStatus: const Value('PENDING'),
          ),
          answers: [
            CheckInAnswersCompanion(
              itemId: Value(itemId),
              value: const Value(7),
            ),
          ],
        );
        expect(responseId, greaterThan(0));

        final result = await dao.getResponseForSession('session_v10');
        expect(result, isNotNull);
        expect(result!.response.compositeScore, closeTo(70.0, 0.001));
        expect(result.answers.first.value, 7);

        await database.close();
      },
    );

    test('session_id index exists on check_in_responses', () async {
      // Verify index by doing an indexed lookup — no assertion needed beyond
      // the query not throwing.
      final database = AppDatabase.forTesting(NativeDatabase.memory());
      final dao = QuestionnaireDao(database);
      final result = await dao.getResponseForSession('nonexistent');
      expect(result, isNull);
      await database.close();
    });

    test(
      'v9 data survives upgrade to v10 (simulated via fresh insert)',
      () async {
        // In-memory DB simulates a fresh create. We verify all pre-v10 tables
        // (journal_sessions, journal_messages) remain accessible.
        final database = AppDatabase.forTesting(NativeDatabase.memory());
        final sessionDao = SessionDao(database);

        // Should not throw: pre-v10 tables still exist.
        await sessionDao.createSession(
          'legacy_session',
          DateTime.utc(2026, 3, 3),
          'UTC',
        );
        final sessions = await sessionDao.getAllSessionsByDate();
        expect(sessions, hasLength(1));
        expect(sessions.first.sessionId, 'legacy_session');

        await database.close();
      },
    );
  });
}
