// ===========================================================================
// file: lib/services/llm_model_download_service.dart
// purpose: Downloads and verifies the local LLM GGUF model file.
//
// Follows the same pattern as ModelDownloadService (STT model) but with:
//   - Single large GGUF file (~380MB) instead of multiple small files
//   - Chunked SHA-256 verification (openRead, not readAsBytes) to avoid OOM
//   - Non-empty SHA-256 checksum (not the empty-placeholder pattern)
//
// Reuses ModelFileInfo, ModelDownloadStatus, and ModelDownloadProgress
// from model_download_service.dart to avoid type duplication.
//
// See: ADR-0017 (Local LLM Layer Architecture)
// ===========================================================================

import 'dart:async';
import 'dart:io';
import 'dart:isolate';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:crypto/crypto.dart';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';

import 'model_download_service.dart'
    show ModelFileInfo, ModelDownloadStatus, ModelDownloadProgress;

/// Service that manages LLM GGUF model download and verification.
///
/// Provides progress reporting via [downloadProgress] stream, WiFi-only
/// gating for the ~380MB download, chunked SHA-256 verification, and
/// resume capability via HTTP Range headers.
class LlmModelDownloadService {
  final Dio _dio;
  final Connectivity _connectivity;

  StreamController<ModelDownloadProgress>? _progressController;
  CancelToken? _cancelToken;

  /// The LLM model file to download from HuggingFace.
  ///
  /// SHA-256 checksum is pre-verified from the canonical HuggingFace release.
  /// This MUST be non-empty before any production release.
  static const modelFile = ModelFileInfo(
    name: 'qwen2.5-0.5b-instruct-q4_k_m',
    url:
        'https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf',
    sha256: '74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db',
    expectedSize: 491400032,
  );

  /// Creates an LLM model download service.
  ///
  /// [dio] and [connectivity] are injectable for testing.
  LlmModelDownloadService({Dio? dio, Connectivity? connectivity})
    : _dio = dio ?? Dio(),
      _connectivity = connectivity ?? Connectivity();

  /// Stream of download progress updates.
  Stream<ModelDownloadProgress> get downloadProgress {
    _progressController ??= StreamController<ModelDownloadProgress>.broadcast();
    return _progressController!.stream;
  }

  /// Check if the LLM model file exists in the app support directory.
  // coverage:ignore-start
  Future<bool> isModelDownloaded() async {
    final modelDir = await _getModelDirectory();
    if (!modelDir.existsSync()) return false;

    final file = File('${modelDir.path}/${_fileNameFromUrl(modelFile.url)}');
    return file.existsSync() && file.lengthSync() == modelFile.expectedSize;
  }
  // coverage:ignore-end

  /// Get the path to the downloaded model file (or where it would be).
  // coverage:ignore-start
  Future<String> getModelFilePath() async {
    final modelDir = await _getModelDirectory();
    return '${modelDir.path}/${_fileNameFromUrl(modelFile.url)}';
  }
  // coverage:ignore-end

  /// Check if the device is on WiFi.
  Future<bool> isOnWifi() async {
    final results = await _connectivity.checkConnectivity();
    return results.contains(ConnectivityResult.wifi);
  }

