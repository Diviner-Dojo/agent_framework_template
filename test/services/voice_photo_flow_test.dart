import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/services/voice_session_orchestrator.dart';
import 'package:agentic_journal/services/audio_file_service.dart';
import 'package:agentic_journal/services/speech_recognition_service.dart';
import 'package:agentic_journal/services/text_to_speech_service.dart';
import 'package:agentic_journal/services/audio_focus_service.dart';

/// Minimal fake STT that can be controlled by tests.
class FakeSttService implements SpeechRecognitionService {
  bool _initialized = false;
  bool _listening = false;
  StreamController<SpeechResult>? _controller;

  @override
  bool get isInitialized => _initialized;
  set isInitialized(bool value) => _initialized = value;

  @override
  bool get isListening => _listening;

  @override
  Future<void> initialize({String? modelPath}) async {
    _initialized = true;
  }

  @override
  Stream<SpeechResult> startListening({AudioFileService? audioFileService}) {
    _listening = true;
    _controller = StreamController<SpeechResult>();
    return _controller!.stream;
  }

  @override
  Future<void> stopListening() async {
    _listening = false;
    await _controller?.close();
    _controller = null;
  }

  @override
  void dispose() {
    _controller?.close();
  }

  /// Emit a speech result to the current stream.
  void emitResult(String text, {bool isFinal = false}) {
    _controller?.add(SpeechResult(text: text, isFinal: isFinal));
  }
}

/// Minimal fake TTS.
class FakeTtsService implements TextToSpeechService {
  bool _speaking = false;
  String? lastSpoken;

  @override
  bool get isSpeaking => _speaking;

  @override
  Future<void> initialize() async {}

  @override
  Future<void> speak(String text) async {
    _speaking = true;
    lastSpoken = text;
    // Simulate instant completion.
    _speaking = false;
  }

  @override
  Future<void> stop() async {
    _speaking = false;
  }

  @override
  Future<void> setSpeechRate(double rate) async {}

  @override
  void dispose() {}
}

/// Minimal fake audio focus.
class FakeAudioFocusService implements AudioFocusService {
  @override
  Stream<AudioFocusEvent> get onFocusChanged =>
      const Stream<AudioFocusEvent>.empty();

  @override
  Future<bool> requestFocus() async => true;

  @override
  Future<void> abandonFocus() async {}

  @override
  void dispose() {}
}

void main() {
  late FakeSttService sttService;
  late FakeTtsService ttsService;
  late FakeAudioFocusService audioFocusService;
  late VoiceSessionOrchestrator orchestrator;

  setUp(() {
    sttService = FakeSttService();
    ttsService = FakeTtsService();
    audioFocusService = FakeAudioFocusService();
    orchestrator = VoiceSessionOrchestrator(
      sttService: sttService,
      ttsService: ttsService,
      audioFocusService: audioFocusService,
      silenceTimeoutSeconds: 15,
      enableThinkingSound: false,
    );
  });

  tearDown(() {
    orchestrator.dispose();
  });

  group('capturePhotoDescription', () {
    test('returns null when STT is not initialized', () async {
      sttService.isInitialized = false;

      final result = await orchestrator.capturePhotoDescription();
      expect(result, isNull);
    });

    test('speaks the prompt before listening', () async {
      sttService.isInitialized = true;

      // Start the capture in a microtask so we can inspect TTS output.
      final future = orchestrator.capturePhotoDescription();

      // Give time for the method to start.
      await Future<void>.delayed(const Duration(milliseconds: 50));

      // The TTS should have spoken the prompt.
      expect(ttsService.lastSpoken, 'Tell me about this photo.');

      // Emit a final result to complete the capture.
      sttService.emitResult('A beautiful sunset', isFinal: true);

      final result = await future;
      expect(result, 'A beautiful sunset');
    });

    test('returns captured text on final result', () async {
      sttService.isInitialized = true;

      final future = orchestrator.capturePhotoDescription();
      await Future<void>.delayed(const Duration(milliseconds: 50));

      // Emit partial then final result.
      sttService.emitResult('My morning', isFinal: false);
      sttService.emitResult('My morning coffee', isFinal: true);

      final result = await future;
      expect(result, 'My morning coffee');
    });
  });
}
