import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/services/audio_file_service.dart';

void main() {
  late AudioFileService service;
  late Directory tempDir;

  setUp(() {
    service = AudioFileService();
    tempDir = Directory.systemTemp.createTempSync('audio_test_');
  });

  tearDown(() async {
    if (service.isRecording) {
      await service.stopRecording();
    }
    if (tempDir.existsSync()) {
      tempDir.deleteSync(recursive: true);
    }
  });

  group('AudioFileService - WAV header correctness', () {
    test('creates valid WAV file with correct header bytes', () async {
      // Write some known PCM16 data and verify the WAV header.
      final filePath = '${tempDir.path}/test-session.wav';

      // Use a test-friendly approach: manually create the file
      // since startRecording uses path_provider (which needs Flutter).
      final file = await File(filePath).open(mode: FileMode.write);
      final header = AudioFileService.buildWavHeaderForTest(0);
      await file.writeFrom(header);

      // Write 100 samples (200 bytes) of PCM16 data.
      final pcmData = Uint8List(200);
      for (var i = 0; i < 200; i += 2) {
        // Write a simple sine-like pattern.
        pcmData[i] = i; // low byte
        pcmData[i + 1] = 0; // high byte
      }
      file.writeFromSync(pcmData);

      // Patch header with actual data size.
      await file.setPosition(0);
      await file.writeFrom(AudioFileService.buildWavHeaderForTest(200));
      await file.close();

      // Read back and verify header.
      final bytes = await File(filePath).readAsBytes();
      final byteData = ByteData.sublistView(bytes);

      // RIFF magic bytes
      expect(bytes[0], 0x52); // 'R'
      expect(bytes[1], 0x49); // 'I'
      expect(bytes[2], 0x46); // 'F'
      expect(bytes[3], 0x46); // 'F'

      // File size: header(44) - 8 + data(200) = 236
      expect(byteData.getUint32(4, Endian.little), 236);

      // WAVE magic
      expect(bytes[8], 0x57); // 'W'
      expect(bytes[9], 0x41); // 'A'
      expect(bytes[10], 0x56); // 'V'
      expect(bytes[11], 0x45); // 'E'

      // fmt subchunk
      expect(bytes[12], 0x66); // 'f'
      expect(bytes[13], 0x6D); // 'm'
      expect(bytes[14], 0x74); // 't'
      expect(bytes[15], 0x20); // ' '
      expect(byteData.getUint32(16, Endian.little), 16); // PCM subchunk size
      expect(byteData.getUint16(20, Endian.little), 1); // PCM format
      expect(byteData.getUint16(22, Endian.little), 1); // mono
      expect(byteData.getUint32(24, Endian.little), 16000); // sample rate
      expect(byteData.getUint32(28, Endian.little), 32000); // byte rate
      expect(byteData.getUint16(32, Endian.little), 2); // block align
      expect(byteData.getUint16(34, Endian.little), 16); // bits per sample

      // data subchunk
      expect(bytes[36], 0x64); // 'd'
      expect(bytes[37], 0x61); // 'a'
      expect(bytes[38], 0x74); // 't'
      expect(bytes[39], 0x61); // 'a'
      expect(byteData.getUint32(40, Endian.little), 200); // data size

      // Verify total file size.
      expect(bytes.length, 244); // 44 header + 200 data
    });

    test('header with zero data size produces valid empty WAV', () {
      final header = AudioFileService.buildWavHeaderForTest(0);

      expect(header.length, 44);

      final byteData = ByteData.sublistView(header);
      // File size: 44 - 8 + 0 = 36
      expect(byteData.getUint32(4, Endian.little), 36);
      // Data size: 0
      expect(byteData.getUint32(40, Endian.little), 0);
    });
  });

  group('AudioFileService - state management', () {
    test('isRecording is false initially', () {
      expect(service.isRecording, false);
    });

    test('filePath is null initially', () {
      expect(service.filePath, isNull);
    });

    test('writeChunk is a no-op when not recording', () {
      // Should not throw.
      service.writeChunk([1, 2, 3, 4]);
    });

    test('stopRecording returns null when not recording', () async {
      final result = await service.stopRecording();
      expect(result, isNull);
    });
  });
}
