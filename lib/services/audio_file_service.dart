// coverage:ignore-file — platform audio pipeline (dart:io WAV file writing, PCM headers).
// ===========================================================================
// file: lib/services/audio_file_service.dart
// purpose: Raw audio preservation — writes PCM16 audio to WAV files during
//          transcription so audio survives STT failures.
//
// WAV format: RIFF/PCM16, 16kHz, mono (44-byte header + raw PCM16 data).
// The header is written with a placeholder data size on start, then patched
// with the actual size on stop. This means even if the app crashes mid-
// session, the WAV file is recoverable (most players handle truncated WAV).
//
// See: ADR-0024 (Raw Audio Preservation)
// ===========================================================================

import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/foundation.dart' show visibleForTesting;
import 'package:path_provider/path_provider.dart';
import 'package:path/path.dart' as p;

/// Service for preserving raw audio to WAV files during transcription.
///
/// Usage:
///   1. Call [startRecording] at session start → creates WAV file
///   2. Call [writeChunk] for each PCM16 audio chunk → appends data
///   3. Call [stopRecording] at session end → finalizes WAV header
///
/// The WAV file is stored at `{appDocumentsDir}/audio/{sessionId}.wav`.
class AudioFileService {
  /// Sample rate matching STT input (16kHz).
  static const int sampleRate = 16000;

  /// Bits per sample (PCM16).
  static const int bitsPerSample = 16;

  /// Number of audio channels (mono).
  static const int numChannels = 1;

  /// WAV header size in bytes.
  static const int headerSize = 44;

  RandomAccessFile? _file;
  int _dataSize = 0;
  String? _filePath;
  bool _isRecording = false;

  /// Whether the service is currently recording.
  bool get isRecording => _isRecording;

  /// The file path of the current or last recording.
  String? get filePath => _filePath;

  /// Start recording audio for the given session.
  ///
  /// Creates the audio directory if needed, opens a new WAV file, and
  /// writes the 44-byte header with a placeholder data size.
  /// Returns the file path.
  Future<String> startRecording(String sessionId) async {
    if (_isRecording) {
      throw StateError('Already recording. Call stopRecording() first.');
    }

    final appDir = await getApplicationDocumentsDirectory();
    final audioDir = Directory(p.join(appDir.path, 'audio'));
    if (!audioDir.existsSync()) {
      await audioDir.create(recursive: true);
    }

    _filePath = p.join(audioDir.path, '$sessionId.wav');
    _file = await File(_filePath!).open(mode: FileMode.write);
    _dataSize = 0;
    _isRecording = true;

    // Write WAV header with placeholder data size (patched on stop).
    await _file!.writeFrom(_buildWavHeader(0));

    return _filePath!;
  }

  /// Append raw PCM16 audio data to the open WAV file.
  ///
  /// [pcm16Bytes] — raw PCM16 bytes from the microphone (little-endian).
  /// No-op if not currently recording.
  Future<void> writeChunk(List<int> pcm16Bytes) async {
    if (!_isRecording || _file == null) return;
    await _file!.writeFrom(pcm16Bytes);
    _dataSize += pcm16Bytes.length;
  }

  /// Stop recording and finalize the WAV header with the actual data size.
  ///
  /// Returns the file path of the completed WAV file, or null if not recording.
  Future<String?> stopRecording() async {
    if (!_isRecording || _file == null) return null;

    _isRecording = false;

    // Patch the WAV header with the actual data size.
    await _file!.setPosition(0);
    await _file!.writeFrom(_buildWavHeader(_dataSize));
    await _file!.close();
    _file = null;

    return _filePath;
  }

  /// Delete the recording file for a given session.
  ///
  /// Returns true if the file existed and was deleted, false otherwise.
  Future<bool> deleteRecording(String sessionId) async {
    final appDir = await getApplicationDocumentsDirectory();
    final file = File(p.join(appDir.path, 'audio', '$sessionId.wav'));
    if (await file.exists()) {
      await file.delete();
      return true;
    }
    return false;
  }

  /// Exposed for testing — builds a WAV header without requiring file I/O.
  @visibleForTesting
  static Uint8List buildWavHeaderForTest(int dataSize) =>
      _buildWavHeader(dataSize);

  /// Build a 44-byte WAV header for PCM16/16kHz/mono audio.
  ///
  /// [dataSize] — the size of the raw PCM16 data in bytes.
  /// The header follows the RIFF/WAVE specification:
  ///   - Bytes 0-3: "RIFF" chunk ID
  ///   - Bytes 4-7: file size minus 8 (RIFF chunk size)
  ///   - Bytes 8-11: "WAVE" format
  ///   - Bytes 12-15: "fmt " subchunk ID
  ///   - Bytes 16-19: fmt subchunk size (16 for PCM)
  ///   - Bytes 20-21: audio format (1 = PCM)
  ///   - Bytes 22-23: number of channels
  ///   - Bytes 24-27: sample rate
  ///   - Bytes 28-31: byte rate (sampleRate * numChannels * bitsPerSample/8)
  ///   - Bytes 32-33: block align (numChannels * bitsPerSample/8)
  ///   - Bytes 34-35: bits per sample
  ///   - Bytes 36-39: "data" subchunk ID
  ///   - Bytes 40-43: data subchunk size
  static Uint8List _buildWavHeader(int dataSize) {
    final byteRate = sampleRate * numChannels * bitsPerSample ~/ 8;
    final blockAlign = numChannels * bitsPerSample ~/ 8;
    final fileSize = headerSize - 8 + dataSize;

    final header = ByteData(headerSize);

    // RIFF chunk descriptor
    header.setUint8(0, 0x52); // 'R'
    header.setUint8(1, 0x49); // 'I'
    header.setUint8(2, 0x46); // 'F'
    header.setUint8(3, 0x46); // 'F'
    header.setUint32(4, fileSize, Endian.little);
    header.setUint8(8, 0x57); // 'W'
    header.setUint8(9, 0x41); // 'A'
    header.setUint8(10, 0x56); // 'V'
    header.setUint8(11, 0x45); // 'E'

    // fmt subchunk
    header.setUint8(12, 0x66); // 'f'
    header.setUint8(13, 0x6D); // 'm'
    header.setUint8(14, 0x74); // 't'
    header.setUint8(15, 0x20); // ' '
    header.setUint32(16, 16, Endian.little); // PCM subchunk size
    header.setUint16(20, 1, Endian.little); // PCM format
    header.setUint16(22, numChannels, Endian.little);
    header.setUint32(24, sampleRate, Endian.little);
    header.setUint32(28, byteRate, Endian.little);
    header.setUint16(32, blockAlign, Endian.little);
    header.setUint16(34, bitsPerSample, Endian.little);

    // data subchunk
    header.setUint8(36, 0x64); // 'd'
    header.setUint8(37, 0x61); // 'a'
    header.setUint8(38, 0x74); // 't'
    header.setUint8(39, 0x61); // 'a'
    header.setUint32(40, dataSize, Endian.little);

    return header.buffer.asUint8List();
  }
}
