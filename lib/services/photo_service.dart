// ===========================================================================
// file: lib/services/photo_service.dart
// purpose: Photo capture, EXIF stripping, compression, and file management.
//
// Handles the full photo pipeline:
//   1. Camera/gallery capture via image_picker
//   2. EXIF strip + resize + compress via image package in a background isolate
//   3. File storage in app-private directory with canonical paths
//   4. File deletion and storage calculation
//
// See: ADR-0018 (Photo Storage Architecture)
// ===========================================================================

import 'dart:io';
import 'dart:isolate';

import 'package:flutter/foundation.dart';
import 'package:image/image.dart' as img;
import 'package:image_picker/image_picker.dart';
import 'package:path_provider/path_provider.dart';
import 'package:path/path.dart' as p;

/// Result of processing a photo (after EXIF strip + resize + compress).
class ProcessedPhoto {
  /// The processed file on disk.
  final File file;

  /// Image width in pixels after processing.
  final int width;

  /// Image height in pixels after processing.
  final int height;

  /// File size in bytes after processing.
  final int fileSizeBytes;

  const ProcessedPhoto({
    required this.file,
    required this.width,
    required this.height,
    required this.fileSizeBytes,
  });
}

/// UUID regex for path traversal prevention (ADR-0018).
final _uuidRegex = RegExp(r'^[a-f0-9\-]+$');

/// Maximum dimension (width or height) for processed photos.
const _maxDimension = 2048;

/// JPEG quality for processed photos (85% is visually lossless).
const _jpegQuality = 85;

/// Manages photo capture, processing, and file operations.
///
/// All image processing runs in a background isolate to avoid janking
/// the UI thread. Files are stored in the app-private support directory
/// under `photos/{sessionId}/{photoId}.jpg`.
class PhotoService {
  final ImagePicker _picker;

  /// Create a PhotoService with the given ImagePicker.
  ///
  /// In tests, pass a mock ImagePicker.
  PhotoService({ImagePicker? picker}) : _picker = picker ?? ImagePicker();

  /// Take a photo using the device camera.
  ///
  /// Returns the raw file from the camera, or null if the user cancelled.
  Future<File?> takePhoto() async {
    final picked = await _picker.pickImage(source: ImageSource.camera);
    if (picked == null) return null;
    return File(picked.path);
  }

  /// Pick a photo from the device gallery.
  ///
  /// Returns the raw file from the gallery, or null if the user cancelled.
  Future<File?> pickFromGallery() async {
    final picked = await _picker.pickImage(source: ImageSource.gallery);
    if (picked == null) return null;
    return File(picked.path);
  }

  /// Process a raw photo: strip EXIF, resize, compress, and save.
  ///
  /// Re-encoding via the `image` package inherently strips all EXIF
  /// metadata (GPS, device info, timestamps). The same pass handles
  /// resize (max 2048px longest edge) and JPEG compression (85%).
  ///
  /// Processing runs in a background isolate to avoid blocking the UI.
  ///
  /// Returns [ProcessedPhoto] with the output file and dimensions,
  /// or null if processing fails.
  Future<ProcessedPhoto?> processAndSave(
    File rawFile,
    String sessionId,
    String photoId,
  ) async {
    final baseDir = await getApplicationSupportDirectory();
    final outputPath = canonicalPath(baseDir.path, sessionId, photoId);

    // Read raw bytes on the main isolate (File I/O is fast).
    final rawBytes = await rawFile.readAsBytes();

    // Process in background isolate (decode + resize + encode is CPU-heavy).
    final result = await Isolate.run(() {
      return _processImageBytes(rawBytes, outputPath);
    });

    if (result == null) return null;

    final outputFile = File(outputPath);
    return ProcessedPhoto(
      file: outputFile,
      width: result.width,
      height: result.height,
      fileSizeBytes: result.fileSizeBytes,
    );
  }

  /// Build the canonical file path for a photo.
  ///
  /// Validates both [sessionId] and [photoId] against UUID regex
  /// to prevent path traversal attacks (ADR-0018).
  ///
  /// Throws [ArgumentError] if either ID fails validation.
  static String canonicalPath(
    String baseDir,
    String sessionId,
    String photoId,
  ) {
    if (!_uuidRegex.hasMatch(sessionId)) {
      throw ArgumentError('Invalid sessionId: $sessionId');
    }
    if (!_uuidRegex.hasMatch(photoId)) {
      throw ArgumentError('Invalid photoId: $photoId');
    }
    return p.join(baseDir, 'photos', sessionId, '$photoId.jpg');
  }

