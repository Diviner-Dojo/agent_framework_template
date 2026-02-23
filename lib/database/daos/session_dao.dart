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

import 'dart:convert';

import 'package:drift/drift.dart';

import '../app_database.dart';
import '../search_query_utils.dart';
import 'message_dao.dart';

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

  /// Watch sessions with a dynamic limit, ordered newest first.
  ///
  /// Used by the landing page for pagination. The [limit] parameter
  /// controls how many sessions are streamed. Incrementing it loads
  /// older entries without a separate cursor-based query.
  Stream<List<JournalSession>> watchSessionsPaginated(int limit) {
    return (_db.select(_db.journalSessions)
          ..orderBy([
            (s) =>
                OrderingTerm(expression: s.startTime, mode: OrderingMode.desc),
          ])
          ..limit(limit))
        .watch();
  }

  // =========================================================================
  // Delete methods (Phase 6 — ADR-0014)
  // =========================================================================

  /// Delete a single session by ID.
  ///
  /// Returns the number of rows deleted (0 if session doesn't exist, 1 if deleted).
  /// IMPORTANT: Caller must delete associated messages first via
  /// [MessageDao.deleteMessagesBySession] — drift's `references()` is
  /// documentation-only and does not enforce cascading deletes.
  Future<int> deleteSession(String sessionId) async {
    return (_db.delete(
      _db.journalSessions,
    )..where((s) => s.sessionId.equals(sessionId))).go();
  }

  /// Delete all sessions.
  ///
  /// Returns the number of rows deleted.
  /// IMPORTANT: Caller must delete all messages first via
  /// [MessageDao.deleteAllMessages].
  Future<int> deleteAllSessions() async {
    return _db.delete(_db.journalSessions).go();
  }

  /// Delete a session and all its messages atomically.
  ///
  /// Wraps the cascade delete (messages first, then session) in a
  /// transaction to prevent orphaned data if one step fails.
  /// Returns the number of session rows deleted (0 or 1).
  Future<int> deleteSessionCascade(
    MessageDao messageDao,
    String sessionId,
  ) async {
    return _db.transaction(() async {
      await messageDao.deleteMessagesBySession(sessionId);
      return deleteSession(sessionId);
    });
  }

  /// Delete all sessions and messages atomically.
  ///
  /// Wraps the cascade (all messages first, then all sessions) in a
  /// transaction to prevent orphaned data if one step fails.
  Future<void> deleteAllCascade(MessageDao messageDao) async {
    await _db.transaction(() async {
      await messageDao.deleteAllMessages();
      await deleteAllSessions();
    });
  }

  /// Resume a completed session for continued journaling (ADR-0014).
  ///
  /// Clears endTime, sets isResumed=true, increments resumeCount,
  /// and reverts syncStatus to 'PENDING' (resumed content needs re-sync).
  /// Returns the number of rows updated (0 if session doesn't exist, 1 if updated).
  Future<int> resumeSession(String sessionId) async {
    // First read the current resumeCount.
    final session = await getSessionById(sessionId);
    if (session == null) return 0;

    return (_db.update(
      _db.journalSessions,
    )..where((s) => s.sessionId.equals(sessionId))).write(
      JournalSessionsCompanion(
        endTime: const Value(null),
        isResumed: const Value(true),
        resumeCount: Value(session.resumeCount + 1),
        syncStatus: const Value('PENDING'),
        updatedAt: Value(DateTime.now().toUtc()),
      ),
    );
  }

  // =========================================================================
  // Sync methods (Phase 4)
  // =========================================================================

  /// Get sessions that need to be synced to the cloud.
  ///
  /// Returns sessions where syncStatus is 'PENDING' or 'FAILED',
  /// ordered by start time ascending (oldest first — sync in chronological order).
  Future<List<JournalSession>> getSessionsToSync() async {
    return (_db.select(_db.journalSessions)
          ..where(
            (s) =>
                s.syncStatus.equals('PENDING') | s.syncStatus.equals('FAILED'),
          )
          ..orderBy([
            (s) =>
                OrderingTerm(expression: s.startTime, mode: OrderingMode.asc),
          ]))
        .get();
  }

  /// Update the sync status of a session.
  ///
  /// Called by SyncRepository after a sync attempt:
  ///   - On success: status='SYNCED', lastAttempt=now
  ///   - On failure: status='FAILED', lastAttempt=now
  Future<void> updateSyncStatus(
    String sessionId,
    String status,
    DateTime lastAttempt,
  ) async {
    await (_db.update(
      _db.journalSessions,
    )..where((s) => s.sessionId.equals(sessionId))).write(
      JournalSessionsCompanion(
        syncStatus: Value(status),
        lastSyncAttempt: Value(lastAttempt),
        updatedAt: Value(DateTime.now().toUtc()),
      ),
    );
  }

  /// Watch the count of sessions that are not yet synced.
  ///
  /// Used by the sync status UI to show pending sync count.
  Stream<int> watchPendingSyncCount() {
    final count = _db.journalSessions.sessionId.count();
    final query = _db.selectOnly(_db.journalSessions)
      ..addColumns([count])
      ..where(_db.journalSessions.syncStatus.isIn(['PENDING', 'FAILED']));
    return query.watchSingle().map((row) => row.read(count) ?? 0);
  }

  // =========================================================================
  // Search methods (Phase 5)
  // =========================================================================

  /// Search sessions by keyword across summary and metadata columns.
  ///
  /// Uses case-insensitive LIKE queries with ESCAPE clause (not FTS5) —
  /// see ADR-0013. LIKE wildcards (%, _) in [query] are escaped.
  /// Optional filters narrow results by date range and metadata tags.
  ///
  /// Note: Metadata tag filters use substring LIKE matching against JSON
  /// array strings (e.g., '["happy","tired"]'). This means a filter for
  /// "happ" would match "happy". Acceptable for personal journal scale;
  /// a normalized tags table would eliminate this if needed.
  ///
  /// Returns sessions ordered by start time descending (newest first).
  Future<List<JournalSession>> searchSessions(
    String query, {
    DateTime? dateStart,
    DateTime? dateEnd,
    List<String>? moodTags,
    List<String>? people,
    List<String>? topicTags,
  }) async {
    final escaped = escapeLikeWildcards(query);
    final pattern = '%$escaped%';

    final select = _db.select(_db.journalSessions)
      ..where((s) {
        // Keyword match across summary and metadata columns.
        Expression<bool> keywordMatch =
            LikeWithEscape(s.summary, pattern) |
            LikeWithEscape(s.moodTags, pattern) |
            LikeWithEscape(s.people, pattern) |
            LikeWithEscape(s.topicTags, pattern);

        // Apply optional date range filter.
        if (dateStart != null) {
          keywordMatch =
              keywordMatch & s.startTime.isBiggerOrEqualValue(dateStart);
        }
        if (dateEnd != null) {
          keywordMatch =
              keywordMatch & s.startTime.isSmallerOrEqualValue(dateEnd);
        }

        // Apply optional metadata tag filters (AND logic — all must match).
        if (moodTags != null && moodTags.isNotEmpty) {
          for (final tag in moodTags) {
            final tagPattern = '%${escapeLikeWildcards(tag)}%';
            keywordMatch =
                keywordMatch & LikeWithEscape(s.moodTags, tagPattern);
          }
        }
        if (people != null && people.isNotEmpty) {
          for (final person in people) {
            final personPattern = '%${escapeLikeWildcards(person)}%';
            keywordMatch =
                keywordMatch & LikeWithEscape(s.people, personPattern);
          }
        }
        if (topicTags != null && topicTags.isNotEmpty) {
          for (final tag in topicTags) {
            final tagPattern = '%${escapeLikeWildcards(tag)}%';
            keywordMatch =
                keywordMatch & LikeWithEscape(s.topicTags, tagPattern);
          }
        }

        return keywordMatch;
      })
      ..orderBy([
        (s) => OrderingTerm(expression: s.startTime, mode: OrderingMode.desc),
      ]);

    return select.get();
  }

  /// Get all distinct mood tags across all sessions.
  ///
  /// Parses JSON array strings from the moodTags column and returns
  /// a deduplicated, sorted list. Used to populate filter chips.
  Future<List<String>> getDistinctMoodTags() async {
    return _getDistinctJsonArrayValues((s) => s.moodTags);
  }

  /// Get all distinct people mentioned across all sessions.
  ///
  /// Parses JSON array strings from the people column and returns
  /// a deduplicated, sorted list. Used to populate filter chips.
  Future<List<String>> getDistinctPeople() async {
    return _getDistinctJsonArrayValues((s) => s.people);
  }

  /// Get all distinct topic tags across all sessions.
  ///
  /// Parses JSON array strings from the topicTags column and returns
  /// a deduplicated, sorted list. Used to populate filter chips.
  Future<List<String>> getDistinctTopicTags() async {
    return _getDistinctJsonArrayValues((s) => s.topicTags);
  }

  /// Count the total number of sessions.
  ///
  /// Used for progressive disclosure: search icon appears at 5+ sessions.
  Future<int> countSessions() async {
    final count = _db.journalSessions.sessionId.count();
    final query = _db.selectOnly(_db.journalSessions)..addColumns([count]);
    final result = await query.getSingle();
    return result.read(count) ?? 0;
  }

  // =========================================================================
  // Private helpers
  // =========================================================================

  /// Extract distinct values from a JSON array column across all sessions.
  ///
  /// The moodTags, people, and topicTags columns store JSON arrays as strings
  /// (e.g., '["happy","tired"]'). This method reads all non-null values,
  /// parses each JSON array, and returns a deduplicated sorted list.
  Future<List<String>> _getDistinctJsonArrayValues(
    GeneratedColumn<String> Function($JournalSessionsTable) columnSelector,
  ) async {
    final column = columnSelector(_db.journalSessions);
    final query = _db.selectOnly(_db.journalSessions)
      ..addColumns([column])
      ..where(column.isNotNull());

    final rows = await query.get();
    final values = <String>{};

    for (final row in rows) {
      final jsonStr = row.read(column);
      if (jsonStr == null || jsonStr.isEmpty) continue;
      try {
        final decoded = _decodeJsonArray(jsonStr);
        values.addAll(decoded);
      } on FormatException {
        // Skip malformed JSON — don't crash search for bad data.
      }
    }

    final sorted = values.toList()..sort();
    return sorted;
  }

  /// Decode a JSON string into a list of strings.
  ///
  /// Handles both JSON array format '["a","b"]' and plain strings.
  static List<String> _decodeJsonArray(String jsonStr) {
    final dynamic decoded = _jsonDecode(jsonStr);
    if (decoded is List) {
      return decoded.whereType<String>().toList();
    }
    // If it's a plain string (not JSON array), return as single-element list.
    if (decoded is String) {
      return [decoded];
    }
    return [];
  }

  /// Wrapper for json.decode to keep the import localized.
  static dynamic _jsonDecode(String source) {
    return const JsonDecoder().convert(source);
  }
}
