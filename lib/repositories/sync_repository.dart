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

import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../database/app_database.dart';
import '../database/daos/calendar_event_dao.dart';
import '../database/daos/message_dao.dart';
import '../database/daos/photo_dao.dart';
import '../database/daos/session_dao.dart';
import '../models/sync_status.dart';
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
  final PhotoDao? _photoDao;
  final CalendarEventDao? _calendarEventDao;

  SyncRepository({
    required SupabaseService supabaseService,
    required SessionDao sessionDao,
    required MessageDao messageDao,
    PhotoDao? photoDao,
    CalendarEventDao? calendarEventDao,
  }) : _supabaseService = supabaseService,
       _sessionDao = sessionDao,
       _messageDao = messageDao,
       _photoDao = photoDao,
       _calendarEventDao = calendarEventDao;

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
        final status = _isFatalSyncError(e)
            ? SyncStatus.fatal.toDbString()
            : SyncStatus.failed.toDbString();
        await _sessionDao.updateSyncStatus(
          session.sessionId,
          status,
          DateTime.now().toUtc(),
        );
        failed++;
        errors.add('Session ${session.sessionId}: $e');
        if (kDebugMode) {
          debugPrint(
            'Sync ${status.toLowerCase()} for session ${session.sessionId}: $e',
          );
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
    if (!_supabaseService.isAuthenticated) {
      debugPrint('[SyncRepo] syncSession: not authenticated, skipping');
      return;
    }

    final session = await _sessionDao.getSessionById(sessionId);
    if (session == null) {
      debugPrint('[SyncRepo] syncSession: session $sessionId not found');
      return;
    }

    try {
      debugPrint('[SyncRepo] Uploading session $sessionId...');
      await uploadSession(session);
      await _sessionDao.updateSyncStatus(
        sessionId,
        'SYNCED',
        DateTime.now().toUtc(),
      );
      debugPrint('[SyncRepo] Session $sessionId synced successfully');
    } on Exception catch (e) {
      final status = _isFatalSyncError(e)
          ? SyncStatus.fatal.toDbString()
          : SyncStatus.failed.toDbString();
      await _sessionDao.updateSyncStatus(
        sessionId,
        status,
        DateTime.now().toUtc(),
      );
      debugPrint('[SyncRepo] Sync ${status.toLowerCase()}: $e');
    }
  }

  // =========================================================================
  // Fatal error classification (E16)
  // =========================================================================

  /// Classify whether a sync error is fatal (non-retryable).
  ///
  /// Fatal errors indicate the data itself is the problem — retrying will
  /// produce the same error. These Postgres error code classes are fatal:
  ///   - Class 22: Data exception (e.g., invalid input syntax)
  ///   - Class 23: Integrity constraint violation (e.g., FK violation)
  ///   - Code 42501: Insufficient privilege (RLS policy violation)
  ///
  /// All other errors (network, timeout, server 5xx) are retryable.
  static bool _isFatalSyncError(Exception e) {
    if (e is PostgrestException) {
      final code = e.code;
      if (code == null) return false;
      // Class 22: Data exception
      if (code.startsWith('22')) return true;
      // Class 23: Integrity constraint violation
      if (code.startsWith('23')) return true;
      // 42501: Insufficient privilege (RLS violation)
      if (code == '42501') return true;
    }
    return false;
  }

  // =========================================================================
  // Upload logic
  // =========================================================================

  /// Upload a session, its messages, and calendar events to Supabase via UPSERT.
  ///
  /// The session, messages, and events are uploaded in separate calls (not
  /// atomic). If any step fails, the caller's catch block sets syncStatus to
  /// FAILED, so a retry will re-upload all. UPSERT idempotency (per ADR-0004)
  /// makes retries safe.
  @visibleForTesting
  Future<void> uploadSession(JournalSession session) async {
    final client = _supabaseService.client;
    if (client == null) return;

    final userId = _supabaseService.currentUser?.id;
    if (userId == null) return;

    // UPSERT session (ON CONFLICT DO UPDATE for idempotency)
    await client
        .from('journal_sessions')
        .upsert(buildSessionUpsertMap(session, userId));

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

    // UPSERT calendar events for this session (ADR-0020).
    if (_calendarEventDao != null) {
      final events = await _calendarEventDao.getEventsForSession(
        session.sessionId,
      );
      if (events.isNotEmpty) {
        final eventRows = events
            .map((e) => buildEventUpsertMap(e, userId))
            .toList();
        await client.from('calendar_events').upsert(eventRows);

        // Mark synced events.
        for (final event in events) {
          await _calendarEventDao.updateSyncStatus(event.eventId, 'SYNCED');
        }
      }
    }
  }

  /// Build the upsert map for a session row in Supabase.
  ///
  /// Extracted as a testable method so unit tests can assert the map's keys.
  /// Per ADR-0019 §3: `location_name` is included; `latitude`, `longitude`,
  /// and `location_accuracy` are intentionally excluded (coordinates stay local).
  @visibleForTesting
  static Map<String, dynamic> buildSessionUpsertMap(
    JournalSession session,
    String userId,
  ) {
    return {
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
      // Location: name only — coordinates stay local (ADR-0019 §3).
      'location_name': session.locationName,
      // Journaling mode for guided sessions (ADR-0025).
      'journaling_mode': session.journalingMode,
      // Note: audioFilePath is intentionally excluded — audio files are
      // local-only and not synced to cloud (ADR-0024).
      'sync_status': 'SYNCED',
      'created_at': session.createdAt.toUtc().toIso8601String(),
      'updated_at': DateTime.now().toUtc().toIso8601String(),
    };
  }

  /// Build the upsert map for a calendar event row in Supabase.
  ///
  /// Extracted as a testable method so unit tests can assert the map's keys.
  /// Mirrors the Supabase `calendar_events` table schema (003_events_schema.sql).
  @visibleForTesting
  static Map<String, dynamic> buildEventUpsertMap(
    CalendarEvent event,
    String userId,
  ) {
    return {
      'event_id': event.eventId,
      'session_id': event.sessionId,
      'user_id': userId,
      'title': event.title,
      'start_time': event.startTime.toUtc().toIso8601String(),
      'end_time': event.endTime?.toUtc().toIso8601String(),
      'google_event_id': event.googleEventId,
      'status': event.status,
      'sync_status': 'SYNCED',
      'raw_user_message': event.rawUserMessage,
      'created_at': event.createdAt.toUtc().toIso8601String(),
      'updated_at': DateTime.now().toUtc().toIso8601String(),
    };
  }

  /// Sync all pending calendar events across all sessions.
  ///
  /// Returns a [SyncResult] with counts of synced/failed events.
  /// No-op if not authenticated or no CalendarEventDao was provided.
  /// See: ADR-0020 (Google Calendar Integration)
  Future<SyncResult> syncPendingCalendarEvents() async {
    if (!_supabaseService.isAuthenticated || _calendarEventDao == null) {
      return const SyncResult();
    }

    final client = _supabaseService.client;
    final userId = _supabaseService.currentUser?.id;
    if (client == null || userId == null) return const SyncResult();

    final eventsToSync = await _calendarEventDao.getEventsToSync();
    if (eventsToSync.isEmpty) return const SyncResult();

    int synced = 0;
    int failed = 0;
    final errors = <String>[];

    for (final event in eventsToSync) {
      try {
        await client
            .from('calendar_events')
            .upsert(buildEventUpsertMap(event, userId));
        await _calendarEventDao.updateSyncStatus(event.eventId, 'SYNCED');
        synced++;
      } on Exception catch (e) {
        final eventStatus = _isFatalSyncError(e)
            ? SyncStatus.fatal.toDbString()
            : SyncStatus.failed.toDbString();
        await _calendarEventDao.updateSyncStatus(event.eventId, eventStatus);
        failed++;
        errors.add('Event ${event.eventId}: $e');
        if (kDebugMode) {
          debugPrint(
            'Event sync ${eventStatus.toLowerCase()} for ${event.eventId}: $e',
          );
        }
      }
    }

    return SyncResult(syncedCount: synced, failedCount: failed, errors: errors);
  }

  /// Upload photos for a session to Supabase Storage.
  ///
  /// Uploads photos in parallel (max 3 concurrent) to the `journal-photos`
  /// bucket under `[userId]/photos/[photoId].jpg`. Updates each photo's
  /// syncStatus and cloudUrl on success/failure.
  ///
  /// No-op if not authenticated or no PhotoDao was provided.
  /// See: ADR-0018 (Photo Storage Architecture)
  Future<SyncResult> uploadSessionPhotos(String sessionId) async {
    if (!_supabaseService.isAuthenticated || _photoDao == null) {
      return const SyncResult();
    }

    final client = _supabaseService.client;
    final userId = _supabaseService.currentUser?.id;
    if (client == null || userId == null) return const SyncResult();

    final photos = await _photoDao.getPhotosForSession(sessionId);
    final pendingPhotos = photos
        .where((p) => p.syncStatus != 'SYNCED')
        .toList();
    if (pendingPhotos.isEmpty) return const SyncResult();

    int synced = 0;
    int failed = 0;
    final errors = <String>[];

    // Process in batches of 3 for bounded concurrency.
    for (int i = 0; i < pendingPhotos.length; i += 3) {
      final batch = pendingPhotos.skip(i).take(3);
      final futures = batch.map((photo) async {
        try {
          final file = File(photo.localPath);
          if (!file.existsSync()) {
            throw FileSystemException('Photo file not found', photo.localPath);
          }

          final storagePath = '$userId/photos/${photo.photoId}.jpg';
          final bytes = await file.readAsBytes();

          await client.storage
              .from('journal-photos')
              .uploadBinary(
                storagePath,
                bytes,
                fileOptions: FileOptions(upsert: true),
              );

          // Store the canonical storage path — NOT a public URL.
          // The bucket is private; use createSignedUrl() at display time
          // to generate a short-lived authenticated URL (ADR-0018).
          await _photoDao.updateCloudUrl(photo.photoId, storagePath);
          await _photoDao.updateSyncStatus(photo.photoId, 'SYNCED');
          synced++;
        } on Exception catch (e) {
          await _photoDao.updateSyncStatus(photo.photoId, 'FAILED');
          failed++;
          errors.add('Photo ${photo.photoId}: $e');
          if (kDebugMode) {
            debugPrint('Photo sync failed for ${photo.photoId}: $e');
          }
        }
      });

      await Future.wait(futures);
    }

    return SyncResult(syncedCount: synced, failedCount: failed, errors: errors);
  }

  /// Upload all pending photos across all sessions.
  ///
  /// Returns a [SyncResult] with counts of synced/failed photos.
  /// No-op if not authenticated or no PhotoDao was provided.
  Future<SyncResult> syncPendingPhotos() async {
    if (!_supabaseService.isAuthenticated || _photoDao == null) {
      return const SyncResult();
    }

    final photosToSync = await _photoDao.getPhotosToSync();
    if (photosToSync.isEmpty) return const SyncResult();

    // Group by session for organized upload.
    final sessionIds = photosToSync.map((p) => p.sessionId).toSet();
    int totalSynced = 0;
    int totalFailed = 0;
    final allErrors = <String>[];

    for (final sessionId in sessionIds) {
      final result = await uploadSessionPhotos(sessionId);
      totalSynced += result.syncedCount;
      totalFailed += result.failedCount;
      allErrors.addAll(result.errors);
    }

    return SyncResult(
      syncedCount: totalSynced,
      failedCount: totalFailed,
      errors: allErrors,
    );
  }
}
