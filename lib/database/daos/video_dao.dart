// ===========================================================================
// file: lib/database/daos/video_dao.dart
// purpose: Data Access Object for session videos. Provides CRUD operations
//          on the videos table using drift's type-safe query API.
//
// Pattern: Constructor injection (see ADR-0007).
//   Same rationale as PhotoDao — inject AppDatabase for easy testing.
//
// See: ADR-0021 (Video Capture Architecture)
// ===========================================================================

import 'package:drift/drift.dart';

import '../app_database.dart';

/// Provides all database operations for videos attached to journal sessions.
///
/// Videos are linked to sessions via [sessionId] and optionally to messages
/// via [messageId]. Each video has a local file path, thumbnail path, and
/// optional cloud URL.
class VideoDao {
  final AppDatabase _db;

  /// Create a VideoDao backed by the given database instance.
  VideoDao(this._db);

  /// Insert a new video record.
  ///
  /// [videoId] is a client-generated UUID.
  /// [sessionId] must reference an existing session.
  /// [localPath] is the relative path within app support directory.
  /// [thumbnailPath] is the relative path to the thumbnail JPEG.
  /// [durationSeconds] is the recording duration.
  /// [timestamp] should be UTC.
  Future<void> insertVideo({
    required String videoId,
    required String sessionId,
    required String localPath,
    required String thumbnailPath,
    required int durationSeconds,
    required DateTime timestamp,
    String? messageId,
    String? description,
    int? width,
    int? height,
    int? fileSizeBytes,
  }) async {
    await _db
        .into(_db.videos)
        .insert(
          VideosCompanion.insert(
            videoId: videoId,
            sessionId: sessionId,
            localPath: localPath,
            thumbnailPath: thumbnailPath,
            durationSeconds: durationSeconds,
            timestamp: timestamp,
            messageId: Value(messageId),
            description: Value(description),
            width: Value(width),
            height: Value(height),
            fileSizeBytes: Value(fileSizeBytes),
          ),
        );
  }

  /// Get a single video by its ID, or null if not found.
  Future<Video?> getVideoById(String videoId) async {
    return (_db.select(
      _db.videos,
    )..where((v) => v.videoId.equals(videoId))).getSingleOrNull();
  }

  /// Get all videos for a session, ordered by timestamp ascending.
  Future<List<Video>> getVideosForSession(String sessionId) async {
    return (_db.select(_db.videos)
          ..where((v) => v.sessionId.equals(sessionId))
          ..orderBy([
            (v) =>
                OrderingTerm(expression: v.timestamp, mode: OrderingMode.asc),
          ]))
        .get();
  }

  /// Watch videos for a session as a reactive stream.
  ///
  /// Used by providers to reactively update the UI when videos change.
  Stream<List<Video>> watchVideosForSession(String sessionId) {
    return (_db.select(_db.videos)
          ..where((v) => v.sessionId.equals(sessionId))
          ..orderBy([
            (v) =>
                OrderingTerm(expression: v.timestamp, mode: OrderingMode.asc),
          ]))
        .watch();
  }

  /// Update the user-authored description of a video.
  ///
  /// Called from the session detail edit sheet when a user edits the caption
  /// on a video bubble (mirrors PhotoDao.updateDescription — see ADR-0021).
  Future<void> updateDescription(String videoId, String description) async {
    await (_db.update(_db.videos)..where((v) => v.videoId.equals(videoId)))
        .write(VideosCompanion(description: Value(description)));
  }

  /// Update the cloud URL after successful upload.
  Future<void> updateCloudUrl(String videoId, String cloudUrl) async {
    await (_db.update(
      _db.videos,
    )..where((v) => v.videoId.equals(videoId))).write(
      VideosCompanion(
        cloudUrl: Value(cloudUrl),
        updatedAt: Value(DateTime.now().toUtc()),
      ),
    );
  }

  /// Update the sync status of a video.
  Future<void> updateSyncStatus(String videoId, String status) async {
    await (_db.update(
      _db.videos,
    )..where((v) => v.videoId.equals(videoId))).write(
      VideosCompanion(
        syncStatus: Value(status),
        updatedAt: Value(DateTime.now().toUtc()),
      ),
    );
  }

  /// Get videos that need to be synced (PENDING or FAILED).
  Future<List<Video>> getVideosToSync() async {
    return (_db.select(_db.videos)
          ..where(
            (v) =>
                v.syncStatus.equals('PENDING') | v.syncStatus.equals('FAILED'),
          )
          ..orderBy([
            (v) =>
                OrderingTerm(expression: v.timestamp, mode: OrderingMode.asc),
          ]))
        .get();
  }

  /// Delete a single video by ID.
  ///
  /// Returns the number of rows deleted (0 or 1).
  /// IMPORTANT: Caller must delete the video file and thumbnail from disk.
  Future<int> deleteVideo(String videoId) async {
    return (_db.delete(
      _db.videos,
    )..where((v) => v.videoId.equals(videoId))).go();
  }

  /// Delete all videos for a session.
  ///
  /// Returns the number of rows deleted.
  /// Used as cascade step before session deletion.
  Future<int> deleteVideosBySession(String sessionId) async {
    return (_db.delete(
      _db.videos,
    )..where((v) => v.sessionId.equals(sessionId))).go();
  }

  /// Count the total number of videos.
  Future<int> getVideoCount() async {
    final count = _db.videos.videoId.count();
    final query = _db.selectOnly(_db.videos)..addColumns([count]);
    final result = await query.getSingle();
    return result.read(count) ?? 0;
  }

  /// Get the total size of all videos in bytes.
  ///
  /// Returns 0 if no videos have size data.
  Future<int> getTotalVideoSize() async {
    final sum = _db.videos.fileSizeBytes.sum();
    final query = _db.selectOnly(_db.videos)..addColumns([sum]);
    final result = await query.getSingle();
    return result.read(sum) ?? 0;
  }

  /// Delete all videos across all sessions.
  ///
  /// Returns the number of rows deleted.
  Future<int> deleteAllVideos() async {
    return _db.delete(_db.videos).go();
  }
}
