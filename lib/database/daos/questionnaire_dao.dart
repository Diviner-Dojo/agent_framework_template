// ===========================================================================
// file: lib/database/daos/questionnaire_dao.dart
// purpose: Data Access Object for Pulse Check-In tables (ADR-0032).
//
// Covers four tables introduced in ADHD Roadmap Phase 1:
//   QuestionnaireTemplates — instrument definitions
//   QuestionnaireItems     — per-template question rows
//   CheckInResponses       — completed check-in sessions
//   CheckInAnswers         — per-item answers within a response
//
// Pattern: Constructor-injected DAO (same as TaskDao, CalendarEventDao).
// System defaults (isSystemDefault=true) cannot be deleted — deleteTemplate()
// is a no-op for system templates.
//
// See: ADR-0032 (Pulse Check-In schema), SPEC-20260302-ADHD Phase 1 Task 1.
// ===========================================================================

import 'package:drift/drift.dart';

import '../app_database.dart';

/// Typed constants for check-in sync status.
abstract final class CheckInSyncStatus {
  static const pending = 'PENDING';
  static const synced = 'SYNCED';
  static const failed = 'FAILED';
}

/// Data Access Object for all four Pulse Check-In tables.
class QuestionnaireDao {
  final AppDatabase _db;

  /// Create a QuestionnaireDao with the given database.
  QuestionnaireDao(this._db);

  // ---------------------------------------------------------------------------
  // QuestionnaireTemplates
  // ---------------------------------------------------------------------------

  /// Insert a new questionnaire template. Returns the auto-generated id.
  Future<int> insertTemplate(QuestionnaireTemplatesCompanion template) {
    return _db.into(_db.questionnaireTemplates).insert(template);
  }

  /// Get a template by id. Returns null if not found.
  Future<QuestionnaireTemplate?> getTemplateById(int id) {
    return (_db.select(
      _db.questionnaireTemplates,
    )..where((t) => t.id.equals(id))).getSingleOrNull();
  }

  /// Get the active system-default template (isSystemDefault=true, isActive=true).
  ///
  /// Returns null only if no default template has been seeded yet. Under normal
  /// operation this always returns a non-null value after first launch.
  Future<QuestionnaireTemplate?> getActiveDefaultTemplate() {
    return (_db.select(_db.questionnaireTemplates)
          ..where(
            (t) => t.isSystemDefault.equals(true) & t.isActive.equals(true),
          )
          ..limit(1))
        .getSingleOrNull();
  }

  /// Watch all active templates ordered by sortOrder (for settings screen).
  Stream<List<QuestionnaireTemplate>> watchActiveTemplates() {
    return (_db.select(_db.questionnaireTemplates)
          ..where((t) => t.isActive.equals(true))
          ..orderBy([(t) => OrderingTerm.asc(t.sortOrder)]))
        .watch();
  }

  /// Watch the active system-default template for real-time scale config.
  ///
  /// Emits null only before [QuestionnaireDefaults.ensureDefaultTemplate] runs.
  /// Used by [activeDefaultTemplateProvider] to drive the settings scale toggle.
  Stream<QuestionnaireTemplate?> watchDefaultTemplate() {
    return (_db.select(_db.questionnaireTemplates)
          ..where(
            (t) => t.isSystemDefault.equals(true) & t.isActive.equals(true),
          )
          ..limit(1))
        .watchSingleOrNull();
  }

  /// Update an existing template.
  Future<int> updateTemplate(
    int id,
    QuestionnaireTemplatesCompanion companion,
  ) {
    return (_db.update(
      _db.questionnaireTemplates,
    )..where((t) => t.id.equals(id))).write(companion);
  }

  /// Delete a template by id.
  ///
  /// No-op for system defaults ([isSystemDefault] = true) — returns 0 without
  /// deleting. Use [updateTemplate] with [isActive] = false to deactivate.
  Future<int> deleteTemplate(int id) async {
    final template = await getTemplateById(id);
    if (template == null || template.isSystemDefault) return 0;
    return (_db.delete(
      _db.questionnaireTemplates,
    )..where((t) => t.id.equals(id))).go();
  }

  // ---------------------------------------------------------------------------
  // QuestionnaireItems
  // ---------------------------------------------------------------------------

  /// Insert a questionnaire item. Returns the auto-generated id.
  Future<int> insertItem(QuestionnaireItemsCompanion item) {
    return _db.into(_db.questionnaireItems).insert(item);
  }

  /// Get all active items for a template, ordered by sortOrder.
  Future<List<QuestionnaireItem>> getActiveItemsForTemplate(int templateId) {
    return (_db.select(_db.questionnaireItems)
          ..where(
            (i) => i.templateId.equals(templateId) & i.isActive.equals(true),
          )
          ..orderBy([(i) => OrderingTerm.asc(i.sortOrder)]))
        .get();
  }

  /// Get all items for a template (including inactive), ordered by sortOrder.
  ///
  /// Use this in historical views (e.g., check-in history dashboard) where
  /// deactivated items must still display their question text against old
  /// answers. Use [getActiveItemsForTemplate] only for "what to answer today".
  Future<List<QuestionnaireItem>> getAllItemsForTemplate(int templateId) {
    return (_db.select(_db.questionnaireItems)
          ..where((i) => i.templateId.equals(templateId))
          ..orderBy([(i) => OrderingTerm.asc(i.sortOrder)]))
        .get();
  }

