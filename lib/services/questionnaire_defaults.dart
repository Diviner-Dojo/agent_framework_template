// ===========================================================================
// file: lib/services/questionnaire_defaults.dart
// purpose: Seeds the default Pulse Check-In questionnaire template on first
//          launch or when the database has no active system default template.
//
// The default template uses 6 questions drawn from validated instruments:
//   - Circumplex valence/arousal (EMA standard)
//   - GAD-2 / PHQ-4 (anxiety, public domain)
//   - ADHD-specific focus item
//   - BEDS (emotion regulation)
//   - WHO-5 sleep item (CC BY-NC-SA 3.0 — see ADR-0032 §License Decision)
//
// Called once from the database provider on app startup. Safe to call
// multiple times — checks for existing system default before inserting.
//
// See: SPEC-20260302-ADHD Phase 1 Task 2, ADR-0032.
// ===========================================================================

import 'package:drift/drift.dart';

import '../database/app_database.dart';
import '../database/daos/questionnaire_dao.dart';

/// Seeds the default Pulse Check-In template if no system default exists.
///
/// Called at app startup. No-op if a system default template already exists.
/// The 6-item default template uses a 1-10 scale and takes ~60 seconds.
class QuestionnaireDefaults {
  final QuestionnaireDao _dao;

  QuestionnaireDefaults(this._dao);

  /// Ensure the default template is present in the database.
  ///
  /// Returns the id of the (existing or newly created) default template.
  Future<int> ensureDefaultTemplate() async {
    final existing = await _dao.getActiveDefaultTemplate();
    if (existing != null) return existing.id;

    return _seedDefaultTemplate();
  }

  Future<int> _seedDefaultTemplate() async {
    final templateId = await _dao.insertTemplate(
      const QuestionnaireTemplatesCompanion(
        name: Value('Pulse Check-In'),
        description: Value(
          '6 quick questions about your current mood, energy, and focus. '
          'Takes about 60 seconds.',
        ),
        isSystemDefault: Value(true),
        isActive: Value(true),
        scaleMin: Value(1),
        scaleMax: Value(10),
        sortOrder: Value(0),
        // Mixed instruments: EMA circumplex, GAD-2, ADHD-specific, BEDS,
        // WHO-5 sleep item. Coded 'custom' because no single instrument applies.
        // Individual items with copyrighted source are noted in questionnaire_defaults.dart.
        // WHO-5 item: licenseInfo records NC clause — see ADR-0032 §License Decision.
        instrumentCode: Value('custom'),
        version: Value('1.0.0'),
        licenseInfo: Value(
          'Mixed: EMA circumplex (public domain), GAD-2/PHQ-4 (public domain), '
          'ADHD-specific (custom), BEDS (research instrument), '
          'WHO-5 sleep item (CC BY-NC-SA 3.0 — Psychiatric Centre North Zealand). '
          'Review ADR-0032 before commercial distribution.',
        ),
      ),
    );

    await _seedItems(templateId);
    return templateId;
  }

  Future<void> _seedItems(int templateId) async {
    final items = [
      // 1. Mood (Circumplex valence)
      _item(
        templateId: templateId,
        sortOrder: 1,
        questionText: 'How would you rate your overall mood right now?',
        minLabel: 'Very low',
        maxLabel: 'Excellent',
        isReversed: false,
      ),
      // 2. Energy (Circumplex arousal / WHO-5 item 3)
      _item(
        templateId: templateId,
        sortOrder: 2,
        questionText: 'How is your energy level?',
        minLabel: 'Depleted',
        maxLabel: 'Fully energized',
        isReversed: false,
      ),
      // 3. Anxiety (GAD-2 / PHQ-4 — reverse-scored: high = negative)
      _item(
        templateId: templateId,
        sortOrder: 3,
        questionText: 'How anxious or worried do you feel?',
        minLabel: 'Not at all',
        maxLabel: 'Extremely',
        isReversed: true,
      ),
      // 4. Focus (ADHD-specific)
      _item(
        templateId: templateId,
        sortOrder: 4,
        questionText: 'How well can you focus right now?',
        minLabel: "Can't concentrate",
        maxLabel: 'Laser focused',
        isReversed: false,
      ),
      // 5. Emotion regulation (BEDS)
      _item(
        templateId: templateId,
        sortOrder: 5,
        questionText: 'How well are you managing your emotions?',
        minLabel: 'Overwhelmed',
        maxLabel: 'In control',
        isReversed: false,
      ),
      // 6. Sleep (WHO-5 item 4 — see ADR-0032 §License Decision)
      _item(
        templateId: templateId,
        sortOrder: 6,
        questionText: 'How well did you sleep last night?',
        minLabel: 'Terribly',
        maxLabel: 'Great',
        isReversed: false,
      ),
    ];

    for (final item in items) {
      await _dao.insertItem(item);
    }
  }

  QuestionnaireItemsCompanion _item({
    required int templateId,
    required int sortOrder,
    required String questionText,
    required String minLabel,
    required String maxLabel,
    required bool isReversed,
  }) {
    return QuestionnaireItemsCompanion(
      templateId: Value(templateId),
      sortOrder: Value(sortOrder),
      questionText: Value(questionText),
      minLabel: Value(minLabel),
      maxLabel: Value(maxLabel),
      isReversed: Value(isReversed),
      isActive: const Value(true),
    );
  }
}
