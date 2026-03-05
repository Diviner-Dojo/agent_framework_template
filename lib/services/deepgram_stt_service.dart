// ===========================================================================
// file: lib/services/deepgram_stt_service.dart
// purpose: Deepgram Nova-3 streaming STT implementation of SpeechRecognitionService.
//
// Architecture (ADR-0031):
//   Uses the `record` package to capture PCM16 audio at 16kHz mono and
//   streams it to the deepgram-proxy Supabase Edge Function via WebSocket.
//   Deepgram JSON events are mapped to SpeechResult per the mapping table
//   in ADR-0031:
//
//     Deepgram event                                         | SpeechResult.isFinal
//     ───────────────────────────────────────────────────────┼─────────────────────
//     is_final: false (interim)                             | false
//     is_final: true, speech_final: false (segment boundary)| false
//     is_final: true, speech_final: true (utterance end)    | true
//     UtteranceEnd (fallback)                               | true
//
//   The UtteranceEnd event is a safety net for network conditions where the
//   speech_final message is dropped. It re-emits the last non-empty transcript
//   as a final result.
//
// Security:
//   The Deepgram API key NEVER appears in client code. It lives in Supabase
//   secrets and is used only inside the deepgram-proxy Edge Function.
//
// Testing:
//   The event parsing logic ([_onSocketMessage], [_handleResultsEvent],
//   [_handleUtteranceEndEvent]) is tested via the [@visibleForTesting] hooks
//   [initStreamForTesting] and [injectMessageForTesting]. Network and audio
//   infrastructure methods are excluded from coverage via narrow
//   `// coverage:ignore-start/end` blocks.
//
// See: ADR-0031 (Deepgram Nova-3 STT), ADR-0022 (Voice Engine Swap),
//      ADR-0005 (Edge Function proxy pattern)
// ===========================================================================

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:record/record.dart';

import 'audio_file_service.dart';
import 'speech_recognition_service.dart';

/// Deepgram Nova-3 streaming STT implementation of [SpeechRecognitionService].
///
/// Streams PCM16 audio from the microphone to the Deepgram proxy Edge Function
/// via WebSocket, and parses Deepgram JSON events into [SpeechResult] objects.
///
/// [proxyWsUrl] — WebSocket URL of the `deepgram-proxy` Edge Function.
///   For example: `wss://xxx.supabase.co/functions/v1/deepgram-proxy`
///   Computed from [Environment.deepgramProxyWsUrl].
///
/// [authToken] — Bearer token for proxy authentication. Typically the
///   Supabase anon key (same pattern as ElevenLabsTtsService).
class DeepgramSttService implements SpeechRecognitionService {
  final String _proxyWsUrl;
  final String _authToken;

  WebSocket? _socket;
  AudioRecorder? _recorder;
  StreamController<SpeechResult>? _resultController;
  StreamSubscription<List<int>>? _audioSubscription;
  AudioFileService? _audioFileService;
  bool _isListening = false;
  bool _isInitialized = false;

  /// The last non-empty transcript from a `is_final: true` result.
  /// Re-emitted as final when UtteranceEnd fires (fallback path).
  String _lastFinalTranscript = '';
  double _lastFinalConfidence = 0.0;

  /// Creates a DeepgramSttService.
  ///
  /// [proxyWsUrl] is the WebSocket URL of the `deepgram-proxy` Edge Function.
  /// [authToken] is the Bearer token for proxy authentication.
  DeepgramSttService({required String proxyWsUrl, required String authToken})
    : _proxyWsUrl = proxyWsUrl,
      _authToken = authToken;

  @override
  Future<void> initialize({required String modelPath}) async {
    // No model download needed — Deepgram is cloud-based.
    _isInitialized = true;
  }

