// ===========================================================================
// file: lib/services/model_download_service.dart
// purpose: Downloads and verifies the Zipformer STT model files.
//
// Architecture (ADR-0015):
//   Model download is lazy — triggered on first voice activation, not at
//   app install. The encoder is ~68MB, so we gate downloads on WiFi when
//   total size >20MB. Downloads include SHA-256 verification and resume
//   capability via HTTP Range headers.
//
//   Model files are stored in getApplicationSupportDirectory()/zipformer/,
//   which is app-private, not backed up, and cleaned up on uninstall.
//
// See: ADR-0015 (Voice Mode Architecture)
// ===========================================================================

import 'dart:async';
import 'dart:io';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:crypto/crypto.dart';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';

/// Metadata for a single model file to download.
class ModelFileInfo {
  /// Display name for the file.
  final String name;

  /// Remote URL to download from.
  final String url;

  /// Expected SHA-256 checksum (hex string) for verification.
  final String sha256;

  /// Expected file size in bytes (for progress calculation).
  final int expectedSize;

  /// Creates model file metadata.
  const ModelFileInfo({
    required this.name,
    required this.url,
    required this.sha256,
    required this.expectedSize,
  });
}

/// Status of a model download operation.
enum ModelDownloadStatus {
  /// No download in progress; model may or may not be present.
  idle,

  /// Currently downloading model files.
  downloading,

  /// Verifying downloaded file checksums.
  verifying,

  /// Download completed and verified successfully.
  completed,

  /// Download failed (see error message).
  failed,
}

/// Progress state for a model download.
class ModelDownloadProgress {
  /// Current status of the download.
  final ModelDownloadStatus status;

  /// Overall progress from 0.0 to 1.0.
  final double progress;

  /// Name of the file currently being downloaded.
  final String? currentFile;

  /// Error message if status is [ModelDownloadStatus.failed].
  final String? error;

  /// Creates a download progress state.
  const ModelDownloadProgress({
    required this.status,
    this.progress = 0.0,
    this.currentFile,
    this.error,
  });
}

/// Service that manages STT model file downloads and verification.
///
/// Provides progress reporting via [downloadProgress] stream, WiFi-only
/// gating for large downloads, and SHA-256 checksum verification.
class ModelDownloadService {
  final Dio _dio;
  final Connectivity _connectivity;

  StreamController<ModelDownloadProgress>? _progressController;
  CancelToken? _cancelToken;

  /// The Zipformer model files to download from HuggingFace.
  static const modelFiles = [
    ModelFileInfo(
      name: 'encoder',
      url:
          'https://huggingface.co/csukuangfj/sherpa-onnx-streaming-zipformer-en-20M-2023-02-17/resolve/main/encoder-epoch-99-avg-1-chunk-16-left-128.int8.onnx',
      sha256: '', // Populated after first verified download
      expectedSize: 68000000,
    ),
    ModelFileInfo(
      name: 'decoder',
      url:
          'https://huggingface.co/csukuangfj/sherpa-onnx-streaming-zipformer-en-20M-2023-02-17/resolve/main/decoder-epoch-99-avg-1-chunk-16-left-128.onnx',
      sha256: '',
      expectedSize: 2000000,
    ),
    ModelFileInfo(
      name: 'joiner',
      url:
          'https://huggingface.co/csukuangfj/sherpa-onnx-streaming-zipformer-en-20M-2023-02-17/resolve/main/joiner-epoch-99-avg-1-chunk-16-left-128.int8.onnx',
      sha256: '',
      expectedSize: 254000,
    ),
    ModelFileInfo(
      name: 'tokens',
      url:
          'https://huggingface.co/csukuangfj/sherpa-onnx-streaming-zipformer-en-20M-2023-02-17/resolve/main/tokens.txt',
      sha256: '',
      expectedSize: 5000,
    ),
  ];

  /// Total expected download size in bytes (all model files).
  static int get totalExpectedSize =>
      modelFiles.fold(0, (sum, f) => sum + f.expectedSize);

  /// Creates a model download service.
  ///
  /// [dio] and [connectivity] are injectable for testing.
  ModelDownloadService({Dio? dio, Connectivity? connectivity})
    : _dio = dio ?? Dio(),
      _connectivity = connectivity ?? Connectivity();

  /// Stream of download progress updates.
  Stream<ModelDownloadProgress> get downloadProgress {
    _progressController ??= StreamController<ModelDownloadProgress>.broadcast();
    return _progressController!.stream;
  }

  /// Check if all model files exist in the app support directory.
  // coverage:ignore-start
  Future<bool> isModelDownloaded() async {
    final modelDir = await _getModelDirectory();
    if (!modelDir.existsSync()) return false;

    for (final fileInfo in modelFiles) {
      final file = File('${modelDir.path}/${_fileNameFromUrl(fileInfo.url)}');
      if (!file.existsSync()) return false;
    }
    return true;
  }
  // coverage:ignore-end

  /// Check if the device is on WiFi.
  Future<bool> isOnWifi() async {
    final results = await _connectivity.checkConnectivity();
    return results.contains(ConnectivityResult.wifi);
  }