  /// Download the LLM model file.
  ///
  /// Reports progress via [downloadProgress] stream. Returns the model
  /// file path on success, throws on failure.
  ///
  /// If [forceOverCellular] is true, skips the WiFi-only gate.
  // coverage:ignore-start
  Future<String> downloadModel({bool forceOverCellular = false}) async {
    _progressController ??= StreamController<ModelDownloadProgress>.broadcast();
    _cancelToken = CancelToken();

    try {
      // WiFi gate for the ~380MB download.
      if (!forceOverCellular) {
        final onWifi = await isOnWifi();
        if (!onWifi) {
          _emitProgress(
            const ModelDownloadProgress(
              status: ModelDownloadStatus.failed,
              error:
                  'WiFi required for model download (~490 MB). '
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

      final fileName = _fileNameFromUrl(modelFile.url);
      final filePath = '${modelDir.path}/$fileName';
      final file = File(filePath);

      // Skip if already downloaded and correct size.
      if (file.existsSync() && file.lengthSync() == modelFile.expectedSize) {
        _emitProgress(
          const ModelDownloadProgress(
            status: ModelDownloadStatus.completed,
            progress: 1.0,
          ),
        );
        return filePath;
      }

      // Resume support: check existing partial file.
      var startByte = 0;
      if (file.existsSync()) {
        startByte = file.lengthSync();
      }

      _emitProgress(
        ModelDownloadProgress(
          status: ModelDownloadStatus.downloading,
          progress: startByte / modelFile.expectedSize,
          currentFile: modelFile.name,
        ),
      );

      await _dio.download(
        modelFile.url,
        filePath,
        cancelToken: _cancelToken,
        deleteOnError: false,
        options: startByte > 0
            ? Options(headers: {'Range': 'bytes=$startByte-'})
            : null,
        onReceiveProgress: (received, total) {
          final overallProgress =
              (startByte + received) / modelFile.expectedSize;
          _emitProgress(
            ModelDownloadProgress(
              status: ModelDownloadStatus.downloading,
              progress: overallProgress.clamp(0.0, 1.0),
              currentFile: modelFile.name,
            ),
          );
        },
      );

      // Verify download.
      _emitProgress(
        const ModelDownloadProgress(
          status: ModelDownloadStatus.verifying,
          progress: 1.0,
        ),
      );

      if (!file.existsSync() || file.lengthSync() == 0) {
        throw StateError('Downloaded file is empty: $fileName');
      }

      // Chunked SHA-256 verification — does NOT read entire file into memory.
      final checksumMatch = await _verifyChunkedSha256(file, modelFile.sha256);
      if (!checksumMatch) {
        file.deleteSync();
        throw StateError(
          'SHA-256 verification failed for $fileName. '
          'File deleted — retry the download.',
        );
      }

      _emitProgress(
        const ModelDownloadProgress(
          status: ModelDownloadStatus.completed,
          progress: 1.0,
        ),
      );

      return filePath;
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
    return Directory('${appDir.path}/llm');
  }
  // coverage:ignore-end

  /// The model file name extracted from the download URL.
  static String get modelFileName => _fileNameFromUrl(modelFile.url);

  /// Extract the filename from a URL.
  static String _fileNameFromUrl(String url) {
    return Uri.parse(url).pathSegments.last;
  }

  /// Chunked SHA-256 verification in a background isolate.
  ///
  /// Reads the file in chunks via [openRead] and feeds them to the SHA-256
  /// digest incrementally. This avoids allocating the entire file (~380MB)
  /// on the Dart heap, preventing OOM on mobile devices.
  ///
  /// Runs in [Isolate.run] so the main UI thread stays responsive during
  /// the ~400MB hash computation.
  ///
  /// Returns true if the computed hash matches [expected].
  static Future<bool> _verifyChunkedSha256(File file, String expected) async {
    if (expected.isEmpty) {
      debugLog('No SHA-256 checksum — skipping verification');
      return true;
    }

    final filePath = file.path;
    final result = await Isolate.run(() async {
      final f = File(filePath);
      final output = AccumulatorSink<Digest>();
      final input = sha256.startChunkedConversion(output);

      await for (final chunk in f.openRead()) {
        input.add(chunk);
      }
      input.close();

      return output.events.single.toString();
    });

    return result == expected.toLowerCase();
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
      debugPrint('[LlmModelDownload] $message');
    }
  }
}

/// Incremental sink for collecting digest output.
///
/// Used by [_verifyChunkedSha256] to receive the final [Digest] from
/// the chunked hash conversion.
class AccumulatorSink<T> implements Sink<T> {
  /// The collected events.
  final List<T> events = [];

  @override
  void add(T event) => events.add(event);

  @override
  void close() {}

  /// Get the single accumulated event.
  T get single => events.single;
}
