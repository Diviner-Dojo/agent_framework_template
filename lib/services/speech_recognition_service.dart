// ===========================================================================
// file: lib/services/speech_recognition_service.dart
// purpose: Abstract STT interface + sherpa_onnx Zipformer implementation.
//
// Architecture (ADR-0015):
//   sherpa_onnx is a pull-based C++ library — callers feed audio chunks,
//   check isReady(), call decode(), and read results. This service wraps
//   that pull loop in a StreamController<SpeechResult> so Flutter widgets
//   can consume transcription results reactively.
//
//   Audio capture is handled by the `record` package (separate from
//   sherpa_onnx, which only processes samples). PCM16 bytes from the
//   microphone are converted to Float32 before feeding to the recognizer.
//
// Critical:
//   sherpa_onnx.initBindings() MUST be called before creating any
//   recognizer. Without it, all recognition silently returns empty strings.
//
// See: ADR-0015 (Voice Mode Architecture)
// ===========================================================================

import 'dart:async';
import 'dart:typed_data';

import 'package:record/record.dart';
import 'package:sherpa_onnx/sherpa_onnx.dart' as sherpa;

import 'audio_file_service.dart';

/// A single speech recognition result (partial or final).
///
/// [text] contains the recognized text so far.
/// [isFinal] is true when endpoint detection has identified an utterance
/// boundary, meaning the speaker paused and this segment is complete.
class SpeechResult {
  /// The recognized text.
  final String text;

  /// True when isEndpoint() detected an utterance boundary.
  final bool isFinal;

  /// STT engine confidence score (0.0–1.0).
  ///
  /// Defaults to 0.0 for engines that don't report confidence (e.g. sherpa_onnx).
  /// Google `speech_to_text` provides this via `SpeechRecognitionResult.confidence`.
  /// Used by the confidence-weighted commit delay (SPEC-20260228 Task 3).
  final double confidence;

  /// Creates a speech result.
  const SpeechResult({
    required this.text,
    required this.isFinal,
    this.confidence = 0.0,
  }); // coverage:ignore-line

  @override
  String toString() =>
      'SpeechResult(text: "$text", isFinal: $isFinal, confidence: $confidence)';

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is SpeechResult &&
          runtimeType == other.runtimeType &&
          text == other.text &&
          isFinal == other.isFinal &&
          confidence == other.confidence;

  @override
  int get hashCode => Object.hash(text, isFinal, confidence);
}

/// Abstract interface for speech-to-text services.
///
/// Implementations wrap a specific STT engine (e.g., sherpa_onnx Zipformer).
/// The abstract interface enables mock implementations for testing, since
/// native STT engines cannot run in CI.
abstract class SpeechRecognitionService {
  /// Initialize the STT engine with model files at [modelPath].
  ///
  /// Must be called before [startListening]. Loads the neural network model
  /// into memory (5-8 seconds on target device).
  Future<void> initialize({required String modelPath});

  /// Start listening and return a stream of recognition results.
  ///
  /// Emits [SpeechResult] objects as audio is processed:
  ///   - `isFinal: false` for partial (in-progress) results
  ///   - `isFinal: true` when endpoint detection identifies an utterance end
  ///
  /// [audioFileService] — optional service for raw audio preservation (ADR-0024).
  /// When provided, PCM16 bytes are teed to the WAV file before STT processing.
  ///
  /// Call [stopListening] to end the audio capture.
  Stream<SpeechResult> startListening({AudioFileService? audioFileService});

  /// Stop listening and clean up the audio stream.
  Future<void> stopListening();

  /// Whether the service is currently capturing audio and recognizing.
  bool get isListening;

  /// Whether the model is loaded and ready for recognition.
  bool get isInitialized;

  /// Release all native resources (recognizer, audio recorder).
  void dispose();
}

/// sherpa_onnx Zipformer-transducer implementation of [SpeechRecognitionService].
///
/// Uses an [OnlineRecognizer] for real-time streaming STT. Audio is captured
/// by the `record` package as PCM16 at 16kHz mono, converted to Float32,
/// and fed to the recognizer chunk by chunk.
///
/// The polling loop runs after each audio chunk:
///   1. Convert PCM16 bytes → Float32 samples
///   2. Feed samples to recognizer stream
///   3. While isReady(): decode()
///   4. Read result text
///   5. Check isEndpoint() → emit final or partial SpeechResult
// coverage:ignore-start
class SherpaOnnxSpeechRecognitionService implements SpeechRecognitionService {
  sherpa.OnlineRecognizer? _recognizer;
  sherpa.OnlineStream? _stream;
  AudioRecorder? _recorder;
  StreamController<SpeechResult>? _resultController;
  StreamSubscription<List<int>>? _audioSubscription;
  AudioFileService? _audioFileService;
  bool _isListening = false;
  bool _isInitialized = false;

  /// Convert ALL CAPS sherpa_onnx output to sentence case.
  ///
  /// The Zipformer model outputs uppercase text. This converts it to
  /// natural sentence case (first letter capitalized, rest lowercase).
  static String _toSentenceCase(String text) {
    if (text.isEmpty) return text;
    // Only transform if the text is all uppercase.
    if (text != text.toUpperCase()) return text;
    final lower = text.toLowerCase();
    return lower[0].toUpperCase() + lower.substring(1);
  }

