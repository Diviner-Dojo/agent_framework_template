// ===========================================================================
// file: test/services/voice_orchestrator_calendar_test.dart
// purpose: Tests for VoiceSessionOrchestrator calendar confirmation flow.
//
// Coverage targets (plan §Phase 5C):
//   - Verbal confirmation flow ("yes" → confirm, "no" → dismiss)
//   - Silence timeout → dismiss
//   - Calendar intent during voice mode
//
// See: ADR-0020 (Google Calendar Integration)
// ===========================================================================

import 'dart:async';

import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/services/audio_focus_service.dart';
import 'package:agentic_journal/services/event_extraction_service.dart';
import 'package:agentic_journal/services/audio_file_service.dart';
import 'package:agentic_journal/services/speech_recognition_service.dart';
import 'package:agentic_journal/services/text_to_speech_service.dart';
import 'package:agentic_journal/services/voice_session_orchestrator.dart';

// ===========================================================================
// Mock implementations (matching voice_session_orchestrator_test.dart)
// ===========================================================================

class MockSpeechRecognitionService implements SpeechRecognitionService {
  bool _isInitialized = false;
  bool _isListening = false;
  StreamController<SpeechResult>? _resultController;

  @override
  Future<void> initialize({required String modelPath}) async {
    _isInitialized = true;
  }

  @override
  Stream<SpeechResult> startListening({AudioFileService? audioFileService}) {
    if (!_isInitialized) throw StateError('Not initialized');
    _isListening = true;
    _resultController = StreamController<SpeechResult>.broadcast();
    return _resultController!.stream;
  }

  @override
  Future<void> stopListening() async {
    _isListening = false;
    await _resultController?.close();
    _resultController = null;
  }

  @override
  bool get isListening => _isListening;

  @override
  bool get isInitialized => _isInitialized;

  @override
  void dispose() {
    _isListening = false;
    _resultController?.close();
    _resultController = null;
  }

  void emitResult(SpeechResult result) {
    _resultController?.add(result);
  }
}

class MockTextToSpeechService implements TextToSpeechService {
  bool _isSpeaking = false;
  bool _isInitialized = false;
  final List<String> spokenTexts = [];

  @override
  Future<void> initialize() async {
    _isInitialized = true;
  }

  @override
  Future<void> speak(String text) async {
    if (!_isInitialized) throw StateError('Not initialized');
    _isSpeaking = true;
    spokenTexts.add(text);
    _isSpeaking = false;
  }

  @override
  Future<void> stop() async {
    _isSpeaking = false;
  }

  @override
  bool get isSpeaking => _isSpeaking;

  @override
  Future<void> setSpeechRate(double rate) async {}

  @override
  void dispose() {
    _isSpeaking = false;
  }
}

class MockAudioFocusService implements AudioFocusService {
  final StreamController<AudioFocusEvent> _focusController =
      StreamController<AudioFocusEvent>.broadcast();

  @override
  Future<bool> requestFocus() async => true;

  @override
  Future<void> abandonFocus() async {}

  @override
  Stream<AudioFocusEvent> get onFocusChanged => _focusController.stream;

  @override
  void dispose() {
    _focusController.close();
  }
}

