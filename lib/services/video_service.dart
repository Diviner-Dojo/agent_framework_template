// coverage:ignore-file — platform video pipeline (ffmpeg, video_thumbnail, image_picker).
// ===========================================================================
// file: lib/services/video_service.dart
// purpose: Video capture, metadata stripping, thumbnail generation, and file
//          management.
//
// Handles the full video pipeline:
//   1. Camera/gallery capture via image_picker
//   2. Metadata strip via ffmpeg_kit_flutter (-map_metadata -1 -codec copy)
//   3. Thumbnail generation via video_thumbnail (320x180 JPEG 70%)
//   4. File storage in app-private directory with canonical paths
//   5. File deletion and storage calculation
//
// See: ADR-0021 (Video Capture Architecture)
// ===========================================================================

import 'dart:io';
import 'dart:typed_data';

import 'package:ffmpeg_kit_min_gpl/ffmpeg_kit.dart';
import 'package:ffmpeg_kit_min_gpl/return_code.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:video_thumbnail/video_thumbnail.dart' as vt;

/// Result of processing a video (after metadata strip + thumbnail generation).
class ProcessedVideo {
  /// The processed video file on disk (metadata stripped).
  final File file;

  /// The thumbnail JPEG file on disk.
  final File thumbnail;

  /// Video duration in seconds.
  final int durationSeconds;

  /// File size in bytes after processing.
  final int fileSizeBytes;

  /// Video width in pixels (null if unavailable).
  final int? width;

  /// Video height in pixels (null if unavailable).
  final int? height;

  const ProcessedVideo({
    required this.file,
    required this.thumbnail,
    required this.durationSeconds,
    required this.fileSizeBytes,
    this.width,
    this.height,
  });
}

/// UUID regex for path traversal prevention (ADR-0021, same as ADR-0018).
final _uuidRegex = RegExp(r'^[a-f0-9\-]+$');

/// Maximum recording duration in seconds.
const maxDurationSeconds = 60;

/// Maximum post-capture file size in bytes (100 MB).
const maxFileSizeBytes = 100 * 1024 * 1024;

/// Thumbnail width in pixels.
const thumbnailWidth = 320;

/// Thumbnail height in pixels.
const thumbnailHeight = 180;

/// Thumbnail JPEG quality (0-100).
const thumbnailQuality = 70;

/// Storage warning threshold in bytes (2 GB).
const storageWarningBytes = 2 * 1024 * 1024 * 1024;

/// Manages video capture, processing, and file operations.
///
/// Metadata stripping uses ffmpeg_kit_flutter with `-map_metadata -1 -codec
/// copy` to strip GPS/device info without re-encoding. Thumbnail generation
/// uses the video_thumbnail package for a 320x180 JPEG at 70% quality.
///
/// Files are stored in the app-private support directory under
/// `videos/{sessionId}/{videoId}.mp4` (video) and
/// `videos/{sessionId}/{videoId}_thumb.jpg` (thumbnail).
class VideoService {
  final ImagePicker _picker;

  /// Create a VideoService with the given ImagePicker.
  ///
  /// In tests, pass a mock ImagePicker.
  VideoService({ImagePicker? picker}) : _picker = picker ?? ImagePicker();

  /// Record a video using the device camera.
  ///
  /// Enforces a 60-second maximum duration (ADR-0021 §2).
  /// Returns the raw file from the camera, or null if the user cancelled.
  Future<File?> recordVideo() async {
    final picked = await _picker.pickVideo(
      source: ImageSource.camera,
      maxDuration: const Duration(seconds: maxDurationSeconds),
    );
    if (picked == null) return null;
    return File(picked.path);
  }

  /// Pick a video from the device gallery.
  ///
  /// Returns the raw file from the gallery, or null if the user cancelled.
  Future<File?> pickFromGallery() async {
    final picked = await _picker.pickVideo(source: ImageSource.gallery);
    if (picked == null) return null;
    return File(picked.path);
  }

  /// Process a raw video: strip metadata, generate thumbnail, and save.
  ///
  /// Metadata stripping uses ffmpeg with `-map_metadata -1 -codec copy`
  /// to remove GPS/device info without re-encoding the video stream
  /// (ADR-0021 §3). This is a container-level operation that preserves
  /// video/audio quality while clearing container metadata fields.
  ///
  /// Returns [ProcessedVideo] with output files and metadata,
  /// or null if processing fails (ffmpeg error, file too large, etc.).
  Future<ProcessedVideo?> processAndSave(
    File rawFile,
    String sessionId,
    String videoId,
  ) async {
    final baseDir = await getApplicationSupportDirectory();
    final videoPath = canonicalVideoPath(baseDir.path, sessionId, videoId);
    final thumbPath = canonicalThumbnailPath(baseDir.path, sessionId, videoId);

    // Ensure output directory exists.
    final outputDir = Directory(p.dirname(videoPath));
    if (!await outputDir.exists()) {
      await outputDir.create(recursive: true);
    }

    // Check file size before processing.
    final rawSize = await rawFile.length();
    if (rawSize > maxFileSizeBytes) {
      return null; // File exceeds 100MB cap.
    }

    // Strip metadata via ffmpeg (-map_metadata -1 removes all metadata,
    // -codec copy avoids re-encoding).
    // Uses executeWithArguments() to avoid shell interpolation of file paths
    // (prevents command injection from paths with quotes/spaces/metacharacters).
    final session = await FFmpegKit.executeWithArguments([
      '-i',
      rawFile.path,
      '-map_metadata',
      '-1',
      '-codec',
      'copy',
      '-y',
      videoPath,
    ]);
    final returnCode = await session.getReturnCode();
    if (!ReturnCode.isSuccess(returnCode)) {
      return null; // ffmpeg failed — caller should handle gracefully.
    }

    final processedFile = File(videoPath);
    if (!await processedFile.exists()) {
      return null; // Output file not created.
    }

    // Generate thumbnail (320x180 JPEG 70%).
    // video_thumbnail runs native-side, already async.
    final Uint8List? thumbBytes = await vt.VideoThumbnail.thumbnailData(
      video: videoPath,
      imageFormat: vt.ImageFormat.JPEG,
      maxWidth: thumbnailWidth,
      maxHeight: thumbnailHeight,
      quality: thumbnailQuality,
    );

    if (thumbBytes == null || thumbBytes.isEmpty) {
      // Thumbnail failed — clean up video file and bail.
      await processedFile.delete();
      return null;
    }

    // Write thumbnail to disk.
    final thumbFile = File(thumbPath);
    await thumbFile.writeAsBytes(thumbBytes);

    // Get processed file size.
    final fileSizeBytes = await processedFile.length();

    // Estimate duration from raw file (ffmpeg probe would be more accurate,
    // but we accept the image_picker-reported duration at the caller level).
    // For now, return 0 — the caller provides the actual duration.
    return ProcessedVideo(
      file: processedFile,
      thumbnail: thumbFile,
      durationSeconds: 0, // Caller provides actual duration.
      fileSizeBytes: fileSizeBytes,
    );
  }

