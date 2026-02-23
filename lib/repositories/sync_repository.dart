// ===========================================================================
// file: lib/repositories/sync_repository.dart
// purpose: Manages uploading local journal data to Supabase PostgreSQL.
//
// Sync strategy:
//   - Upload-only (phone → cloud), no download (ADR-0012)
//   - On-demand: after endSession() + manual "Sync Now"
//   - UPSERT for idempotency (safe retries per ADR-0004)
//   - No-op when not authenticated (optional auth)
//
// See: ADR-0012 (Optional Auth with Upload-Only Cloud Sync)
//      ADR-0004 (Offline-First Architecture)
// ===========================================================================

import 'package:flutter/foundation.dart';

import '../database/app_database.dart';
import '../database/daos/message_dao.dart';
import '../database/daos/session_dao.dart';
import '../services/supabase_service.dart';

/// Result of a sync operation.
class SyncResult {
  final int syncedCount;
  final int failedCount;
  final List<String> errors;

  const SyncResult({
    this.syncedCount = 0,
    this.failedCount = 0,
    this.errors = const [],
  });

  bool get hasFailures => failedCount > 0;
}

/// Uploads local journal data to Supabase PostgreSQL.
///
/// All sync operations require authentication. When the user is not
/// signed in, methods return early (no-op). Sync failures are recorded
/// in the local database (syncStatus = 'FAILED') for retry.
class SyncRepository {
  final SupabaseService _supabaseService;
  final SessionDao _sessionDao;
  final MessageDao _messageDao;

  SyncRepository({
    required SupabaseService supabaseService,
    required SessionDao sessionDao,
    required MessageDao messageDao,
  }) : _supabaseService = supabaseService,
       _sessionDao = sessionDao,
       _messageDao = messageDao;

  /// Sync all pending and failed sessions to Supabase.
  ///
  /// Returns a [SyncResult] with counts of synced/failed sessions.
  /// No-op if not authenticated.
  Future<SyncResult> syncPendingSessions() async {
    if (!_supabaseService.isAuthenticated) {
      return const SyncResult();
    }

    final sessionsToSync = await _sessionDao.getSessionsToSync();
    if (sessionsToSync.isEmpty) return const SyncResult();

    int synced = 0;
    int failed = 0;
    final errors = <String>[];

    for (final session in sessionsToSync) {
      try {
        await uploadSession(session);
        await _sessionDao.updateSyncStatus(
          session.sessionId,
          'SYNCED',
          DateTime.now().toUtc(),
        );
        synced++;
      } on Exception catch (e) {
        await _sessionDao.updateSyncStatus(
          session.sessionId,
          'FAILED',
          DateTime.now().toUtc(),
        );
        failed++;
        errors.add('Session ${session.sessionId}: $e');
        if (kDebugMode) {
          debugPrint('Sync failed for session ${session.sessionId}: $e');
        }
      }
    }

    return SyncResult(syncedCount: synced, failedCount: failed, errors: errors);
  }

  /// Sync a single session to Supabase.
  ///
  /// Called after endSession() for immediate upload.
  /// No-op if not authenticated.
  Future<void> syncSession(String sessionId) async {
    if (!_supabaseService.isAuthenticated) return;

    final session = await _sessionDao.getSessionById(sessionId);
    if (session == null) return;

    try {
      await uploadSession(session);
      await _sessionDao.updateSyncStatus(
        sessionId,
        'SYNCED',
        DateTime.now().toUtc(),
      );
    } on Exception catch (e) {
      await _sessionDao.updateSyncStatus(
        sessionId,
        'FAILED',
        DateTime.now().toUtc(),
      );
      if (kDebugMode) {
        debugPrint('Sync failed for session $sessionId: $e');
      }
    }
  }

  // =========================================================================
  // Upload logic
  // =========================================================================

  /// Upload a session and its messages to Supabase via UPSERT.
  ///
  /// The session and messages are uploaded in two separate calls (not atomic).
  /// If the session UPSERT succeeds but messages fail, the caller's catch
  /// block sets syncStatus to FAILED, so a retry will re-upload both.
  /// UPSERT idempotency (per ADR-0004) makes retries safe.
  @visibleForTesting
  Future<void> uploadSession(JournalSession session) async {
    final client = _supabaseService.client;
    if (client == null) return;

    final userId = _supabaseService.currentUser?.id;
    if (userId == null) return;

    // UPSERT session (ON CONFLICT DO UPDATE for idempotency)
    await client.from('journal_sessions').upsert({
      'session_id': session.sessionId,
      'user_id': userId,
      'start_time': session.startTime.toUtc().toIso8601String(),
      'end_time': session.endTime?.toUtc().toIso8601String(),
      'timezone': session.timezone,
      'summary': session.summary,
      'mood_tags': session.moodTags,
      'people': session.people,
      'topic_tags': session.topicTags,
      'is_resumed': session.isResumed,
      'resume_count': session.resumeCount,
      'sync_status': 'SYNCED',
      'created_at': session.createdAt.toUtc().toIso8601String(),
      'updated_at': DateTime.now().toUtc().toIso8601String(),
    });

    // UPSERT all messages for this session
    final messages = await _messageDao.getMessagesForSession(session.sessionId);

    if (messages.isNotEmpty) {
      final messageRows = messages
          .map(
            (m) => {
              'message_id': m.messageId,
              'session_id': m.sessionId,
              'user_id': userId,
              'role': m.role,
              'content': m.content,
              'timestamp': m.timestamp.toUtc().toIso8601String(),
              'input_method': m.inputMethod,
              'entities_json': m.entitiesJson,
              'sentiment': m.sentiment,
              'embedding_id': m.embeddingId,
            },
          )
          .toList();

      await client.from('journal_messages').upsert(messageRows);
    }
  }
}
