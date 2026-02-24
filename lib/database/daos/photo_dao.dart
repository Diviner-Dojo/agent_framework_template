// ===========================================================================
// file: lib/database/daos/photo_dao.dart
// purpose: Data Access Object for session photos. Provides CRUD operations
//          on the photos table using drift's type-safe query API.
//
// Pattern: Constructor injection (see ADR-0007).
//   Same rationale as SessionDao — inject AppDatabase for easy testing.
//   Do NOT refactor to @DriftAccessor mixin.
//
// See: ADR-0018 (Photo Storage Architecture)
// ===========================================================================

import 'package:drift/drift.dart';

import '../app_database.dart';

/// Provides all database operations for photos attached to journal sessions.
///
/// Photos are linked to sessions via [sessionId] and optionally to messages
/// via [messageId]. Each photo has a local file path and optional cloud URL.
class PhotoDao {
  final AppDatabase _db;

  /// Create a PhotoDao backed by the given database instance.
  PhotoDao(this._db);

  /// Insert a new photo record.
  ///
  /// [photoId] is a client-generated UUID.
  /// [sessionId] must reference an existing session.
  /// [localPath] is the relative path within app support directory.
  /// [timestamp] should be UTC.
  Future<void> insertPhoto({
    required String photoId,
    required String sessionId,
    required String localPath,
    required DateTime timestamp,
    String? messageId,
    String? description,
    int? width,
    int? height,
    int? fileSizeBytes,
  }) async {
    await _db
        .into(_db.photos)
        .insert(
          PhotosCompanion.insert(
            photoId: photoId,
            sessionId: sessionId,
            localPath: localPath,
            timestamp: timestamp,
            messageId: Value(messageId),
            description: Value(description),
            width: Value(width),
            height: Value(height),
            fileSizeBytes: Value(fileSizeBytes),
          ),
        );
  }

  /// Get a single photo by its ID, or null if not found.
  Future<Photo?> getPhotoById(String photoId) async {
    return (_db.select(
      _db.photos,
    )..where((p) => p.photoId.equals(photoId))).getSingleOrNull();
  }

  /// Get all photos for a session, ordered by timestamp ascending.
  Future<List<Photo>> getPhotosForSession(String sessionId) async {
    return (_db.select(_db.photos)
          ..where((p) => p.sessionId.equals(sessionId))
          ..orderBy([
            (p) =>
                OrderingTerm(expression: p.timestamp, mode: OrderingMode.asc),
          ]))
        .get();
  }

  /// Watch photos for a session as a reactive stream.
  ///
  /// Used by providers to reactively update the UI when photos change.
  Stream<List<Photo>> watchPhotosForSession(String sessionId) {
    return (_db.select(_db.photos)
          ..where((p) => p.sessionId.equals(sessionId))
          ..orderBy([
            (p) =>
                OrderingTerm(expression: p.timestamp, mode: OrderingMode.asc),
          ]))
        .watch();
  }

  /// Get the photo associated with a specific message, or null.
  Future<Photo?> getPhotoByMessageId(String messageId) async {
    return (_db.select(
      _db.photos,
    )..where((p) => p.messageId.equals(messageId))).getSingleOrNull();
  }

  /// Get all photos across all sessions, ordered newest first.
  Future<List<Photo>> getAllPhotos() async {
    return (_db.select(_db.photos)..orderBy([
          (p) => OrderingTerm(expression: p.timestamp, mode: OrderingMode.desc),
        ]))
        .get();
  }

  /// Watch all photos as a reactive stream, ordered newest first.
  Stream<List<Photo>> watchAllPhotos() {
    return (_db.select(_db.photos)..orderBy([
          (p) => OrderingTerm(expression: p.timestamp, mode: OrderingMode.desc),
        ]))
        .watch();
  }

  /// Count the total number of photos.
  Future<int> getPhotoCount() async {
    final count = _db.photos.photoId.count();
    final query = _db.selectOnly(_db.photos)..addColumns([count]);
    final result = await query.getSingle();
    return result.read(count) ?? 0;
  }

  /// Get the total size of all photos in bytes.
  ///
  /// Returns 0 if no photos have size data.
  Future<int> getTotalPhotoSize() async {
    final sum = _db.photos.fileSizeBytes.sum();
    final query = _db.selectOnly(_db.photos)..addColumns([sum]);
    final result = await query.getSingle();
    return result.read(sum) ?? 0;
  }

  /// Update the description of a photo.
  Future<void> updateDescription(String photoId, String description) async {
    await (_db.update(
      _db.photos,
    )..where((p) => p.photoId.equals(photoId))).write(
      PhotosCompanion(
        description: Value(description),
        updatedAt: Value(DateTime.now().toUtc()),
      ),
    );
  }

  /// Update the cloud URL after successful upload.
  Future<void> updateCloudUrl(String photoId, String cloudUrl) async {
    await (_db.update(
      _db.photos,
    )..where((p) => p.photoId.equals(photoId))).write(
      PhotosCompanion(
        cloudUrl: Value(cloudUrl),
        updatedAt: Value(DateTime.now().toUtc()),
      ),
    );
  }

  /// Update the sync status of a photo.
  Future<void> updateSyncStatus(String photoId, String status) async {
    await (_db.update(
      _db.photos,
    )..where((p) => p.photoId.equals(photoId))).write(
      PhotosCompanion(
        syncStatus: Value(status),
        updatedAt: Value(DateTime.now().toUtc()),
      ),
    );
  }

  /// Get photos that need to be synced (PENDING or FAILED).
  Future<List<Photo>> getPhotosToSync() async {
    return (_db.select(_db.photos)
          ..where(
            (p) =>
                p.syncStatus.equals('PENDING') | p.syncStatus.equals('FAILED'),
          )
          ..orderBy([
            (p) =>
                OrderingTerm(expression: p.timestamp, mode: OrderingMode.asc),
          ]))
        .get();
  }

  /// Delete a single photo by ID.
  ///
  /// Returns the number of rows deleted (0 or 1).
  /// IMPORTANT: Caller must delete the photo file from disk separately.
  Future<int> deletePhoto(String photoId) async {
    return (_db.delete(
      _db.photos,
    )..where((p) => p.photoId.equals(photoId))).go();
  }

  /// Delete all photos for a session.
  ///
  /// Returns the number of rows deleted.
  /// Used as cascade step before session deletion.
  Future<int> deletePhotosBySession(String sessionId) async {
    return (_db.delete(
      _db.photos,
    )..where((p) => p.sessionId.equals(sessionId))).go();
  }

  /// Delete all photos across all sessions.
  ///
  /// Returns the number of rows deleted.
  Future<int> deleteAllPhotos() async {
    return _db.delete(_db.photos).go();
  }
}
