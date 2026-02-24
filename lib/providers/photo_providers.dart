// ===========================================================================
// file: lib/providers/photo_providers.dart
// purpose: Riverpod providers for photo-related state and services.
//
// Provides reactive access to photos for the UI layer:
//   - photoServiceProvider: singleton PhotoService instance
//   - sessionPhotosProvider: stream of photos for a specific session
//   - allPhotosProvider: stream of all photos (newest first)
//   - photoCountProvider: total number of photos
//   - photoStorageInfoProvider: combined count and size info
//
// See: ADR-0018 (Photo Storage Architecture)
// ===========================================================================

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../database/app_database.dart';
import '../services/photo_service.dart';
import 'database_provider.dart';

/// Provides the singleton PhotoService instance.
final photoServiceProvider = Provider<PhotoService>((ref) {
  return PhotoService();
});

/// Watches photos for a specific session as a reactive stream.
///
/// Usage: `ref.watch(sessionPhotosProvider('session-id'))`
final sessionPhotosProvider = StreamProvider.family<List<Photo>, String>((
  ref,
  sessionId,
) {
  final photoDao = ref.watch(photoDaoProvider);
  return photoDao.watchPhotosForSession(sessionId);
});

/// Watches all photos as a reactive stream, ordered newest first.
final allPhotosProvider = StreamProvider<List<Photo>>((ref) {
  final photoDao = ref.watch(photoDaoProvider);
  return photoDao.watchAllPhotos();
});

/// Provides the total number of photos.
final photoCountProvider = FutureProvider<int>((ref) async {
  final photoDao = ref.watch(photoDaoProvider);
  return photoDao.getPhotoCount();
});

/// Combined photo storage info: count and total size in bytes.
class PhotoStorageInfo {
  final int count;
  final int totalSizeBytes;

  const PhotoStorageInfo({required this.count, required this.totalSizeBytes});

  /// Format the total size as a human-readable string.
  String get formattedSize {
    if (totalSizeBytes < 1024) return '$totalSizeBytes B';
    if (totalSizeBytes < 1024 * 1024) {
      return '${(totalSizeBytes / 1024).toStringAsFixed(1)} KB';
    }
    return '${(totalSizeBytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }
}

/// Provides photo storage info (count + total size).
final photoStorageInfoProvider = FutureProvider<PhotoStorageInfo>((ref) async {
  final photoDao = ref.watch(photoDaoProvider);
  final count = await photoDao.getPhotoCount();
  final totalSize = await photoDao.getTotalPhotoSize();
  return PhotoStorageInfo(count: count, totalSizeBytes: totalSize);
});
