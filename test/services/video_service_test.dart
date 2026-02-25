import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/services/video_service.dart';

void main() {
  group('VideoService', () {
    group('canonicalVideoPath', () {
      test('builds correct path with valid UUIDs', () {
        final path = VideoService.canonicalVideoPath(
          '/data/app',
          'abc-123',
          'def-456',
        );
        // path.join uses OS separator; just check components are present.
        expect(path, contains('videos'));
        expect(path, contains('abc-123'));
        expect(path, contains('def-456.mp4'));
      });

      test('throws ArgumentError for invalid sessionId', () {
        expect(
          () => VideoService.canonicalVideoPath('/data', '../etc', 'def-456'),
          throwsArgumentError,
        );
      });

      test('throws ArgumentError for invalid videoId', () {
        expect(
          () => VideoService.canonicalVideoPath('/data', 'abc-123', '../etc'),
          throwsArgumentError,
        );
      });

      test('throws ArgumentError for sessionId with spaces', () {
        expect(
          () => VideoService.canonicalVideoPath('/data', 'abc 123', 'def-456'),
          throwsArgumentError,
        );
      });

      test('accepts valid hex-and-dash UUIDs', () {
        // Standard UUID v4 format.
        final path = VideoService.canonicalVideoPath(
          '/data',
          'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
          'f0e1d2c3-b4a5-6789-0123-456789abcdef',
        );
        expect(path, contains('.mp4'));
      });
    });

    group('canonicalThumbnailPath', () {
      test('builds correct path with _thumb.jpg suffix', () {
        final path = VideoService.canonicalThumbnailPath(
          '/data/app',
          'abc-123',
          'def-456',
        );
        expect(path, contains('videos'));
        expect(path, contains('abc-123'));
        expect(path, contains('def-456_thumb.jpg'));
      });

      test('throws ArgumentError for invalid sessionId', () {
        expect(
          () => VideoService.canonicalThumbnailPath('/data', '../etc', 'def'),
          throwsArgumentError,
        );
      });

      test('throws ArgumentError for invalid videoId', () {
        expect(
          () => VideoService.canonicalThumbnailPath('/data', 'abc', '../etc'),
          throwsArgumentError,
        );
      });
    });
  });

  group('VideoService constants', () {
    test('maxDurationSeconds is 60', () {
      expect(maxDurationSeconds, 60);
    });

    test('maxFileSizeBytes is 100MB', () {
      expect(maxFileSizeBytes, 100 * 1024 * 1024);
    });

    test('storageWarningBytes is 2GB', () {
      expect(storageWarningBytes, 2 * 1024 * 1024 * 1024);
    });
  });
}