void main() {
  late MockSpeechRecognitionService mockStt;
  late MockTextToSpeechService mockTts;
  late MockAudioFocusService mockAudioFocus;
  late VoiceSessionOrchestrator orchestrator;

  setUp(() {
    mockStt = MockSpeechRecognitionService();
    mockTts = MockTextToSpeechService();
    mockAudioFocus = MockAudioFocusService();

    mockStt.initialize(modelPath: '/test');

    orchestrator = VoiceSessionOrchestrator(
      sttService: mockStt,
      ttsService: mockTts,
      audioFocusService: mockAudioFocus,
      enableThinkingSound: false,
    );
  });

  tearDown(() {
    orchestrator.dispose();
    mockAudioFocus.dispose();
  });

  group('VoiceSessionOrchestrator — calendar confirmation', () {
    test(
      'confirmCalendarEvent speaks prompt and returns false if STT not initialized',
      () async {
        // Create orchestrator with un-initialized STT.
        final uninitStt = MockSpeechRecognitionService();
        final orch = VoiceSessionOrchestrator(
          sttService: uninitStt,
          ttsService: mockTts,
          audioFocusService: mockAudioFocus,
          enableThinkingSound: false,
        );
        addTearDown(orch.dispose);

        final event = ExtractedEvent(
          title: 'Team standup',
          startTime: DateTime.utc(2026, 3, 1, 14, 0),
        );

        final result = await orch.confirmCalendarEvent(event);
        expect(result, isFalse);
      },
    );

    test('confirmCalendarEvent speaks event details prompt', () async {
      orchestrator.onSendMessage =
          (text, {String inputMethod = 'TEXT'}) async => null;

      await orchestrator.startContinuousMode('Hello');
      await Future<void>.delayed(const Duration(milliseconds: 50));

      final event = ExtractedEvent(
        title: 'Team standup',
        startTime: DateTime.utc(2026, 3, 1, 14, 0),
      );

      mockTts.spokenTexts.clear();

      // Start confirmation in background (it waits for speech input).
      final confirmFuture = orchestrator.confirmCalendarEvent(event);

      // Wait for the prompt to be spoken.
      await Future<void>.delayed(const Duration(milliseconds: 100));

      // Should have spoken the confirmation prompt.
      expect(
        mockTts.spokenTexts.any((t) => t.contains('Team standup')),
        isTrue,
      );

      // Emit a "yes" to complete the confirmation.
      mockStt.emitResult(
        const SpeechResult(text: 'yes', isFinal: true, confidence: 0.9),
      );

      final result = await confirmFuture;
      expect(result, isTrue);
    });

    test('confirmCalendarEvent calls onConfirmCalendarEvent on yes', () async {
      bool confirmCalled = false;
      orchestrator.onConfirmCalendarEvent = () async {
        confirmCalled = true;
      };
      orchestrator.onSendMessage =
          (text, {String inputMethod = 'TEXT'}) async => null;

      await orchestrator.startContinuousMode('Hello');
      await Future<void>.delayed(const Duration(milliseconds: 50));

      final event = ExtractedEvent(
        title: 'Lunch',
        startTime: DateTime.utc(2026, 3, 1, 12, 0),
      );

      final confirmFuture = orchestrator.confirmCalendarEvent(event);
      await Future<void>.delayed(const Duration(milliseconds: 100));

      mockStt.emitResult(
        const SpeechResult(text: 'yes', isFinal: true, confidence: 0.9),
      );

      await confirmFuture;
      expect(confirmCalled, isTrue);

      // Should have spoken the adding message.
      expect(mockTts.spokenTexts.any((t) => t.contains('Adding')), isTrue);
    });

    test('confirmCalendarEvent calls onDismissCalendarEvent on no', () async {
      bool dismissCalled = false;
      orchestrator.onDismissCalendarEvent = () async {
        dismissCalled = true;
      };
      orchestrator.onSendMessage =
          (text, {String inputMethod = 'TEXT'}) async => null;

      await orchestrator.startContinuousMode('Hello');
      await Future<void>.delayed(const Duration(milliseconds: 50));

      final event = ExtractedEvent(
        title: 'Dinner',
        startTime: DateTime.utc(2026, 3, 1, 19, 0),
      );

      final confirmFuture = orchestrator.confirmCalendarEvent(event);
      await Future<void>.delayed(const Duration(milliseconds: 100));

      mockStt.emitResult(
        const SpeechResult(text: 'no thanks', isFinal: true, confidence: 0.9),
      );

      final result = await confirmFuture;
      expect(result, isFalse);
      expect(dismissCalled, isTrue);

      // Should have spoken the dismiss feedback.
      expect(mockTts.spokenTexts.any((t) => t.contains("won't add")), isTrue);
    });

    test('confirmCalendarEvent handles silence timeout as dismiss', () async {
      orchestrator.onSendMessage =
          (text, {String inputMethod = 'TEXT'}) async => null;

      await orchestrator.startContinuousMode('Hello');
      await Future<void>.delayed(const Duration(milliseconds: 50));

      final event = ExtractedEvent(
        title: 'Call',
        startTime: DateTime.utc(2026, 3, 1, 10, 0),
      );

      // The confirmation will timeout after 8 seconds (no speech input).
      // For test purposes, we don't wait the full 8s — the mock STT stream
      // closing triggers the null response path.
      final confirmFuture = orchestrator.confirmCalendarEvent(event);
      await Future<void>.delayed(const Duration(milliseconds: 100));

      // Close the STT stream to simulate timeout-like behavior.
      await mockStt.stopListening();
      await Future<void>.delayed(const Duration(milliseconds: 100));

      // The future should resolve with false.
      final result = await confirmFuture;
      expect(result, isFalse);
    });
  });

  group('VoiceSessionOrchestrator — speakDeferral', () {
    test('speaks deferral and resumes listening in continuous mode', () async {
      orchestrator.onSendMessage =
          (text, {String inputMethod = 'TEXT'}) async => null;

      await orchestrator.startContinuousMode('Hello');
      await Future<void>.delayed(const Duration(milliseconds: 50));

      mockTts.spokenTexts.clear();
      await orchestrator.speakDeferral();

      expect(
        mockTts.spokenTexts.any((t) => t.contains('Google Calendar')),
        isTrue,
      );

      // Should resume listening.
      expect(orchestrator.state.phase, VoiceLoopPhase.listening);
    });

    test('speaks deferral and returns to idle in push-to-talk mode', () async {
      mockTts.spokenTexts.clear();

      // In idle state (no continuous mode), just speak the message.
      await orchestrator.speakDeferral();

      expect(
        mockTts.spokenTexts.any((t) => t.contains('Google Calendar')),
        isTrue,
      );

      expect(orchestrator.state.phase, VoiceLoopPhase.idle);
    });
  });
}
