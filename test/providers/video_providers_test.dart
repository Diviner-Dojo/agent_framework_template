import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/providers/video_providers.dart';
import 'package:agentic_journal/services/video_service.dart';

void main() {
  group('VideoStorageInfo', () {
    test('formattedSize returns bytes for small values', () {
      const info = VideoStorageInfo(count: 1, totalSizeBytes: 512);
      expect(info.formattedSize, '512 B');
    });

    test('formattedSize returns KB for kilobyte values', () {
      const info = VideoStorageInfo(count: 1, totalSizeBytes: 2048);
      expect(info.formattedSize, '2.0 KB');
    });

    test('formattedSize returns MB for megabyte values', () {
      const info = VideoStorageInfo(count: 1, totalSizeBytes: 52428800);
      expect(info.formattedSize, '50.0 MB');
    });

    test('formattedSize returns GB for gigabyte values', () {
      const info = VideoStorageInfo(count: 2, totalSizeBytes: 2147483648);
      expect(info.formattedSize, '2.0 GB');
    });

    test('formattedSize returns 0 B for zero', () {
      const info = VideoStorageInfo(count: 0, totalSizeBytes: 0);
      expect(info.formattedSize, '0 B');
    });

    test('isOverWarningThreshold false when under 2GB', () {
      const info = VideoStorageInfo(
        count: 1,
        totalSizeBytes: storageWarningBytes - 1,
      );
      expect(info.isOverWarningThreshold, isFalse);
    });

    test('isOverWarningThreshold true at exactly 2GB', () {
      const info = VideoStorageInfo(
        count: 1,
        totalSizeBytes: storageWarningBytes,
      );
      expect(info.isOverWarningThreshold, isTrue);
    });

    test('isOverWarningThreshold true when over 2GB', () {
      const info = VideoStorageInfo(
        count: 1,
        totalSizeBytes: storageWarningBytes + 1,
      );
      expect(info.isOverWarningThreshold, isTrue);
    });
  });

  group('VideoService constants', () {
    test('maxDurationSeconds is 60', () {
      expect(maxDurationSeconds, 60);
    });

    test('maxFileSizeBytes is 100MB', () {
      expect(maxFileSizeBytes, 100 * 1024 * 1024);
    });

    test('thumbnailWidth is 320', () {
      expect(thumbnailWidth, 320);
    });

    test('thumbnailHeight is 180', () {
      expect(thumbnailHeight, 180);
    });

    test('thumbnailQuality is 70', () {
      expect(thumbnailQuality, 70);
    });
  });
}
