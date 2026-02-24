import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path_provider_platform_interface/path_provider_platform_interface.dart';
import 'package:plugin_platform_interface/plugin_platform_interface.dart';
import 'package:agentic_journal/services/photo_service.dart';

/// Fake PathProviderPlatform that returns a configurable support directory.
class _FakePathProviderPlatform extends Fake
    with MockPlatformInterfaceMixin
    implements PathProviderPlatform {
  final String supportPath;

  _FakePathProviderPlatform(this.supportPath);

  @override
  Future<String?> getApplicationSupportPath() async => supportPath;
}

/// A fake ImagePicker that returns a configurable file.
class _FakeImagePicker extends ImagePicker {
  XFile? returnFile;

  @override
  Future<XFile?> pickImage({
    required ImageSource source,
    double? maxWidth,
    double? maxHeight,
    int? imageQuality,
    bool requestFullMetadata = true,
    CameraDevice preferredCameraDevice = CameraDevice.rear,
  }) async {
    return returnFile;
  }
}

void main() {
  group('PhotoService.canonicalPath', () {
    test('builds correct path for valid UUIDs', () {
      final path = PhotoService.canonicalPath(
        '/app/support',
        'abc-def-123',
        'aaa-bbb-456-789',
      );
      // Platform-independent check — contains the expected segments.
      expect(path, contains('photos'));
      expect(path, contains('abc-def-123'));
      expect(path, contains('aaa-bbb-456-789.jpg'));
    });

    test('rejects sessionId with path traversal characters', () {
      expect(
        () => PhotoService.canonicalPath('/base', '../etc', 'photo-1'),
        throwsA(isA<ArgumentError>()),
      );
    });

    test('rejects photoId with path traversal characters', () {
      expect(
        () => PhotoService.canonicalPath('/base', 'session-1', '../../passwd'),
        throwsA(isA<ArgumentError>()),
      );
    });

    test('rejects sessionId with spaces', () {
      expect(
        () => PhotoService.canonicalPath('/base', 'bad session', 'photo-1'),
        throwsA(isA<ArgumentError>()),
      );
    });

    test('rejects sessionId with uppercase letters', () {
      expect(
        () => PhotoService.canonicalPath('/base', 'ABC-DEF', 'photo-1'),
        throwsA(isA<ArgumentError>()),
      );
    });

    test('accepts standard UUID format', () {
      // Should not throw.
      final path = PhotoService.canonicalPath(
        '/base',
        'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        'f0e1d2c3-b4a5-6789-0123-456789abcdef',
      );
      expect(path, contains('a1b2c3d4-e5f6-7890-abcd-ef1234567890'));
    });

    test('accepts hex-only IDs without dashes', () {
      final path = PhotoService.canonicalPath(
        '/base',
        'abcdef1234567890',
        'fedcba0987654321',
      );
      expect(path, contains('abcdef1234567890'));
    });
  });

  group('PhotoService.processAndSave', () {
    // Note: processAndSave requires actual file I/O and image decoding,
    // which is tested via integration tests on a real device.
    // Unit tests here focus on the canonicalPath validation aspect.

    test('would reject invalid IDs before processing', () {
      // The validation happens in canonicalPath, which processAndSave calls.
      // Verifying the validation separately is sufficient.
      expect(
        () => PhotoService.canonicalPath('/base', 'bad/id', 'photo-1'),
        throwsA(isA<ArgumentError>()),
      );
    });
  });

  group('PhotoService.takePhoto', () {
    test('returns null when user cancels', () async {
      final fakePicker = _FakeImagePicker();
      fakePicker.returnFile = null;
      final service = PhotoService(picker: fakePicker);

      final result = await service.takePhoto();
      expect(result, isNull);
    });

    test('returns File when user takes a photo', () async {
      final tempDir = Directory.systemTemp.createTempSync('take_photo_test');
      final tempFile = File('${tempDir.path}/captured.jpg');
      tempFile.writeAsBytesSync([0xFF, 0xD8, 0xFF, 0xE0]);

      final fakePicker = _FakeImagePicker();
      fakePicker.returnFile = XFile(tempFile.path);
      final service = PhotoService(picker: fakePicker);

      final result = await service.takePhoto();
      expect(result, isNotNull);
      expect(result!.path, tempFile.path);

      tempDir.deleteSync(recursive: true);
    });
  });

  group('PhotoService.pickFromGallery', () {
    test('returns null when user cancels', () async {
      final fakePicker = _FakeImagePicker();
      fakePicker.returnFile = null;
      final service = PhotoService(picker: fakePicker);

      final result = await service.pickFromGallery();
      expect(result, isNull);
    });

    test('returns File when user picks a photo', () async {
      final tempDir = Directory.systemTemp.createTempSync('pick_gallery_test');
      final tempFile = File('${tempDir.path}/gallery.jpg');
      tempFile.writeAsBytesSync([0xFF, 0xD8, 0xFF, 0xE0]);

      final fakePicker = _FakeImagePicker();
      fakePicker.returnFile = XFile(tempFile.path);
      final service = PhotoService(picker: fakePicker);

      final result = await service.pickFromGallery();
      expect(result, isNotNull);
      expect(result!.path, tempFile.path);

      tempDir.deleteSync(recursive: true);
    });
  });

  group('ProcessedPhoto', () {
    test('stores all properties correctly', () {
      final tempDir = Directory.systemTemp.createTempSync('processed_test');
      final tempFile = File('${tempDir.path}/test.jpg');
      tempFile.writeAsBytesSync([0xFF, 0xD8]);

      final processed = ProcessedPhoto(
        file: tempFile,
        width: 800,
        height: 600,
        fileSizeBytes: 12345,
      );

      expect(processed.file.path, tempFile.path);
      expect(processed.width, 800);
      expect(processed.height, 600);
      expect(processed.fileSizeBytes, 12345);

      tempDir.deleteSync(recursive: true);
    });
  });

  group('PhotoService.deletePhotoFile', () {
    test('is no-op when platform bindings unavailable', () async {
      final tempDir = Directory.systemTemp.createTempSync('delete_test');
      final tempFile = File('${tempDir.path}/photo.jpg');
      tempFile.writeAsBytesSync([0xFF, 0xD8]);
      expect(tempFile.existsSync(), true);

      final service = PhotoService();
      // Without platform bindings, deletePhotoFile refuses to delete (safe
      // default — cannot verify path confinement without the base dir).
      await service.deletePhotoFile(tempFile.path);

      expect(tempFile.existsSync(), true);
      tempDir.deleteSync(recursive: true);
    });

    test('is no-op for nonexistent file', () async {
      final service = PhotoService();
      // Should not throw even without bindings.
      await service.deletePhotoFile('/nonexistent/path.jpg');
    });
  });

  group('PhotoService file operations (with bindings)', () {
    late Directory baseDir;

    setUp(() {
      TestWidgetsFlutterBinding.ensureInitialized();
      baseDir = Directory.systemTemp.createTempSync('photo_service_bindings');
      PathProviderPlatform.instance = _FakePathProviderPlatform(baseDir.path);
    });

    tearDown(() {
      if (baseDir.existsSync()) {
        baseDir.deleteSync(recursive: true);
      }
    });

    test('deletePhotoFile deletes file within photos directory', () async {
      // Create a file inside the photos/ subdirectory (path confinement zone).
      final photosDir = Directory('${baseDir.path}/photos/session-1');
      photosDir.createSync(recursive: true);
      final photoFile = File('${photosDir.path}/photo.jpg');
      photoFile.writeAsBytesSync([0xFF, 0xD8]);
      expect(photoFile.existsSync(), true);

      final service = PhotoService();
      await service.deletePhotoFile(photoFile.path);

      expect(photoFile.existsSync(), false);
    });

    test(
      'deletePhotoFile refuses to delete file outside photos directory',
      () async {
        // Create a file outside the photos/ subdirectory.
        final outsideFile = File('${baseDir.path}/outside.jpg');
        outsideFile.writeAsBytesSync([0xFF, 0xD8]);
        expect(outsideFile.existsSync(), true);

        final service = PhotoService();
        await service.deletePhotoFile(outsideFile.path);

        // File should still exist — path confinement rejected the delete.
        expect(outsideFile.existsSync(), true);
      },
    );

    test('deleteSessionPhotos removes session photo directory', () async {
      final sessionDir = Directory('${baseDir.path}/photos/abc-def-123');
      sessionDir.createSync(recursive: true);
      File('${sessionDir.path}/photo1.jpg').writeAsBytesSync([0xFF]);
      File('${sessionDir.path}/photo2.jpg').writeAsBytesSync([0xFF]);
      expect(sessionDir.existsSync(), true);

      final service = PhotoService();
      await service.deleteSessionPhotos('abc-def-123');

      expect(sessionDir.existsSync(), false);
    });

    test('deleteSessionPhotos is no-op for nonexistent session', () async {
      final service = PhotoService();
      // Should not throw.
      await service.deleteSessionPhotos('nonexistent-session-id');
    });

    test('deleteSessionPhotos rejects invalid session ID', () async {
      final service = PhotoService();
      // Should not throw — returns early due to regex validation.
      await service.deleteSessionPhotos('../etc');
    });

    test('deleteAllPhotos removes entire photos directory', () async {
      final photosDir = Directory('${baseDir.path}/photos');
      photosDir.createSync();
      final session1 = Directory('${photosDir.path}/session-1');
      session1.createSync();
      File('${session1.path}/photo.jpg').writeAsBytesSync([0xFF]);
      expect(photosDir.existsSync(), true);

      final service = PhotoService();
      await service.deleteAllPhotos();

      expect(photosDir.existsSync(), false);
    });

    test('calculateTotalSize returns total bytes of all photos', () async {
      final photosDir = Directory('${baseDir.path}/photos/session-1');
      photosDir.createSync(recursive: true);
      File('${photosDir.path}/a.jpg').writeAsBytesSync(List.filled(100, 0xFF));
      File('${photosDir.path}/b.jpg').writeAsBytesSync(List.filled(200, 0xFF));

      final service = PhotoService();
      final size = await service.calculateTotalSize();

      expect(size, 300);
    });

    test('calculateTotalSize returns 0 when no photos directory', () async {
      final service = PhotoService();
      final size = await service.calculateTotalSize();
      expect(size, 0);
    });
  });
}