  /// Watch all items for a template (including inactive), ordered by sortOrder.
  Stream<List<QuestionnaireItem>> watchItemsForTemplate(int templateId) {
    return (_db.select(_db.questionnaireItems)
          ..where((i) => i.templateId.equals(templateId))
          ..orderBy([(i) => OrderingTerm.asc(i.sortOrder)]))
        .watch();
  }

  /// Update a questionnaire item.
  Future<int> updateItem(int id, QuestionnaireItemsCompanion companion) {
    return (_db.update(
      _db.questionnaireItems,
    )..where((i) => i.id.equals(id))).write(companion);
  }

  /// Delete a questionnaire item.
  ///
  /// Caller is responsible for not deleting items that have existing
  /// CheckInAnswers (historical data would become orphaned). Prefer
  /// deactivating via [updateItem] with [isActive] = false.
  Future<int> deleteItem(int id) {
    return (_db.delete(
      _db.questionnaireItems,
    )..where((i) => i.id.equals(id))).go();
  }

  // ---------------------------------------------------------------------------
  // CheckInResponses + CheckInAnswers (atomic save)
  // ---------------------------------------------------------------------------

  /// Save a complete check-in response with all its answers atomically.
  ///
  /// Inserts the [CheckInResponsesCompanion] first, then inserts each answer
  /// in [answers] with the returned response id. Returns the new response id.
  ///
  /// Callers must pass all answered items (nulls included for skipped items).
  /// The [compositeScore] on the companion must be pre-computed by
  /// [CheckInScoreService.computeScore] before calling this method.
  Future<int> saveCheckInResponse({
    required CheckInResponsesCompanion response,
    required List<CheckInAnswersCompanion> answers,
  }) async {
    return _db.transaction(() async {
      final responseId = await _db.into(_db.checkInResponses).insert(response);
      for (final answer in answers) {
        await _db
            .into(_db.checkInAnswers)
            .insert(answer.copyWith(responseId: Value(responseId)));
      }
      return responseId;
    });
  }

  /// Get the most recent check-in response for a session, with answers.
  ///
  /// Returns null if no check-in was completed for the given [sessionId].
  Future<CheckInResponseWithAnswers?> getResponseForSession(
    String sessionId,
  ) async {
    final response =
        await (_db.select(_db.checkInResponses)
              ..where((r) => r.sessionId.equals(sessionId))
              ..orderBy([(r) => OrderingTerm.desc(r.completedAt)])
              ..limit(1))
            .getSingleOrNull();
    if (response == null) return null;

    final answers = await (_db.select(
      _db.checkInAnswers,
    )..where((a) => a.responseId.equals(response.id))).get();
    return CheckInResponseWithAnswers(response: response, answers: answers);
  }

  /// Get all responses for a session (may be multiple if session was resumed).
  ///
  /// Uses a single IN-clause query for answers to avoid N+1 round-trips
  /// (performance-analyst checkpoint finding — trend view grows linearly).
  Future<List<CheckInResponseWithAnswers>> getAllResponsesForSession(
    String sessionId,
  ) async {
    final responses =
        await (_db.select(_db.checkInResponses)
              ..where((r) => r.sessionId.equals(sessionId))
              ..orderBy([(r) => OrderingTerm.asc(r.completedAt)]))
            .get();

    if (responses.isEmpty) return [];

    // Single IN-clause query — idx_checkin_answers_response_id serves this.
    final ids = responses.map((r) => r.id).toList();
    final allAnswers = await (_db.select(
      _db.checkInAnswers,
    )..where((a) => a.responseId.isIn(ids))).get();

    final answersByResponseId = <int, List<CheckInAnswer>>{};
    for (final a in allAnswers) {
      answersByResponseId.putIfAbsent(a.responseId, () => []).add(a);
    }

    return responses
        .map(
          (r) => CheckInResponseWithAnswers(
            response: r,
            answers: answersByResponseId[r.id] ?? [],
          ),
        )
        .toList();
  }

  /// Watch all responses across all sessions (for trend view).
  Stream<List<CheckInResponse>> watchAllResponses() {
    return (_db.select(
      _db.checkInResponses,
    )..orderBy([(r) => OrderingTerm.desc(r.completedAt)])).watch();
  }

  /// Watch all responses with their answers (for the history dashboard).
  ///
  /// Emits whenever any response or answer row changes. Uses a single
  /// IN-clause query for answers to avoid N+1 round-trips.
  Stream<List<CheckInResponseWithAnswers>> watchAllResponsesWithAnswers() {
    return watchAllResponses().asyncMap((responses) async {
      if (responses.isEmpty) return [];
      final ids = responses.map((r) => r.id).toList();
      final allAnswers = await (_db.select(
        _db.checkInAnswers,
      )..where((a) => a.responseId.isIn(ids))).get();

      final answersByResponseId = <int, List<CheckInAnswer>>{};
      for (final a in allAnswers) {
        answersByResponseId.putIfAbsent(a.responseId, () => []).add(a);
      }

      return responses
          .map(
            (r) => CheckInResponseWithAnswers(
              response: r,
              answers: answersByResponseId[r.id] ?? [],
            ),
          )
          .toList();
    });
  }
}

/// A [CheckInResponse] row bundled with its [CheckInAnswer] rows.
///
/// Returned by [QuestionnaireDao.getResponseForSession] to avoid separate
/// queries at the caller site.
class CheckInResponseWithAnswers {
  final CheckInResponse response;
  final List<CheckInAnswer> answers;

  const CheckInResponseWithAnswers({
    required this.response,
    required this.answers,
  });
}
