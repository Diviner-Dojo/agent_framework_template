// ===========================================================================
// file: test/services/model_download_service_test.dart
// purpose: Tests for ModelDownloadService — file checks, progress, status.
//
// Strategy:
//   Tests cover the ModelFileInfo model, ModelDownloadProgress state,
//   ModelDownloadStatus enum, and static helpers. Actual download tests
//   would require network mocking (dio adapter) which is out of scope
//   for Phase 7A unit tests.
// ===========================================================================

import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/services/model_download_service.dart';

void main() {
  group('ModelFileInfo', () {
    test('creates with required fields', () {
      const info = ModelFileInfo(
        name: 'encoder',
        url: 'https://example.com/encoder.onnx',
        sha256: 'abc123',
        expectedSize: 68000000,
      );
      expect(info.name, 'encoder');
      expect(info.url, 'https://example.com/encoder.onnx');
      expect(info.sha256, 'abc123');
      expect(info.expectedSize, 68000000);
    });
  });

  group('ModelDownloadProgress', () {
    test('creates with default values', () {
      const progress = ModelDownloadProgress(status: ModelDownloadStatus.idle);
      expect(progress.status, ModelDownloadStatus.idle);
      expect(progress.progress, 0.0);
      expect(progress.currentFile, isNull);
      expect(progress.error, isNull);
    });

    test('creates with all fields', () {
      const progress = ModelDownloadProgress(
        status: ModelDownloadStatus.downloading,
        progress: 0.5,
        currentFile: 'encoder',
        error: null,
      );
      expect(progress.status, ModelDownloadStatus.downloading);
      expect(progress.progress, 0.5);
      expect(progress.currentFile, 'encoder');
    });

    test('creates failed status with error', () {
      const progress = ModelDownloadProgress(
        status: ModelDownloadStatus.failed,
        error: 'Network error',
      );
      expect(progress.status, ModelDownloadStatus.failed);
      expect(progress.error, 'Network error');
    });
  });

  group('ModelDownloadStatus', () {
    test('has all expected values', () {
      expect(
        ModelDownloadStatus.values,
        containsAll([
          ModelDownloadStatus.idle,
          ModelDownloadStatus.downloading,
          ModelDownloadStatus.verifying,
          ModelDownloadStatus.completed,
          ModelDownloadStatus.failed,
        ]),
      );
    });
  });

  group('ModelDownloadService', () {
    test('modelFiles has 4 entries', () {
      expect(ModelDownloadService.modelFiles, hasLength(4));
    });

    test('totalExpectedSize is sum of all file sizes', () {
      final expected = ModelDownloadService.modelFiles.fold(
        0,
        (sum, f) => sum + f.expectedSize,
      );
      expect(ModelDownloadService.totalExpectedSize, expected);
    });

    test('model file names match expected Zipformer files', () {
      final names = ModelDownloadService.modelFiles.map((f) => f.name).toList();
      expect(names, contains('encoder'));
      expect(names, contains('decoder'));
      expect(names, contains('joiner'));
      expect(names, contains('tokens'));
    });

    test('all model file URLs point to HuggingFace', () {
      for (final file in ModelDownloadService.modelFiles) {
        expect(file.url, startsWith('https://huggingface.co/'));
      }
    });

    test('downloadProgress returns a stream', () {
      final service = ModelDownloadService();
      expect(service.downloadProgress, isA<Stream<ModelDownloadProgress>>());
      service.dispose();
    });

    test('dispose is safe to call multiple times', () {
      final service = ModelDownloadService();
      service.dispose();
      service.dispose(); // Should not throw.
    });

    test('cancelDownload is safe to call without active download', () {
      final service = ModelDownloadService();
      service.cancelDownload(); // Should not throw.
      service.dispose();
    });
  });
}