  @override
  Stream<SpeechResult> startListening({AudioFileService? audioFileService}) {
    if (!_isInitialized) {
      throw StateError(
        'DeepgramSttService not initialized. Call initialize() first.',
      );
    }
    if (_isListening) {
      throw StateError('Already listening. Call stopListening() first.');
    }

    _resultController = StreamController<SpeechResult>.broadcast();
    _audioFileService = audioFileService;
    _isListening = true;
    _lastFinalTranscript = '';
    _lastFinalConfidence = 0.0;

    // coverage:ignore-start
    // Connect WebSocket and start audio capture asynchronously.
    _connectAndCapture().catchError((Object error) {
      if (_resultController != null && !_resultController!.isClosed) {
        _resultController!.addError(error);
      }
    });
    // coverage:ignore-end

    return _resultController!.stream;
  }

  // coverage:ignore-start
  /// Opens the WebSocket connection and starts the audio capture loop.
  Future<void> _connectAndCapture() async {
    // Connect to the Deepgram proxy with Bearer auth header.
    debugPrint('[Deepgram] Connecting to proxy WebSocket...');
    _socket = await WebSocket.connect(
      _proxyWsUrl,
      headers: {'Authorization': 'Bearer $_authToken'},
    );
    debugPrint(
      '[Deepgram] WebSocket connected. readyState=${_socket!.readyState}',
    );

    // Listen for Deepgram JSON transcription events.
    _socket!.listen(
      (dynamic rawMessage) {
        debugPrint(
          '[Deepgram] Message received: ${rawMessage.toString().substring(0, (rawMessage.toString().length).clamp(0, 120))}',
        );
        _onSocketMessage(rawMessage);
      },
      onError: (Object error) {
        debugPrint('[Deepgram] WebSocket error: $error');
        if (_resultController != null && !_resultController!.isClosed) {
          _resultController!.addError(
            StateError('Deepgram WebSocket error: $error'),
          );
        }
      },
      onDone: () {
        // Socket closed — end the result stream if still listening.
        debugPrint(
          '[Deepgram] WebSocket closed. readyState=${_socket?.readyState}, '
          'closeCode=${_socket?.closeCode}, closeReason=${_socket?.closeReason}, '
          'isListening=$_isListening',
        );
        // Release the microphone unconditionally before updating _isListening.
        //
        // CRITICAL: stopListening() guards on `_isListening == false` and
        // returns early without stopping the recorder. When the WebSocket closes
        // due to an error (code 1011), _isListening is set to false here, which
        // causes any subsequent stopListening() call to skip recorder cleanup.
        // The AudioRecorder stays running, holding the microphone indefinitely
        // and blocking all other STT engines (speech_to_text, sherpa_onnx).
        // Fire-and-forget: we're in a synchronous callback and cannot await.
        _audioSubscription?.cancel();
        _audioSubscription = null;
        _recorder?.stop().then((_) => _recorder?.dispose()).catchError((_) {});
        _recorder = null;
        if (_isListening) {
          _isListening = false;
          _resultController?.close();
        }
      },
    );

    // Start audio capture: PCM16 at 16kHz mono (Deepgram linear16 format).
    //
    // Audio source: AndroidAudioSource.unprocessed
    //   Raw microphone input — bypasses all Samsung OEM post-processing.
    //   VOICE_RECOGNITION (source 6) still produced silent PCM on Samsung
    //   Galaxy S21 Ultra (SM_G998U1, Android 14, One UI 6) after just_audio
    //   TTS playback. UNPROCESSED bypasses the OEM audio routing layer
    //   entirely, getting raw PCM directly from the hardware microphone.
    //   Available since Android API 24; no special permissions required.
    //
    // echoCancel/noiseSuppress/autoGain all disabled: these flags would
    //   switch the source to VOICE_COMMUNICATION on some OEMs regardless of
    //   androidConfig. Deepgram's server-side noise reduction handles quality.
    //
    // manageBluetooth: false — prevents automatic Bluetooth SCO connection,
    //   which also requires MODE_IN_COMMUNICATION and can cause the same
    //   empty-stream failure when Bluetooth audio devices are connected.
    _recorder = AudioRecorder();
    debugPrint('[Deepgram] Starting audio stream (UNPROCESSED source)...');
    final audioStream = await _recorder!.startStream(
      const RecordConfig(
        encoder: AudioEncoder.pcm16bits,
        sampleRate: 16000,
        numChannels: 1,
        autoGain: false,
        echoCancel: false,
        noiseSuppress: false,
        androidConfig: AndroidRecordConfig(
          audioSource: AndroidAudioSource.unprocessed,
          manageBluetooth: false,
        ),
      ),
    );
    debugPrint('[Deepgram] Audio stream started.');

    // Diagnostic: log silence status of the first 5 chunks.
    var chunkCount = 0;
    _audioSubscription = audioStream.listen(
      (List<int> chunk) {
        chunkCount++;
        // Log the first 5 chunks to detect silent audio.
        if (chunkCount <= 5) {
          final maxVal = chunk.isEmpty
              ? 0
              : chunk.reduce((a, b) => a > b ? a : b);
          debugPrint(
            '[Deepgram] Chunk #$chunkCount: ${chunk.length} bytes, '
            'max=$maxVal (${maxVal == 0 ? "SILENT" : "has audio"})',
          );
        }

        // E7 (ADR-0024): Tee raw PCM16 bytes to WAV file before forwarding.
        _audioFileService?.writeChunk(chunk);

        // Forward audio chunk to Deepgram via WebSocket binary frame.
        if (_socket != null &&
            _socket!.readyState == WebSocket.open &&
            _isListening) {
          _socket!.add(chunk);
        } else if (chunkCount <= 5) {
          debugPrint(
            '[Deepgram] Chunk #$chunkCount NOT sent: '
            'socket=${_socket?.readyState}, listening=$_isListening',
          );
        }
      },
      onError: (Object error) {
        debugPrint('[Deepgram] Audio stream error: $error');
        if (_resultController != null && !_resultController!.isClosed) {
          _resultController!.addError(error);
        }
      },
    );
  }
  // coverage:ignore-end

