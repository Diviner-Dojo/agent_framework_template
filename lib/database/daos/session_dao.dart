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
import 'photo_dao.dart';
import 'video_dao.dart';

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

  /// Create a complete quick mood tap session in a single atomic INSERT.
  ///
  /// Unlike the three-step sequence used by [SessionNotifier] (createSession →
  /// updateJournalingMode → endSession), this method writes all fields in one
  /// INSERT so no partial session is left if the app crashes between steps.
  /// A phantom session with journalingMode=null and endTime=null would be
  /// picked up by [resumeLatestSession] as a regular journaling session.
  ///
  /// [summary] is a pre-built human-readable string, e.g. "Mood: 😐 Neutral".
  Future<void> createQuickMoodSession(
    String sessionId,
    DateTime startTime,
    String timezone,
    String summary,
  ) async {
    await _db
        .into(_db.journalSessions)
        .insert(
          JournalSessionsCompanion.insert(
            sessionId: sessionId,
            startTime: startTime,
            timezone: Value(timezone),
            journalingMode: const Value('quick_mood_tap'),
            endTime: Value(startTime),
            summary: Value(summary),
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
    return (_db.select(_db.journalSessions)
          ..where((s) => s.journalingMode.isNotValue('quick_mood_tap'))
          ..orderBy([
            (s) =>
                OrderingTerm(expression: s.startTime, mode: OrderingMode.desc),
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
          ..where((s) => s.journalingMode.isNotValue('quick_mood_tap'))
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

  /// Delete a session and all its messages (and photos) atomically.
  ///
  /// Wraps the cascade delete in a transaction to prevent orphaned data.
  /// When [photoDao] is provided, photo records are deleted from the DB.
  /// Photo files on disk must be deleted separately before calling this
  /// (file I/O cannot run inside a drift transaction).
  /// Returns the number of session rows deleted (0 or 1).
  Future<int> deleteSessionCascade(
    MessageDao messageDao,
    String sessionId, {
    PhotoDao? photoDao,
    VideoDao? videoDao,
  }) async {
    return _db.transaction(() async {
      if (videoDao != null) {
        await videoDao.deleteVideosBySession(sessionId);
      }
      if (photoDao != null) {
        await photoDao.deletePhotosBySession(sessionId);
      }
      await messageDao.deleteMessagesBySession(sessionId);
      return deleteSession(sessionId);
    });
  }

  /// Delete all sessions, messages, photos, and videos atomically.
  ///
  /// Wraps the cascade in a transaction to prevent orphaned data.
  /// When [photoDao]/[videoDao] are provided, all records are deleted from
  /// the DB. Media files on disk must be deleted separately before calling
  /// this.
  Future<void> deleteAllCascade(
    MessageDao messageDao, {
    PhotoDao? photoDao,
    VideoDao? videoDao,
  }) async {
    await _db.transaction(() async {
      if (videoDao != null) {
        await videoDao.deleteAllVideos();
      }
      if (photoDao != null) {
        await photoDao.deleteAllPhotos();
      }
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
  // Location methods (Phase 10 — ADR-0019)
  // =========================================================================

  /// Update a session's location data after fire-and-forget capture.
  ///
  /// Coordinates should already be reduced to 2 decimal places before calling.
  /// Update summary and metadata on an already-ended session.
  ///
  /// Called from background metadata extraction after the session has been
  /// closed. Updates summary, mood tags, people, and topic tags without
  /// touching endTime.
  Future<void> updateSessionMetadata(
    String sessionId, {
    String? summary,
    String? moodTags,
    String? people,
    String? topicTags,
  }) async {
    await (_db.update(
      _db.journalSessions,
    )..where((s) => s.sessionId.equals(sessionId))).write(
      JournalSessionsCompanion(
        summary: Value(summary),
        moodTags: Value(moodTags),
        people: Value(people),
        topicTags: Value(topicTags),
        updatedAt: Value(DateTime.now().toUtc()),
      ),
    );
  }

  /// Set the journaling mode on a session.
  ///
  /// Called immediately after [createSession] when the session is started
  /// with a specific mode (e.g., 'onboarding', 'gratitude').
  Future<void> updateJournalingMode(
    String sessionId,
    String journalingMode,
  ) async {
    await (_db.update(
      _db.journalSessions,
    )..where((s) => s.sessionId.equals(sessionId))).write(
      JournalSessionsCompanion(
        journalingMode: Value(journalingMode),
        updatedAt: Value(DateTime.now().toUtc()),
      ),
    );
  }

  /// Sets syncStatus to 'PENDING' so the session re-enters the sync queue
  /// and [locationName] eventually reaches Supabase (coordinates are excluded
  /// from sync per ADR-0019).
  Future<int> updateSessionLocation(
    String sessionId, {
    required double latitude,
    required double longitude,
    double? locationAccuracy,
    String? locationName,
  }) async {
    return (_db.update(
      _db.journalSessions,
    )..where((s) => s.sessionId.equals(sessionId))).write(
      JournalSessionsCompanion(
        latitude: Value(latitude),
        longitude: Value(longitude),
        locationAccuracy: Value(locationAccuracy),
        locationName: Value(locationName),
        syncStatus: const Value('PENDING'),
        updatedAt: Value(DateTime.now().toUtc()),
      ),
    );
  }

  /// Write weather metadata captured at session start (Phase 4C).
  ///
  /// All three fields are written together — the WeatherService returns a
  /// complete result or nothing. Null is allowed for all fields if the API
  /// returns an unexpected code that has no human-readable label.
  Future<int> updateSessionWeather(
    String sessionId, {
    required double? weatherTempC,
    required int? weatherCode,
    required String? weatherDescription,
  }) async {
    return (_db.update(
      _db.journalSessions,
    )..where((s) => s.sessionId.equals(sessionId))).write(
      JournalSessionsCompanion(
        weatherTempC: Value(weatherTempC),
        weatherCode: Value(weatherCode),
        weatherDescription: Value(weatherDescription),
        updatedAt: Value(DateTime.now().toUtc()),
      ),
    );
  }

  /// Nullify all location columns across all sessions.
  ///
  /// Called by the "Clear Location Data" button in Settings. Also sets
  /// syncStatus to 'PENDING' on affected sessions so the next sync uploads
  /// null locationName to Supabase, overwriting previously synced values.
  ///
  /// Note: This does not trigger re-sync automatically — the existing sync
  /// machinery picks up PENDING sessions on the next sync cycle.
  /// Non-location columns (summary, moodTags, etc.) are left untouched.
  Future<int> clearAllLocationData() async {
    return (_db.update(_db.journalSessions)..where(
          (s) =>
              s.latitude.isNotNull() |
              s.longitude.isNotNull() |
              s.locationAccuracy.isNotNull() |
              s.locationName.isNotNull(),
        ))
        .write(
          JournalSessionsCompanion(
            latitude: const Value(null),
            longitude: const Value(null),
            locationAccuracy: const Value(null),
            locationName: const Value(null),
            syncStatus: const Value('PENDING'),
            updatedAt: Value(DateTime.now().toUtc()),
          ),
        );
  }

  // =========================================================================
  // Tag editing methods (ADHD Roadmap Phase 4A)
  // =========================================================================

  /// Update the three tag columns on a session without touching other fields.
  ///
  /// Each parameter should be a JSON-encoded array string (e.g. '["happy","tired"]')
  /// or null to clear that tag category.
  ///
  /// Called by the tag-editing UI in SessionDetailScreen whenever the user
  /// adds, removes, or edits a tag chip.
  Future<void> updateSessionTags(
    String sessionId, {
    String? moodTags,
    String? people,
    String? topicTags,
  }) async {
    await (_db.update(
      _db.journalSessions,
    )..where((s) => s.sessionId.equals(sessionId))).write(
      JournalSessionsCompanion(
        moodTags: Value(moodTags),
        people: Value(people),
        topicTags: Value(topicTags),
        updatedAt: Value(DateTime.now().toUtc()),
      ),
    );
  }

  // =========================================================================
  // Audio file methods (E7 — ADR-0024)
  // =========================================================================

  /// Update a session's audio file path after recording starts.
  ///
  /// Called by the voice session orchestrator after AudioFileService creates
  /// the WAV file. The path is an absolute path to the app documents directory.
  Future<void> updateAudioFilePath(String sessionId, String? path) async {
    await (_db.update(
      _db.journalSessions,
    )..where((s) => s.sessionId.equals(sessionId))).write(
      JournalSessionsCompanion(
        audioFilePath: Value(path),
        updatedAt: Value(DateTime.now().toUtc()),
      ),
    );
  }

  // =========================================================================
  // Session history methods (ADR-0023)
  // =========================================================================

  /// Get recent completed sessions with summaries for conversational continuity.
  ///
  /// Returns up to [limit] sessions that have both an endTime (completed)
  /// and a non-null summary. Ordered newest first. Each summary is truncated
  /// to 200 characters for payload size control (ADR-0023).
  Future<List<JournalSession>> getRecentCompletedSessions({
    int limit = 5,
  }) async {
    return (_db.select(_db.journalSessions)
          ..where((s) => s.endTime.isNotNull() & s.summary.isNotNull())
          ..orderBy([
            (s) =>
                OrderingTerm(expression: s.startTime, mode: OrderingMode.desc),
          ])
          ..limit(limit))
        .get();
  }

  // =========================================================================
  // Sync methods (Phase 4)
  // =========================================================================

  /// Get sessions that need to be synced to the cloud.
  ///
  /// Returns sessions where syncStatus is 'PENDING' or 'FAILED',
  /// ordered by start time ascending (oldest first — sync in chronological order).
  /// Sessions with 'FATAL' status are excluded — they failed due to
  /// non-retryable errors (E16) and would fail again on retry.
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
    final select = _db.select(_db.journalSessions)
      ..where((s) {
        // Start with keyword match when a query is provided.
        // When query is empty (filter-only browse), skip the keyword clause
        // so that all sessions are candidates before tag/date filtering.
        Expression<bool>? constraint;
        if (query.isNotEmpty) {
          final escaped = escapeLikeWildcards(query);
          final pattern = '%$escaped%';
          constraint =
              LikeWithEscape(s.summary, pattern) |
              LikeWithEscape(s.moodTags, pattern) |
              LikeWithEscape(s.people, pattern) |
              LikeWithEscape(s.topicTags, pattern);
        }

        // Apply optional date range filter.
        if (dateStart != null) {
          final c = s.startTime.isBiggerOrEqualValue(dateStart);
          constraint = constraint == null ? c : constraint & c;
        }
        if (dateEnd != null) {
          final c = s.startTime.isSmallerOrEqualValue(dateEnd);
          constraint = constraint == null ? c : constraint & c;
        }

        // Apply optional metadata tag filters (AND logic — all must match).
        if (moodTags != null && moodTags.isNotEmpty) {
          for (final tag in moodTags) {
            final tagPattern = '%${escapeLikeWildcards(tag)}%';
            final c = LikeWithEscape(s.moodTags, tagPattern);
            constraint = constraint == null ? c : constraint & c;
          }
        }
        if (people != null && people.isNotEmpty) {
          for (final person in people) {
            final personPattern = '%${escapeLikeWildcards(person)}%';
            final c = LikeWithEscape(s.people, personPattern);
            constraint = constraint == null ? c : constraint & c;
          }
        }
        if (topicTags != null && topicTags.isNotEmpty) {
          for (final tag in topicTags) {
            final tagPattern = '%${escapeLikeWildcards(tag)}%';
            final c = LikeWithEscape(s.topicTags, tagPattern);
            constraint = constraint == null ? c : constraint & c;
          }
        }

        // If no constraints at all (shouldn't happen — callers guard this),
        // return all sessions.
        return constraint ?? const Constant(true);
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
