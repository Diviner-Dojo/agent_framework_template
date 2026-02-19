// ===========================================================================
// file: lib/database/daos/session_dao.dart
// purpose: Data Access Object for journal sessions. Provides CRUD operations
//          on the journal_sessions table using drift's type-safe query API.
//
// Pattern: Constructor injection (see ADR-0007).
//   This DAO accepts AppDatabase in its constructor rather than using drift's
//   @DriftAccessor mixin. This makes testing straightforward:
//     final db = AppDatabase.forTesting(NativeDatabase.memory());
//     final dao = SessionDao(db);
//   Do NOT refactor to @DriftAccessor — the mixin pattern couples the DAO
//   to the database class hierarchy and complicates test setup.
// ===========================================================================

import 'package:drift/drift.dart';

import '../app_database.dart';

/// Provides all database operations for journal sessions.
///
/// Every method is async because drift operations return Futures
/// (they execute SQL on a background isolate).
///
/// Stream-returning methods (watch*) are used by Riverpod providers
/// to reactively update the UI when data changes.
class SessionDao {
  final AppDatabase _db;

  /// Create a SessionDao backed by the given database instance.
  /// In production, pass the singleton AppDatabase.
  /// In tests, pass AppDatabase.forTesting(NativeDatabase.memory()).
  SessionDao(this._db);

  /// Insert a new journal session.
  ///
  /// [sessionId] is a client-generated UUID (offline-first — no server needed).
  /// [startTime] should be UTC (call .toUtc() before passing).
  /// [timezone] is an IANA timezone string like "America/Denver".
  Future<void> createSession(
    String sessionId,
    DateTime startTime,
    String timezone,
  ) async {
    await _db
        .into(_db.journalSessions)
        .insert(
          JournalSessionsCompanion.insert(
            sessionId: sessionId,
            startTime: startTime,
            timezone: Value(timezone),
          ),
        );
  }

  /// Update a session when it ends.
  ///
  /// Sets the end time, AI-generated summary, and extracted metadata.
  /// All metadata fields are nullable — in Phase 1, only summary is populated.
  /// moodTags, people, and topicTags will be set by AI processing in Phase 3+.
  Future<void> endSession(
    String sessionId,
    DateTime endTime, {
    String? summary,
    String? moodTags,
    String? people,
    String? topicTags,
  }) async {
    await (_db.update(
      _db.journalSessions,
    )..where((s) => s.sessionId.equals(sessionId))).write(
      JournalSessionsCompanion(
        endTime: Value(endTime),
        summary: Value(summary),
        moodTags: Value(moodTags),
        people: Value(people),
        topicTags: Value(topicTags),
        updatedAt: Value(DateTime.now().toUtc()),
      ),
    );
  }

  /// Get a single session by its ID, or null if not found.
  ///
  /// Used when navigating to session detail view or when the session
  /// notifier needs to read back the current session's data.
  Future<JournalSession?> getSessionById(String sessionId) async {
    return (_db.select(
      _db.journalSessions,
    )..where((s) => s.sessionId.equals(sessionId))).getSingleOrNull();
  }

  /// Get all sessions ordered by start time descending (newest first).
  ///
  /// Used to populate the session list screen. Returns a one-time snapshot.
  /// For reactive updates, use [watchAllSessions] instead.
  Future<List<JournalSession>> getAllSessionsByDate() async {
    return (_db.select(_db.journalSessions)..orderBy([
          (s) => OrderingTerm(expression: s.startTime, mode: OrderingMode.desc),
        ]))
        .get();
  }

  /// Get sessions within a date range (inclusive on both ends).
  ///
  /// Useful for filtering sessions by week, month, etc.
  /// Both [start] and [end] should be UTC DateTimes.
  Future<List<JournalSession>> getSessionsByDateRange(
    DateTime start,
    DateTime end,
  ) async {
    return (_db.select(_db.journalSessions)
          ..where(
            (s) =>
                s.startTime.isBiggerOrEqualValue(start) &
                s.startTime.isSmallerOrEqualValue(end),
          )
          ..orderBy([
            (s) =>
                OrderingTerm(expression: s.startTime, mode: OrderingMode.desc),
          ]))
        .get();
  }

  /// Watch all sessions as a reactive stream, ordered newest first.
  ///
  /// This is the primary data source for the session list screen.
  /// drift automatically re-emits whenever the journal_sessions table changes,
  /// so the UI stays in sync without manual refresh logic.
  Stream<List<JournalSession>> watchAllSessions() {
    return (_db.select(_db.journalSessions)..orderBy([
          (s) => OrderingTerm(expression: s.startTime, mode: OrderingMode.desc),
        ]))
        .watch();
  }
}