  /// Download all model files.
  ///
  /// Reports progress via [downloadProgress] stream. Returns the model
  /// directory path on success, throws on failure.
  ///
  /// If [forceOverCellular] is true, skips the WiFi-only gate.
  // coverage:ignore-start
  Future<String> downloadModel({bool forceOverCellular = false}) async {
    _progressController ??= StreamController<ModelDownloadProgress>.broadcast();
    _cancelToken = CancelToken();

    try {
      // WiFi gate for large downloads.
      if (!forceOverCellular) {
        final onWifi = await isOnWifi();
        if (!onWifi) {
          _emitProgress(
            const ModelDownloadProgress(
              status: ModelDownloadStatus.failed,
              error:
                  'WiFi required for model download. '
                  'Connect to WiFi or choose "Download Now" to use cellular.',
            ),
          );
          throw StateError('WiFi required for model download');
        }
      }

      final modelDir = await _getModelDirectory();
      if (!modelDir.existsSync()) {
        modelDir.createSync(recursive: true);
      }

      var totalDownloaded = 0;

      for (var i = 0; i < modelFiles.length; i++) {
        final fileInfo = modelFiles[i];
        final fileName = _fileNameFromUrl(fileInfo.url);
        final filePath = '${modelDir.path}/$fileName';
        final file = File(filePath);

        // Skip already-downloaded files.
        if (file.existsSync() && file.lengthSync() == fileInfo.expectedSize) {
          totalDownloaded += fileInfo.expectedSize;
          continue;
        }

        _emitProgress(
          ModelDownloadProgress(
            status: ModelDownloadStatus.downloading,
            progress: totalDownloaded / totalExpectedSize,
            currentFile: fileInfo.name,
          ),
        );

        // Download with resume support.
        var startByte = 0;
        if (file.existsSync()) {
          startByte = file.lengthSync();
          totalDownloaded += startByte;
        }

        await _dio.download(
          fileInfo.url,
          filePath,
          cancelToken: _cancelToken,
          deleteOnError: false,
          options: startByte > 0
              ? Options(headers: {'Range': 'bytes=$startByte-'})
              : null,
          onReceiveProgress: (received, total) {
            final fileProgress = startByte + received;
            final overallProgress =
                (totalDownloaded + received) / totalExpectedSize;
            _emitProgress(
              ModelDownloadProgress(
                status: ModelDownloadStatus.downloading,
                progress: overallProgress.clamp(0.0, 1.0),
                currentFile: fileInfo.name,
              ),
            );

            // Update total for the current file when done.
            if (total > 0 && received >= total) {
              totalDownloaded += fileProgress - startByte;
            }
          },
        );

        // Count this file as fully downloaded.
        if (file.existsSync()) {
          totalDownloaded = totalDownloaded - startByte + file.lengthSync();
        }
      }

      _emitProgress(
        const ModelDownloadProgress(
          status: ModelDownloadStatus.verifying,
          progress: 1.0,
        ),
      );

      // Verify downloaded files: existence, non-zero size, and SHA-256 when
      // checksums are populated. Empty sha256 fields log a warning in debug
      // mode — populate them from the first successful on-device download.
      for (final fileInfo in modelFiles) {
        final fileName = _fileNameFromUrl(fileInfo.url);
        final file = File('${modelDir.path}/$fileName');
        if (!file.existsSync() || file.lengthSync() == 0) {
          throw StateError('Downloaded file is empty: $fileName');
        }
        if (fileInfo.sha256.isNotEmpty) {
          final match = await _verifySha256(file, fileInfo.sha256);
          if (!match) {
            // Delete corrupt file so next attempt re-downloads.
            file.deleteSync();
            throw StateError(
              'SHA-256 verification failed for $fileName. '
              'File deleted — retry the download.',
            );
          }
        } else {
          debugLog(
            'No SHA-256 for $fileName — skipping integrity check. '
            'Populate ModelFileInfo.sha256 before production release.',
          );
        }
      }

      _emitProgress(
        const ModelDownloadProgress(
          status: ModelDownloadStatus.completed,
          progress: 1.0,
        ),
      );

      return modelDir.path;
    } on DioException catch (e) {
      if (e.type == DioExceptionType.cancel) {
        _emitProgress(
          const ModelDownloadProgress(
            status: ModelDownloadStatus.failed,
            error: 'Download cancelled.',
          ),
        );
        rethrow;
      }
      _emitProgress(
        ModelDownloadProgress(
          status: ModelDownloadStatus.failed,
          error: 'Download failed: ${e.message}',
        ),
      );
      rethrow;
    } on StateError {
      rethrow;
    } catch (e) {
      _emitProgress(
        ModelDownloadProgress(
          status: ModelDownloadStatus.failed,
          error: 'Download failed: $e',
        ),
      );
      rethrow;
    }
  }

  // coverage:ignore-end

  /// Cancel an in-progress download.
  void cancelDownload() {
    _cancelToken?.cancel('User cancelled download');
    _cancelToken = null;
  }

  /// Get the model directory path.
  // coverage:ignore-start
  Future<Directory> _getModelDirectory() async {
    final appDir = await getApplicationSupportDirectory();
    return Directory('${appDir.path}/zipformer');
  }
  // coverage:ignore-end

  /// Extract the filename from a URL.
  static String _fileNameFromUrl(String url) {
    return Uri.parse(url).pathSegments.last;
  }

  /// Verify a file's SHA-256 checksum.
  ///
  /// Reads the file and computes SHA-256. For the 68MB encoder file this is
  /// acceptable on the target device (Galaxy S21 Ultra, 6GB RAM).
  /// Returns true if the computed hash matches [expected].
  static Future<bool> _verifySha256(File file, String expected) async {
    final bytes = await file.readAsBytes();
    final digest = sha256.convert(bytes);
    return digest.toString() == expected.toLowerCase();
  }

  /// Emit a progress update.
  void _emitProgress(ModelDownloadProgress progress) {
    if (_progressController != null && !_progressController!.isClosed) {
      _progressController!.add(progress);
    }
  }

  /// Release resources.
  void dispose() {
    cancelDownload();
    _progressController?.close();
    _progressController = null;
    _dio.close();
  }

  /// Log a debug message (debug builds only).
  @visibleForTesting
  static void debugLog(String message) {
    if (kDebugMode) {
      debugPrint('[ModelDownload] $message');
    }
  }
}
