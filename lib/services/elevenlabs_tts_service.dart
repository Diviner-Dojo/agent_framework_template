// ===========================================================================
// file: lib/services/elevenlabs_tts_service.dart
// purpose: ElevenLabs TTS implementation via Supabase Edge Function proxy.
//
// Uses the ElevenLabs API (proxied through Supabase) for natural-sounding
// text-to-speech. Audio is returned as MP3 bytes and played via just_audio.
//
// The API key never reaches the client — all calls go through the
// elevenlabs-proxy Edge Function (same security pattern as ADR-0005).
//
// Falls back to flutter_tts (FlutterTextToSpeechService) on network error,
// handled at the provider level.
//
// See: ADR-0022 (Voice Engine Swap)
// ===========================================================================

import 'dart:async';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:just_audio/just_audio.dart';

import 'text_to_speech_service.dart';

/// ElevenLabs TTS implementation of [TextToSpeechService].
///
/// Sends text to the ElevenLabs proxy Edge Function, receives MP3 audio
/// bytes, and plays them via [AudioPlayer] from the just_audio package.
/// Uses a [Completer] to match the existing blocking [speak] contract.
// coverage:ignore-start
class ElevenLabsTtsService implements TextToSpeechService {
  final Dio _dio;
  final String _proxyUrl;
  final String? _authToken;
  AudioPlayer? _player;
  bool _isSpeaking = false;
  Completer<void>? _speakCompleter;
  double _rate = 1.0;

  /// Creates an ElevenLabs TTS service.
  ///
  /// [proxyUrl] is the full URL to the elevenlabs-proxy Edge Function.
  /// [authToken] is the Bearer token (JWT or proxy access key).
  /// [dio] is an optional Dio instance for testing.
  ElevenLabsTtsService({
    required String proxyUrl,
    required String? authToken,
    Dio? dio,
  }) : _proxyUrl = proxyUrl,
       _authToken = authToken,
       _dio = dio ?? Dio();

  @override
  Future<void> initialize() async {
    _player = AudioPlayer();

    // Listen for playback completion.
    _player!.playerStateStream.listen(
      (state) {
        if (state.processingState == ProcessingState.completed) {
          _isSpeaking = false;
          _speakCompleter?.complete();
          _speakCompleter = null;
        }
      },
      onError: (Object e) {
        _isSpeaking = false;
        _speakCompleter?.completeError(StateError('Playback error: $e'));
        _speakCompleter = null;
      },
    );
  }

  @override
  Future<void> speak(String text) async {
    if (_player == null) {
      throw StateError(
        'ElevenLabsTtsService not initialized. Call initialize() first.',
      );
    }
    if (text.isEmpty) return;

    // Always stop the player before new playback — releases the previous
    // audio session so just_audio doesn't fight speech_to_text for focus.
    await _player!.stop();
    _isSpeaking = false;
    _speakCompleter?.complete();
    _speakCompleter = null;

    // Call the proxy Edge Function to get MP3 audio bytes.
    final Response<List<int>> response;
    try {
      response = await _dio.post<List<int>>(
        _proxyUrl,
        data: {'text': text},
        options: Options(
          headers: {
            if (_authToken != null) 'Authorization': 'Bearer $_authToken',
            'Content-Type': 'application/json',
          },
          responseType: ResponseType.bytes,
          receiveTimeout: const Duration(seconds: 30),
          sendTimeout: const Duration(seconds: 10),
        ),
      );
    } on DioException catch (e) {
      throw StateError('ElevenLabs TTS network error: ${e.message}');
    }

    final audioBytes = response.data;
    if (audioBytes == null || audioBytes.isEmpty) {
      throw StateError('ElevenLabs TTS returned empty audio');
    }

    // Play the MP3 audio bytes via just_audio.
    _isSpeaking = true;
    _speakCompleter = Completer<void>();
    final future = _speakCompleter!.future;

    final source = _Mp3BytesAudioSource(Uint8List.fromList(audioBytes));
    await _player!.setAudioSource(source);
    // Re-apply stored speech rate after setAudioSource, which resets speed.
    // Without this, rate set via setSpeechRate() before speak() is lost.
    await _player!.setSpeed(_rate);
    // play() starts playback asynchronously — don't await it.
    // The _speakCompleter is completed by the playerStateStream listener
    // when ProcessingState.completed fires.
    unawaited(_player!.play());

    return future;
  }

  @override
  Future<void> setSpeechRate(double rate) async {
    // Store rate so it survives calls before initialize() and across
    // setAudioSource() resets in speak(). See regression ledger.
    _rate = rate;
    if (_player != null) {
      await _player!.setSpeed(rate);
    }
  }

  @override
  Future<void> stop() async {
    if (_player == null) return;
    await _player!.stop();
    _isSpeaking = false;
    _speakCompleter?.complete();
    _speakCompleter = null;
  }

  @override
  bool get isSpeaking => _isSpeaking;

  @override
  void dispose() {
    stop();
    _player?.dispose();
    _player = null;
  }
}

/// Audio source that serves MP3 bytes from memory.
///
/// Used to feed the MP3 response from the ElevenLabs proxy directly
/// to just_audio's AudioPlayer without writing to disk.
// ignore: experimental_member_use
class _Mp3BytesAudioSource extends StreamAudioSource {
  final Uint8List _bytes;

  _Mp3BytesAudioSource(this._bytes);

  @override
  // ignore: experimental_member_use
  Future<StreamAudioResponse> request([int? start, int? end]) async {
    final effectiveStart = start ?? 0;
    final effectiveEnd = end ?? _bytes.length;

    // ignore: experimental_member_use
    return StreamAudioResponse(
      sourceLength: _bytes.length,
      contentLength: effectiveEnd - effectiveStart,
      offset: effectiveStart,
      stream: Stream.value(_bytes.sublist(effectiveStart, effectiveEnd)),
      contentType: 'audio/mpeg',
    );
  }
}

// coverage:ignore-end