  /// Delete a single photo file from disk.
  ///
  /// Validates that the resolved path is within the app's photos directory
  /// to prevent arbitrary file deletion via a corrupted DB record.
  /// No-op if the file doesn't exist, is outside the photos directory,
  /// or platform bindings are unavailable.
  Future<void> deletePhotoFile(String localPath) async {
    final Directory baseDir;
    try {
      baseDir = await getApplicationSupportDirectory();
    } on Exception {
      return; // Platform bindings unavailable — refuse to delete.
    } on Error {
      return; // FlutterError when bindings not initialized (e.g., unit tests).
    }
    final photosBase = p.join(baseDir.path, 'photos');
    // Normalize both paths for safe comparison.
    final normalizedPath = p.normalize(localPath);
    final normalizedBase = p.normalize(photosBase);
    if (!normalizedPath.startsWith(normalizedBase)) {
      return; // Path outside photos directory — refuse to delete.
    }
    final file = File(normalizedPath);
    if (await file.exists()) {
      await file.delete();
    }
  }

  /// Delete all photo files for a session.
  ///
  /// Removes the entire `photos/{sessionId}/` directory.
  /// No-op if the directory doesn't exist.
  Future<void> deleteSessionPhotos(String sessionId) async {
    if (!_uuidRegex.hasMatch(sessionId)) return;

    final Directory baseDir;
    try {
      baseDir = await getApplicationSupportDirectory();
    } on Exception {
      return; // Platform bindings unavailable — skip file cleanup.
    } on Error {
      return; // FlutterError when bindings not initialized (e.g., unit tests).
    }
    final sessionDir = Directory(p.join(baseDir.path, 'photos', sessionId));
    if (await sessionDir.exists()) {
      await sessionDir.delete(recursive: true);
    }
  }

  /// Delete all photo files from disk.
  ///
  /// Removes the entire `photos/` directory.
  /// No-op if the directory doesn't exist.
  Future<void> deleteAllPhotos() async {
    final baseDir = await getApplicationSupportDirectory();
    final photosDir = Directory(p.join(baseDir.path, 'photos'));
    if (await photosDir.exists()) {
      await photosDir.delete(recursive: true);
    }
  }

  /// Calculate the total size of all photos on disk (bytes).
  Future<int> calculateTotalSize() async {
    final baseDir = await getApplicationSupportDirectory();
    final photosDir = Directory(p.join(baseDir.path, 'photos'));
    if (!await photosDir.exists()) return 0;

    int totalSize = 0;
    await for (final entity in photosDir.list(recursive: true)) {
      if (entity is File) {
        totalSize += await entity.length();
      }
    }
    return totalSize;
  }
}

/// Internal class for isolate communication (must be top-level or static).
class _ProcessResult {
  final int width;
  final int height;
  final int fileSizeBytes;

  const _ProcessResult({
    required this.width,
    required this.height,
    required this.fileSizeBytes,
  });
}

/// Process image bytes in a background isolate.
///
/// Decodes, resizes (max 2048px), and re-encodes as JPEG (85%).
/// Re-encoding inherently strips all EXIF metadata.
/// Returns null if decoding fails.
_ProcessResult? _processImageBytes(Uint8List rawBytes, String outputPath) {
  final decoded = img.decodeImage(rawBytes);
  if (decoded == null) return null;

  // Resize if either dimension exceeds the maximum.
  img.Image processed;
  if (decoded.width > _maxDimension || decoded.height > _maxDimension) {
    if (decoded.width >= decoded.height) {
      processed = img.copyResize(decoded, width: _maxDimension);
    } else {
      processed = img.copyResize(decoded, height: _maxDimension);
    }
  } else {
    processed = decoded;
  }

  // Encode as JPEG (strips EXIF metadata as a side effect).
  final jpegBytes = img.encodeJpg(processed, quality: _jpegQuality);

  // Ensure the output directory exists.
  final outputDir = Directory(p.dirname(outputPath));
  if (!outputDir.existsSync()) {
    outputDir.createSync(recursive: true);
  }

  // Write to disk.
  File(outputPath).writeAsBytesSync(jpegBytes);

  return _ProcessResult(
    width: processed.width,
    height: processed.height,
    fileSizeBytes: jpegBytes.length,
  );
}