  /// Build the canonical file path for a video.
  ///
  /// Validates both [sessionId] and [videoId] against UUID regex
  /// to prevent path traversal attacks (ADR-0021).
  ///
  /// Throws [ArgumentError] if either ID fails validation.
  static String canonicalVideoPath(
    String baseDir,
    String sessionId,
    String videoId,
  ) {
    _validateId(sessionId, 'sessionId');
    _validateId(videoId, 'videoId');
    return p.join(baseDir, 'videos', sessionId, '$videoId.mp4');
  }

  /// Build the canonical file path for a video thumbnail.
  ///
  /// Validates both [sessionId] and [videoId] against UUID regex
  /// to prevent path traversal attacks (ADR-0021).
  ///
  /// Throws [ArgumentError] if either ID fails validation.
  static String canonicalThumbnailPath(
    String baseDir,
    String sessionId,
    String videoId,
  ) {
    _validateId(sessionId, 'sessionId');
    _validateId(videoId, 'videoId');
    return p.join(baseDir, 'videos', sessionId, '${videoId}_thumb.jpg');
  }

  /// Delete a single video file from disk.
  ///
  /// Validates that the resolved path is within the app's videos directory
  /// to prevent arbitrary file deletion via a corrupted DB record.
  /// No-op if the file doesn't exist or is outside the videos directory.
  Future<void> deleteVideoFile(String localPath) async {
    final Directory baseDir;
    try {
      baseDir = await getApplicationSupportDirectory();
    } on Exception {
      return; // Platform bindings unavailable — refuse to delete.
    } on Error {
      return; // FlutterError when bindings not initialized.
    }
    final videosBase = p.join(baseDir.path, 'videos');
    final normalizedPath = p.normalize(localPath);
    final normalizedBase = p.normalize(videosBase);
    if (!normalizedPath.startsWith(normalizedBase)) {
      return; // Path outside videos directory — refuse to delete.
    }
    final file = File(normalizedPath);
    if (await file.exists()) {
      await file.delete();
    }
  }

  /// Delete all video files for a session.
  ///
  /// Removes the entire `videos/{sessionId}/` directory (video + thumbnail).
  /// No-op if the directory doesn't exist.
  Future<void> deleteSessionVideos(String sessionId) async {
    if (!_uuidRegex.hasMatch(sessionId)) return;

    final Directory baseDir;
    try {
      baseDir = await getApplicationSupportDirectory();
    } on Exception {
      return; // Platform bindings unavailable — skip file cleanup.
    } on Error {
      return; // FlutterError when bindings not initialized.
    }
    final sessionDir = Directory(p.join(baseDir.path, 'videos', sessionId));
    if (await sessionDir.exists()) {
      await sessionDir.delete(recursive: true);
    }
  }

  /// Delete all video files from disk.
  ///
  /// Removes the entire `videos/` directory.
  /// No-op if the directory doesn't exist.
  Future<void> deleteAllVideos() async {
    final Directory baseDir;
    try {
      baseDir = await getApplicationSupportDirectory();
    } on Exception {
      return;
    } on Error {
      return;
    }
    final videosDir = Directory(p.join(baseDir.path, 'videos'));
    if (await videosDir.exists()) {
      await videosDir.delete(recursive: true);
    }
  }

  /// Calculate the total size of all videos on disk (bytes).
  Future<int> calculateTotalSize() async {
    final Directory baseDir;
    try {
      baseDir = await getApplicationSupportDirectory();
    } on Exception {
      return 0;
    } on Error {
      return 0;
    }
    final videosDir = Directory(p.join(baseDir.path, 'videos'));
    if (!await videosDir.exists()) return 0;

    int totalSize = 0;
    await for (final entity in videosDir.list(recursive: true)) {
      if (entity is File) {
        totalSize += await entity.length();
      }
    }
    return totalSize;
  }

  /// Validate an ID against UUID regex.
  static void _validateId(String id, String paramName) {
    if (!_uuidRegex.hasMatch(id)) {
      throw ArgumentError('Invalid $paramName: $id');
    }
  }
}