  // ---------------------------------------------------------------------------
  // Event parsing — exercised by unit tests via @visibleForTesting hooks below.
  // ---------------------------------------------------------------------------

  /// Parse an incoming Deepgram WebSocket message and emit [SpeechResult].
  void _onSocketMessage(dynamic rawMessage) {
    if (_resultController == null || _resultController!.isClosed) return;

    // All Deepgram transcription messages are JSON text frames.
    if (rawMessage is! String) return;

    final Map<String, dynamic> data;
    try {
      data = json.decode(rawMessage) as Map<String, dynamic>;
    } on FormatException {
      return; // Ignore non-JSON frames (keepalive pings etc.).
    }

    final type = data['type'] as String?;

    if (type == 'Results') {
      _handleResultsEvent(data);
    } else if (type == 'UtteranceEnd') {
      _handleUtteranceEndEvent();
    }
    // Other types (Metadata, SpeechStarted, etc.) are safely ignored.
  }

  /// Handle a Deepgram `Results` event.
  ///
  /// Maps Deepgram's `is_final` + `speech_final` flags to [SpeechResult.isFinal]
  /// per the mapping table in ADR-0031.
  void _handleResultsEvent(Map<String, dynamic> data) {
    final isDeepgramFinal = data['is_final'] as bool? ?? false;
    final speechFinal = data['speech_final'] as bool? ?? false;

    final channel = data['channel'] as Map<String, dynamic>?;
    final alternatives = channel?['alternatives'] as List<dynamic>?;
    if (alternatives == null || alternatives.isEmpty) return;

    final best = alternatives.first as Map<String, dynamic>;
    final transcript = (best['transcript'] as String? ?? '').trim();
    final confidence = (best['confidence'] as num?)?.toDouble() ?? 0.0;

    if (transcript.isEmpty) return;

    // ADR-0031 mapping:
    //   is_final: true + speech_final: true  → commit (isFinal: true)
    //   is_final: true + speech_final: false → segment boundary (isFinal: false)
    //   is_final: false                      → interim partial (isFinal: false)
    final isFinal = isDeepgramFinal && speechFinal;

    if (isDeepgramFinal) {
      // Track last final for UtteranceEnd fallback.
      _lastFinalTranscript = transcript;
      _lastFinalConfidence = confidence;
    }

    _resultController!.add(
      SpeechResult(text: transcript, isFinal: isFinal, confidence: confidence),
    );
  }