  @override
  Future<void> initialize({required String modelPath}) async {
    if (_isInitialized) return;

    // Critical: initBindings() must be called before any sherpa_onnx usage.
    // Without this, all recognition silently returns empty strings.
    sherpa.initBindings();

    final config = sherpa.OnlineRecognizerConfig(
      model: sherpa.OnlineModelConfig(
        transducer: sherpa.OnlineTransducerModelConfig(
          encoder: '$modelPath/encoder-epoch-99-avg-1.int8.onnx',
          decoder: '$modelPath/decoder-epoch-99-avg-1.onnx',
          joiner: '$modelPath/joiner-epoch-99-avg-1.int8.onnx',
        ),
        tokens: '$modelPath/tokens.txt',
        numThreads: 2,
        debug: false,
      ),
      decodingMethod: 'greedy_search',
      enableEndpoint: true,
      // Explicit endpoint rules tuned for natural journaling speech cadence.
      // These match library defaults but are pinned here so upstream changes
      // don't silently alter our endpoint behavior.
      rule1MinTrailingSilence: 2.4, // long pause → utterance end
      rule2MinTrailingSilence: 1.2, // short pause → clause end
    );

    _recognizer = sherpa.OnlineRecognizer(config);
    _stream = _recognizer!.createStream();
    _isInitialized = true;
  }

  @override
  Stream<SpeechResult> startListening({AudioFileService? audioFileService}) {
    if (!_isInitialized) {
      throw StateError(
        'SpeechRecognitionService not initialized. Call initialize() first.',
      );
    }
    if (_isListening) {
      throw StateError('Already listening. Call stopListening() first.');
    }

    _audioFileService = audioFileService;
    _resultController = StreamController<SpeechResult>.broadcast();
    _recorder = AudioRecorder();
    _isListening = true;

    // Start audio capture asynchronously.
    _startAudioCapture();

    return _resultController!.stream;
  }

  /// Start the audio capture and processing loop.
  Future<void> _startAudioCapture() async {
    final audioStream = await _recorder!.startStream(
      const RecordConfig(
        encoder: AudioEncoder.pcm16bits,
        sampleRate: 16000,
        numChannels: 1,
        autoGain: true,
        echoCancel: true,
        noiseSuppress: true,
      ),
    );

    _audioSubscription = audioStream.listen(
      _processAudioChunk,
      onError: (Object error) {
        _resultController?.addError(error);
      },
      onDone: () {
        // Audio stream ended (recorder stopped).
        _isListening = false;
      },
    );
  }

  /// Process a single audio chunk from the microphone.
  ///
  /// Converts PCM16 bytes to Float32 samples, feeds them to the recognizer,
  /// runs the decoding loop, and emits results.
  void _processAudioChunk(List<int> data) {
    if (_recognizer == null || _stream == null || _resultController == null) {
      return;
    }

    // E7 (ADR-0024): Tee raw PCM16 bytes to WAV file before STT processing.
    // This preserves audio even if STT fails mid-session.
    // Async write dispatches to OS I/O thread pool — does not block STT.
    _audioFileService?.writeChunk(data);

    // Convert PCM16 bytes to Float32 samples.
    // PCM16 is little-endian 16-bit signed integers; normalize to [-1.0, 1.0].
    final bytes = Uint8List.fromList(data);
    final int16List = ByteData.sublistView(bytes).buffer.asInt16List();
    final samples = Float32List(int16List.length);
    for (var i = 0; i < int16List.length; i++) {
      samples[i] = int16List[i] / 32768.0;
    }

    // Feed samples to the recognizer stream.
    _stream!.acceptWaveform(samples: samples, sampleRate: 16000);

    // Decode all available frames.
    while (_recognizer!.isReady(_stream!)) {
      _recognizer!.decode(_stream!);
    }

    // Read the current result and convert from ALL CAPS to sentence case.
    final rawText = _recognizer!.getResult(_stream!).text.trim();
    final text = _toSentenceCase(rawText);

    // Check for endpoint (utterance boundary).
    if (_recognizer!.isEndpoint(_stream!)) {
      if (text.isNotEmpty) {
        _resultController!.add(SpeechResult(text: text, isFinal: true));
      }
      // Reset the stream for the next utterance.
      _recognizer!.reset(_stream!);
    } else if (text.isNotEmpty) {
      _resultController!.add(SpeechResult(text: text, isFinal: false));
    }
  }

  @override
  Future<void> stopListening() async {
    if (!_isListening) return;

    _isListening = false;
    await _audioSubscription?.cancel();
    _audioSubscription = null;

    // Flush trailing audio by padding with 0.5s of silence.
    // Without this, the recognizer drops partially-decoded frames when
    // the mic stream ends abruptly. The silence lets the decoder finish
    // processing any buffered audio before we read the final result.
    if (_recognizer != null && _stream != null && _resultController != null) {
      final tailPadding = Float32List(8000); // 0.5s silence at 16 kHz
      _stream!.acceptWaveform(samples: tailPadding, sampleRate: 16000);
      while (_recognizer!.isReady(_stream!)) {
        _recognizer!.decode(_stream!);
      }

      // Get any remaining text after flushing.
      final text = _toSentenceCase(
        _recognizer!.getResult(_stream!).text.trim(),
      );
      if (text.isNotEmpty) {
        _resultController!.add(SpeechResult(text: text, isFinal: true));
      }
      _recognizer!.reset(_stream!);
    }

    // E7 (ADR-0024): Finalize WAV header before closing recorder.
    await _audioFileService?.stopRecording();
    _audioFileService = null;

    await _recorder?.stop();
    await _recorder?.dispose();
    _recorder = null;

    await _resultController?.close();
    _resultController = null;
  }

  @override
  bool get isListening => _isListening;

  @override
  bool get isInitialized => _isInitialized;

  @override
  void dispose() {
    if (_isListening) {
      // Fire-and-forget cleanup.
      stopListening();
    }
    _stream?.free();
    _stream = null;
    _recognizer?.free();
    _recognizer = null;
    _isInitialized = false;
  }
}

// coverage:ignore-end
