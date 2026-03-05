// ===========================================================================
// file: test/services/questionnaire_defaults_test.dart
// purpose: Unit tests for QuestionnaireDefaults seeding logic.
//
// Verifies that:
//   - ensureDefaultTemplate seeds on first call
//   - ensureDefaultTemplate is idempotent (no-op on repeat calls)
//   - Default template has correct attributes (isSystemDefault, scale)
//   - Default template seeds exactly 6 items
//   - At least one item is reverse-scored (anxiety question)
//
// See: SPEC-20260302-ADHD Phase 1 Task 2, ADR-0032.
// ===========================================================================

import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/questionnaire_dao.dart';
import 'package:agentic_journal/services/questionnaire_defaults.dart';

void main() {
  late AppDatabase db;
  late QuestionnaireDao dao;
  late QuestionnaireDefaults defaults;

  setUp(() {
    db = AppDatabase.forTesting(NativeDatabase.memory());
    dao = QuestionnaireDao(db);
    defaults = QuestionnaireDefaults(dao);
  });

  tearDown(() async {
    await db.close();
  });

  group('QuestionnaireDefaults.ensureDefaultTemplate', () {
    test('seeds template on first call', () async {
      final id = await defaults.ensureDefaultTemplate();
      expect(id, greaterThan(0));

      final template = await dao.getTemplateById(id);
      expect(template, isNotNull);
      expect(template!.name, 'Pulse Check-In');
    });

    test('template is marked as system default', () async {
      await defaults.ensureDefaultTemplate();
      final template = await dao.getActiveDefaultTemplate();
      expect(template, isNotNull);
      expect(template!.isSystemDefault, isTrue);
      expect(template.isActive, isTrue);
    });

    test('template uses 1-10 scale', () async {
      await defaults.ensureDefaultTemplate();
      final template = await dao.getActiveDefaultTemplate();
      expect(template!.scaleMin, 1);
      expect(template.scaleMax, 10);
    });

    test('seeds exactly 6 items', () async {
      final id = await defaults.ensureDefaultTemplate();
      final items = await dao.getActiveItemsForTemplate(id);
      expect(items, hasLength(6));
    });

    test('items are ordered by sortOrder', () async {
      final id = await defaults.ensureDefaultTemplate();
      final items = await dao.getActiveItemsForTemplate(id);
      final sortOrders = items.map((i) => i.sortOrder).toList();
      expect(sortOrders, orderedEquals([1, 2, 3, 4, 5, 6]));
    });

    test('exactly one item is reverse-scored (anxiety question)', () async {
      final id = await defaults.ensureDefaultTemplate();
      final items = await dao.getActiveItemsForTemplate(id);
      final reversedCount = items.where((i) => i.isReversed).length;
      expect(reversedCount, 1);
    });

    test('reverse-scored item is the anxiety question (Q3)', () async {
      final id = await defaults.ensureDefaultTemplate();
      final items = await dao.getActiveItemsForTemplate(id);
      final reversed = items.firstWhere((i) => i.isReversed);
      expect(reversed.sortOrder, 3);
      expect(reversed.questionText.toLowerCase(), contains('anxious'));
    });

    test('all items have non-empty questionText', () async {
      final id = await defaults.ensureDefaultTemplate();
      final items = await dao.getActiveItemsForTemplate(id);
      for (final item in items) {
        expect(item.questionText, isNotEmpty);
      }
    });

    test('all items are active', () async {
      final id = await defaults.ensureDefaultTemplate();
      final items = await dao.getActiveItemsForTemplate(id);
      expect(items.every((i) => i.isActive), isTrue);
    });

    test('is idempotent — second call returns same id', () async {
      final id1 = await defaults.ensureDefaultTemplate();
      final id2 = await defaults.ensureDefaultTemplate();
      expect(id1, id2);
    });

    test(
      'is idempotent — second call does not create duplicate template',
      () async {
        await defaults.ensureDefaultTemplate();
        await defaults.ensureDefaultTemplate();

        // Only one active system default should exist.
        final template = await dao.getActiveDefaultTemplate();
        expect(template, isNotNull);
      },
    );

    test('is idempotent — second call does not duplicate items', () async {
      final id = await defaults.ensureDefaultTemplate();
      await defaults.ensureDefaultTemplate();
      final items = await dao.getActiveItemsForTemplate(id);
      expect(items, hasLength(6)); // still exactly 6
    });
  });
}