  /// Handle a Deepgram `UtteranceEnd` event.
  ///
  /// Re-emits the last non-empty `is_final` transcript as a final result.
  /// Safety net for when `speech_final` was not received due to network
  /// packet loss, per ADR-0031.
  void _handleUtteranceEndEvent() {
    if (_lastFinalTranscript.isEmpty) return;

    _resultController!.add(
      SpeechResult(
        text: _lastFinalTranscript,
        isFinal: true,
        confidence: _lastFinalConfidence,
      ),
    );

    _lastFinalTranscript = '';
    _lastFinalConfidence = 0.0;
  }

  // ---------------------------------------------------------------------------
  // Test hooks — allow white-box testing without a live WebSocket connection.
  // ---------------------------------------------------------------------------

  /// Initialises the result [StreamController] and resets parsing state without
  /// opening a network connection.
  ///
  /// Call this in the test subclass constructor, subscribe to the returned
  /// stream, then drive parsing via [injectMessageForTesting].
  @visibleForTesting
  StreamController<SpeechResult> initStreamForTesting() {
    // sync: true delivers events synchronously to listeners in the same call
    // stack, which makes unit tests deterministic without requiring await.
    // Production code uses sync: false (default) to avoid re-entrancy.
    _resultController = StreamController<SpeechResult>.broadcast(sync: true);
    _lastFinalTranscript = '';
    _lastFinalConfidence = 0.0;
    return _resultController!;
  }

  /// Injects [rawMessage] directly into the production [_onSocketMessage]
  /// handler, bypassing the WebSocket layer entirely.
  ///
  /// Requires [initStreamForTesting] to have been called first so that
  /// `_resultController` is non-null.
  @visibleForTesting
  void injectMessageForTesting(String rawMessage) =>
      _onSocketMessage(rawMessage);

  // ---------------------------------------------------------------------------
  // Lifecycle — infrastructure methods excluded from coverage.
  // ---------------------------------------------------------------------------

  // coverage:ignore-start
  @override
  Future<void> stopListening() async {
    if (!_isListening) return;

    _isListening = false;

    // Stop audio recording first.
    await _audioSubscription?.cancel();
    _audioSubscription = null;
    await _audioFileService?.stopRecording();
    _audioFileService = null;

    await _recorder?.stop();
    await _recorder?.dispose();
    _recorder = null;

    // Send Deepgram CloseStream to flush any buffered audio gracefully.
    if (_socket != null && _socket!.readyState == WebSocket.open) {
      try {
        _socket!.add(json.encode({'type': 'CloseStream'}));
        // Give Deepgram ~500ms to flush and return the final transcript.
        await Future<void>.delayed(const Duration(milliseconds: 500));
      } on StateError {
        // Socket already closing — ignore.
      }
    }

    await _socket?.close();
    _socket = null;

    await _resultController?.close();
    _resultController = null;
  }

  @override
  void dispose() {
    // Release microphone unconditionally — _isListening may already be false
    // if the WebSocket closed with an error, leaving the recorder still running.
    _audioSubscription?.cancel();
    _audioSubscription = null;
    _recorder?.stop().then((_) => _recorder?.dispose()).catchError((_) {});
    _recorder = null;
    if (_isListening) {
      stopListening();
    }
    _socket?.close();
    _socket = null;
    _isInitialized = false;
  }
  // coverage:ignore-end

  @override
  bool get isListening => _isListening;

  @override
  bool get isInitialized => _isInitialized;
}
