// ===========================================================================
// file: lib/providers/video_providers.dart
// purpose: Riverpod providers for video-related state and services.
//
// Provides reactive access to videos for the UI layer:
//   - videoServiceProvider: singleton VideoService instance
//   - sessionVideosProvider: stream of videos for a specific session
//   - videoStorageInfoProvider: combined count and size info
//
// See: ADR-0021 (Video Capture Architecture)
// ===========================================================================

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../database/app_database.dart';
import '../services/video_service.dart';
import 'database_provider.dart';

/// Provides the singleton VideoService instance.
final videoServiceProvider = Provider<VideoService>((ref) {
  return VideoService();
});

/// Watches videos for a specific session as a reactive stream.
///
/// Usage: `ref.watch(sessionVideosProvider('session-id'))`
final sessionVideosProvider = StreamProvider.family<List<Video>, String>((
  ref,
  sessionId,
) {
  final videoDao = ref.watch(videoDaoProvider);
  return videoDao.watchVideosForSession(sessionId);
});

/// Provides the total number of videos.
final videoCountProvider = FutureProvider<int>((ref) async {
  final videoDao = ref.watch(videoDaoProvider);
  return videoDao.getVideoCount();
});

/// Combined video storage info: count and total size in bytes.
class VideoStorageInfo {
  /// Number of videos stored.
  final int count;

  /// Total size of all videos in bytes.
  final int totalSizeBytes;

  const VideoStorageInfo({required this.count, required this.totalSizeBytes});

  /// Format the total size as a human-readable string.
  String get formattedSize {
    if (totalSizeBytes < 1024) return '$totalSizeBytes B';
    if (totalSizeBytes < 1024 * 1024) {
      return '${(totalSizeBytes / 1024).toStringAsFixed(1)} KB';
    }
    if (totalSizeBytes < 1024 * 1024 * 1024) {
      return '${(totalSizeBytes / (1024 * 1024)).toStringAsFixed(1)} MB';
    }
    return '${(totalSizeBytes / (1024 * 1024 * 1024)).toStringAsFixed(1)} GB';
  }

  /// True if total size exceeds 2 GB warning threshold (ADR-0021 §2).
  bool get isOverWarningThreshold => totalSizeBytes >= storageWarningBytes;
}

/// Provides video storage info (count + total size).
final videoStorageInfoProvider = FutureProvider<VideoStorageInfo>((ref) async {
  final videoDao = ref.watch(videoDaoProvider);
  final count = await videoDao.getVideoCount();
  final totalSize = await videoDao.getTotalVideoSize();
  return VideoStorageInfo(count: count, totalSizeBytes: totalSize);
});
