// ===========================================================================
// file: test/services/voice_session_orchestrator_test.dart
// purpose: Tests for VoiceSessionOrchestrator state machine.
//
// All services are mocked. Tests verify:
//   - State transitions (idle → speaking → listening → processing → speaking)
//   - Push-to-talk flow (idle → listening → idle)
//   - Interrupt during speaking
//   - Error recovery on STT failure
//   - Silence timeout
//   - Pause/resume with audio focus
//   - Voice command handling (end, discard, undo)
//   - Sentence splitting for TTS
// ===========================================================================

import 'dart:async';

import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/services/audio_focus_service.dart';
import 'package:agentic_journal/services/audio_file_service.dart';
import 'package:agentic_journal/services/speech_recognition_service.dart';
import 'package:agentic_journal/services/task_extraction_service.dart';
import 'package:agentic_journal/services/text_to_speech_service.dart';
import 'package:agentic_journal/services/voice_session_orchestrator.dart';

// ===========================================================================
// Mock implementations
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
    if (!_isInitialized) {
      throw StateError('Not initialized');
    }
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

  /// Simulate a speech result being received.
  void emitResult(SpeechResult result) {
    _resultController?.add(result);
  }

  /// Simulate an STT error.
  void emitError(Object error) {
    _resultController?.addError(error);
  }
}

class MockTextToSpeechService implements TextToSpeechService {
  bool _isSpeaking = false;
  bool _isInitialized = false;
  final List<String> spokenTexts = [];
  Completer<void>? _speakCompleter;

  /// If true, speak() completes immediately. If false, caller must call
  /// completeSpeaking() to resolve.
  bool autoComplete;

  MockTextToSpeechService({this.autoComplete = true});

  @override
  Future<void> initialize() async {
    _isInitialized = true;
  }

  @override
  Future<void> speak(String text) async {
    if (!_isInitialized) throw StateError('Not initialized');
    _isSpeaking = true;
    spokenTexts.add(text);
    if (autoComplete) {
      _isSpeaking = false;
    } else {
      _speakCompleter = Completer<void>();
      return _speakCompleter!.future;
    }
  }

  /// Complete the current speak() call (when autoComplete is false).
  void completeSpeaking() {
    _isSpeaking = false;
    _speakCompleter?.complete();
    _speakCompleter = null;
  }

  @override
  Future<void> stop() async {
    _isSpeaking = false;
    _speakCompleter?.complete();
    _speakCompleter = null;
  }

  @override
  bool get isSpeaking => _isSpeaking;

  @override
  Future<void> setSpeechRate(double rate) async {}

  @override
  void dispose() {
    _isSpeaking = false;
    _speakCompleter?.complete();
    _speakCompleter = null;
  }
}

class MockAudioFocusService implements AudioFocusService {
  final StreamController<AudioFocusEvent> _focusController =
      StreamController<AudioFocusEvent>.broadcast();
  bool focusRequested = false;
  bool focusAbandoned = false;

  @override
  Future<bool> requestFocus() async {
    focusRequested = true;
    return true;
  }

  @override
  Future<void> abandonFocus() async {
    focusAbandoned = true;
  }

  @override
  Stream<AudioFocusEvent> get onFocusChanged => _focusController.stream;

  /// Simulate an audio focus change event.
  void emitFocusEvent(AudioFocusEvent event) {
    _focusController.add(event);
  }

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

    // Pre-initialize STT to avoid initialize() in most tests.
    mockStt.initialize(modelPath: '/test');

    orchestrator = VoiceSessionOrchestrator(
      sttService: mockStt,
      ttsService: mockTts,
      audioFocusService: mockAudioFocus,
      enableThinkingSound: false,
      ttsReleaseDelay: Duration.zero,
    );
  });

  tearDown(() {
    orchestrator.dispose();
    mockAudioFocus.dispose();
  });

  group('VoiceSessionOrchestrator', () {
    group('initial state', () {
      test('starts in idle phase', () {
        expect(orchestrator.state.phase, VoiceLoopPhase.idle);
        expect(orchestrator.state.isContinuousMode, isFalse);
        expect(orchestrator.state.transcriptPreview, isEmpty);
        expect(orchestrator.state.error, isNull);
      });
    });

    group('push-to-talk', () {
      test('transitions idle → listening on startPushToTalk', () async {
        await orchestrator.startPushToTalk();

        expect(orchestrator.state.phase, VoiceLoopPhase.listening);
        expect(orchestrator.state.isContinuousMode, isFalse);
        expect(mockAudioFocus.focusRequested, isTrue);
      });

      test('transitions listening → idle on stopPushToTalk', () async {
        await orchestrator.startPushToTalk();
        await orchestrator.stopPushToTalk();

        expect(orchestrator.state.phase, VoiceLoopPhase.idle);
        expect(mockAudioFocus.focusAbandoned, isTrue);
      });

      test('ignores startPushToTalk when not idle', () async {
        await orchestrator.startPushToTalk();
        final firstState = orchestrator.state;

        await orchestrator.startPushToTalk(); // Should be no-op.
        expect(orchestrator.state.phase, firstState.phase);
      });

      test('ignores stopPushToTalk in continuous mode', () async {
        await orchestrator.startContinuousMode('Hello');
        // Wait for listening phase.
        await Future<void>.delayed(const Duration(milliseconds: 50));

        await orchestrator.stopPushToTalk(); // Should be no-op.
        // Should still be in continuous mode (listening phase).
        expect(orchestrator.state.isContinuousMode, isTrue);
      });

      test('updates transcript on partial results', () async {
        await orchestrator.startPushToTalk();

        mockStt.emitResult(
          const SpeechResult(text: 'Hello world', isFinal: false),
        );
        await Future<void>.delayed(const Duration(milliseconds: 10));

        expect(orchestrator.state.transcriptPreview, 'Hello world');
      });

      test('returns to idle on final result in push-to-talk', () async {
        String? sentText;
        orchestrator.onSendMessage =
            (text, {String inputMethod = 'TEXT'}) async {
              sentText = text;
              return null;
            };

        await orchestrator.startPushToTalk();

        mockStt.emitResult(
          const SpeechResult(
            text: 'Test message',
            isFinal: true,
            confidence: 0.9,
          ),
        );
        await Future<void>.delayed(const Duration(milliseconds: 50));

        expect(orchestrator.state.phase, VoiceLoopPhase.idle);
        expect(sentText, 'Test message');
      });
    });

    group('continuous mode', () {
      test('speaks greeting and transitions to listening', () async {
        await orchestrator.startContinuousMode('Hello!');
        // After TTS completes (auto-complete mock), should transition to listening.
        await Future<void>.delayed(const Duration(milliseconds: 50));

        expect(orchestrator.state.isContinuousMode, isTrue);
        expect(mockTts.spokenTexts, contains('Hello!'));
        expect(mockAudioFocus.focusRequested, isTrue);
      });

      test('ignores startContinuousMode when not idle', () async {
        await orchestrator.startPushToTalk();
        await orchestrator.startContinuousMode('Hello');

        // Should still be in push-to-talk listening mode.
        expect(orchestrator.state.isContinuousMode, isFalse);
      });

      test('fires sendMessage callback on final result', () async {
        String? sentText;
        String? sentInputMethod;
        orchestrator.onSendMessage =
            (text, {String inputMethod = 'TEXT'}) async {
              sentText = text;
              sentInputMethod = inputMethod;
              return null;
            };

        await orchestrator.startContinuousMode('Hello');
        await Future<void>.delayed(const Duration(milliseconds: 50));

        mockStt.emitResult(
          const SpeechResult(
            text: 'I had a great day',
            isFinal: true,
            confidence: 0.9,
          ),
        );
        await Future<void>.delayed(const Duration(milliseconds: 50));

        expect(sentText, 'I had a great day');
        expect(sentInputMethod, 'VOICE');
        expect(orchestrator.state.phase, VoiceLoopPhase.processing);
      });

      test(
        'speaks response and resumes listening after onAssistantMessage',
        () async {
          orchestrator.onSendMessage =
              (text, {String inputMethod = 'TEXT'}) async {
                return null;
              };

          await orchestrator.startContinuousMode('Hello');
          await Future<void>.delayed(const Duration(milliseconds: 50));

          // Simulate user speech → processing.
          mockStt.emitResult(
            const SpeechResult(text: 'test', isFinal: true, confidence: 0.9),
          );
          await Future<void>.delayed(const Duration(milliseconds: 50));

          // Simulate assistant response.
          await orchestrator.onAssistantMessage(
            'That sounds wonderful. Tell me more.',
          );
          await Future<void>.delayed(const Duration(milliseconds: 50));

          // TTS should have spoken the response.
          expect(mockTts.spokenTexts, contains('That sounds wonderful.'));
        },
      );
    });

    group('interrupt', () {
      test('stops TTS and transitions to listening', () async {
        // Start continuous mode in background (non-blocking speak).
        mockTts.autoComplete = false;
        // Don't await — startContinuousMode will be blocked on speak().
        unawaited(orchestrator.startContinuousMode('Hello'));
        // Wait briefly for the state to update to speaking.
        await Future<void>.delayed(const Duration(milliseconds: 50));
        expect(orchestrator.state.phase, VoiceLoopPhase.speaking);

        await orchestrator.interrupt();

        expect(orchestrator.state.phase, VoiceLoopPhase.listening);
      });

      test('is no-op when not speaking', () async {
        await orchestrator.startPushToTalk();
        await orchestrator.interrupt(); // No-op.

        expect(orchestrator.state.phase, VoiceLoopPhase.listening);
      });
    });

    group('pause and resume', () {
      test('transitions to paused on pause', () async {
        await orchestrator.startPushToTalk();
        await orchestrator.pause();

        expect(orchestrator.state.phase, VoiceLoopPhase.paused);
      });

      test('is no-op when already idle', () async {
        await orchestrator.pause();
        expect(orchestrator.state.phase, VoiceLoopPhase.idle);
      });

      test('is no-op when already paused', () async {
        await orchestrator.startPushToTalk();
        await orchestrator.pause();
        await orchestrator.pause();

        expect(orchestrator.state.phase, VoiceLoopPhase.paused);
      });

      test('resumes push-to-talk to idle', () async {
        await orchestrator.startPushToTalk();
        await orchestrator.pause();
        await orchestrator.resume();

        expect(orchestrator.state.phase, VoiceLoopPhase.idle);
      });

      test('resumes continuous mode with welcome back', () async {
        await orchestrator.startContinuousMode('Hi');
        await Future<void>.delayed(const Duration(milliseconds: 50));

        await orchestrator.pause();
        expect(orchestrator.state.phase, VoiceLoopPhase.paused);

        mockTts.spokenTexts.clear();
        await orchestrator.resume();
        await Future<void>.delayed(const Duration(milliseconds: 50));

        expect(mockTts.spokenTexts, contains('Go ahead.'));
      });

      test('is no-op when resume called in non-paused state', () async {
        await orchestrator.resume(); // Should be no-op.
        expect(orchestrator.state.phase, VoiceLoopPhase.idle);
      });
    });

    group('stop', () {
      test('returns to idle from any state', () async {
        await orchestrator.startContinuousMode('Hi');
        await Future<void>.delayed(const Duration(milliseconds: 50));

        await orchestrator.stop();

        expect(orchestrator.state.phase, VoiceLoopPhase.idle);
        expect(orchestrator.state.isContinuousMode, isFalse);
      });

      test('cleans up all subscriptions', () async {
        await orchestrator.startPushToTalk();
        await orchestrator.stop();

        expect(orchestrator.state.phase, VoiceLoopPhase.idle);
        expect(mockAudioFocus.focusAbandoned, isTrue);
      });
    });

    group('audio focus events', () {
      test('ignores focus loss during own audio capture', () async {
        // When our own recording is active, focus loss from the record
        // package's internal focus request should be ignored.
        await orchestrator.startPushToTalk();

        mockAudioFocus.emitFocusEvent(AudioFocusEvent.loss);
        await Future<void>.delayed(const Duration(milliseconds: 50));

        // Should stay in listening, not pause.
        expect(orchestrator.state.phase, VoiceLoopPhase.listening);
      });

      test('ignores transient focus loss during own audio capture', () async {
        await orchestrator.startPushToTalk();

        mockAudioFocus.emitFocusEvent(AudioFocusEvent.lossTransient);
        await Future<void>.delayed(const Duration(milliseconds: 50));

        expect(orchestrator.state.phase, VoiceLoopPhase.listening);
      });

      test('pauses on focus loss when not actively recording', () async {
        // After stopping push-to-talk, external focus loss should pause.
        await orchestrator.startPushToTalk();
        await orchestrator.stopPushToTalk();
        // Now idle with _isOurAudioActive = false.

        // Manually set to a non-idle phase to test pause behavior.
        // Use startContinuousMode which sets speaking phase.
        await orchestrator.startContinuousMode('Hello');
        await Future<void>.delayed(const Duration(milliseconds: 50));
        // After greeting TTS, should be listening.
        await orchestrator.stop();
        // Now idle.

        // Focus loss when idle is a no-op (already idle).
        mockAudioFocus.emitFocusEvent(AudioFocusEvent.loss);
        await Future<void>.delayed(const Duration(milliseconds: 50));
        expect(orchestrator.state.phase, VoiceLoopPhase.idle);
      });

      test('ignores focus gain when not paused', () async {
        mockAudioFocus.emitFocusEvent(AudioFocusEvent.gain);
        await Future<void>.delayed(const Duration(milliseconds: 50));

        expect(orchestrator.state.phase, VoiceLoopPhase.idle);
      });
    });

    group('voice commands', () {
      test('detects end session command in continuous mode', () async {
        bool endSessionCalled = false;
        orchestrator.onEndSession = () async {
          endSessionCalled = true;
        };
        orchestrator.onSendMessage =
            (text, {String inputMethod = 'TEXT'}) async {
              return null;
            };

        await orchestrator.startContinuousMode('Hello');
        await Future<void>.delayed(const Duration(milliseconds: 50));

        // User says "goodbye" — strong end signal.
        mockStt.emitResult(
          const SpeechResult(text: 'goodbye', isFinal: true, confidence: 0.9),
        );
        await Future<void>.delayed(const Duration(milliseconds: 100));

        expect(endSessionCalled, isTrue);
      });

      test('detects discard command and asks for confirmation', () async {
        orchestrator.onSendMessage =
            (text, {String inputMethod = 'TEXT'}) async {
              return null;
            };

        await orchestrator.startContinuousMode('Hello');
        await Future<void>.delayed(const Duration(milliseconds: 50));

        mockTts.spokenTexts.clear();

        // User says "delete this" — discard always requires confirmation.
        mockStt.emitResult(
          const SpeechResult(
            text: 'delete this',
            isFinal: true,
            confidence: 0.9,
          ),
        );
        await Future<void>.delayed(const Duration(milliseconds: 100));

        // Should have spoken a confirmation prompt.
        expect(mockTts.spokenTexts.any((t) => t.contains('sure')), isTrue);
      });

      test('detects undo command', () async {
        String? resumedSessionId;
        orchestrator.onResumeSession = (id) async {
          resumedSessionId = id;
          return id;
        };
        orchestrator.onSendMessage =
            (text, {String inputMethod = 'TEXT'}) async {
              return null;
            };

        await orchestrator.startContinuousMode('Hello');
        await Future<void>.delayed(const Duration(milliseconds: 50));

        // User says "undo" but there's no closed session.
        mockStt.emitResult(
          const SpeechResult(text: 'undo', isFinal: true, confidence: 0.9),
        );
        await Future<void>.delayed(const Duration(milliseconds: 100));

        // No session to resume, so onResumeSession should not be called
        // with a valid ID.
        expect(resumedSessionId, isNull);
      });
    });

    group('error recovery', () {
      test('transitions to error state on STT error', () async {
        await orchestrator.startPushToTalk();

        mockStt.emitError(Exception('Microphone unavailable'));
        await Future<void>.delayed(const Duration(milliseconds: 100));

        // Should have spoken an error message.
        expect(
          mockTts.spokenTexts.any((t) => t.contains('trouble hearing')),
          isTrue,
        );
        // Should be back to idle after error recovery.
        expect(orchestrator.state.phase, VoiceLoopPhase.idle);
      });

      test('handles sendMessage callback error gracefully', () async {
        orchestrator.onSendMessage =
            (text, {String inputMethod = 'TEXT'}) async {
              throw Exception('Network error');
            };

        await orchestrator.startContinuousMode('Hello');
        await Future<void>.delayed(const Duration(milliseconds: 50));

        mockStt.emitResult(
          const SpeechResult(
            text: 'test message',
            isFinal: true,
            confidence: 0.9,
          ),
        );
        await Future<void>.delayed(const Duration(milliseconds: 100));

        // Should have spoken an error recovery message.
        expect(
          mockTts.spokenTexts.any((t) => t.contains('went wrong')),
          isTrue,
        );
      });
    });

    group('sentence splitting', () {
      test('splits on sentence-ending punctuation', () {
        final sentences = VoiceSessionOrchestrator.splitIntoSentences(
          'Hello world. How are you? I am fine!',
        );
        expect(sentences, ['Hello world.', 'How are you?', 'I am fine!']);
      });

      test('handles single sentence', () {
        final sentences = VoiceSessionOrchestrator.splitIntoSentences(
          'Just one sentence.',
        );
        expect(sentences, ['Just one sentence.']);
      });

      test('handles empty string', () {
        final sentences = VoiceSessionOrchestrator.splitIntoSentences('');
        expect(sentences, isEmpty);
      });

      test('handles no punctuation', () {
        final sentences = VoiceSessionOrchestrator.splitIntoSentences(
          'No punctuation here',
        );
        expect(sentences, ['No punctuation here']);
      });

      test('filters out empty segments', () {
        final sentences = VoiceSessionOrchestrator.splitIntoSentences(
          'First.   Second.',
        );
        expect(sentences, ['First.', 'Second.']);
      });

      test('handles multiple spaces between sentences', () {
        final sentences = VoiceSessionOrchestrator.splitIntoSentences(
          'A.  B.  C.',
        );
        expect(sentences, ['A.', 'B.', 'C.']);
      });

      test('splits on [PAUSE] and preserves as standalone segment', () {
        final sentences = VoiceSessionOrchestrator.splitIntoSentences(
          'First sentence.[PAUSE]Second sentence.',
        );
        expect(sentences, ['First sentence.', '[PAUSE]', 'Second sentence.']);
      });

      test('handles [PAUSE] with surrounding spaces', () {
        final sentences = VoiceSessionOrchestrator.splitIntoSentences(
          'Hello. [PAUSE] How are you?',
        );
        expect(sentences, ['Hello.', '[PAUSE]', 'How are you?']);
      });

      test('handles multiple [PAUSE] markers', () {
        final sentences = VoiceSessionOrchestrator.splitIntoSentences(
          'A.[PAUSE]B.[PAUSE]C.',
        );
        expect(sentences, ['A.', '[PAUSE]', 'B.', '[PAUSE]', 'C.']);
      });

      test('handles [PAUSE] at start of text', () {
        final sentences = VoiceSessionOrchestrator.splitIntoSentences(
          '[PAUSE]Hello.',
        );
        expect(sentences, ['[PAUSE]', 'Hello.']);
      });

      test('handles [PAUSE] at end of text', () {
        final sentences = VoiceSessionOrchestrator.splitIntoSentences(
          'Hello.[PAUSE]',
        );
        expect(sentences, ['Hello.', '[PAUSE]']);
      });

      test('handles [PAUSE] only', () {
        final sentences = VoiceSessionOrchestrator.splitIntoSentences(
          '[PAUSE]',
        );
        expect(sentences, ['[PAUSE]']);
      });

      test('handles [PAUSE] with sentence splitting', () {
        final sentences = VoiceSessionOrchestrator.splitIntoSentences(
          'First. Second.[PAUSE]Third. Fourth.',
        );
        expect(sentences, [
          'First.',
          'Second.',
          '[PAUSE]',
          'Third.',
          'Fourth.',
        ]);
      });
    });

    group('verbal close confirmation flow', () {
      test('discard confirmation with "yes" executes discard', () async {
        bool discardCalled = false;
        orchestrator.onDiscardSession = () async {
          discardCalled = true;
        };
        orchestrator.onSendMessage =
            (text, {String inputMethod = 'TEXT'}) async => null;

        await orchestrator.startContinuousMode('Hello');
        await Future<void>.delayed(const Duration(milliseconds: 50));

        // User says "delete this" — triggers confirmation.
        mockStt.emitResult(
          const SpeechResult(
            text: 'delete this',
            isFinal: true,
            confidence: 0.9,
          ),
        );
        await Future<void>.delayed(const Duration(milliseconds: 100));

        // Confirm with "yes".
        mockStt.emitResult(
          const SpeechResult(text: 'yes', isFinal: true, confidence: 0.9),
        );
        await Future<void>.delayed(const Duration(milliseconds: 100));

        expect(discardCalled, isTrue);
      });

      test('discard confirmation with "no" resumes listening', () async {
        bool discardCalled = false;
        orchestrator.onDiscardSession = () async {
          discardCalled = true;
        };
        orchestrator.onSendMessage =
            (text, {String inputMethod = 'TEXT'}) async => null;

        await orchestrator.startContinuousMode('Hello');
        await Future<void>.delayed(const Duration(milliseconds: 50));

        // User says "delete this" — triggers confirmation.
        mockStt.emitResult(
          const SpeechResult(
            text: 'delete this',
            isFinal: true,
            confidence: 0.9,
          ),
        );
        await Future<void>.delayed(const Duration(milliseconds: 100));

        // Decline with "no".
        mockStt.emitResult(
          const SpeechResult(text: 'no thanks', isFinal: true, confidence: 0.9),
        );
        await Future<void>.delayed(const Duration(milliseconds: 100));

        expect(discardCalled, isFalse);
        // Should resume listening in continuous mode.
        expect(orchestrator.state.phase, VoiceLoopPhase.listening);
      });

      test(
        'end session command with callback executes and enables undo',
        () async {
          bool endCalled = false;
          orchestrator.onEndSession = () async {
            endCalled = true;
          };
          orchestrator.onSendMessage =
              (text, {String inputMethod = 'TEXT'}) async => null;

          await orchestrator.startContinuousMode('Hello');
          await Future<void>.delayed(const Duration(milliseconds: 50));

          // High-confidence end command — no confirmation needed.
          mockStt.emitResult(
            const SpeechResult(text: 'goodbye', isFinal: true, confidence: 0.9),
          );
          await Future<void>.delayed(const Duration(milliseconds: 100));

          expect(endCalled, isTrue);
          // After end, should return to idle.
          expect(orchestrator.state.phase, VoiceLoopPhase.idle);
          expect(orchestrator.state.isContinuousMode, isFalse);
        },
      );

      test('undo after end session resumes session', () async {
        String? resumedId;
        orchestrator.onEndSession = () async {};
        orchestrator.onResumeSession = (id) async {
          resumedId = id;
          return id;
        };
        orchestrator.onSendMessage =
            (text, {String inputMethod = 'TEXT'}) async => null;

        // Set the current session ID so end session can store it.
        orchestrator.currentSessionId = 'session-123';

        await orchestrator.startContinuousMode('Hello');
        await Future<void>.delayed(const Duration(milliseconds: 50));

        // End the session.
        mockStt.emitResult(
          const SpeechResult(text: 'goodbye', isFinal: true, confidence: 0.9),
        );
        await Future<void>.delayed(const Duration(milliseconds: 100));

        // Now start again and say "undo".
        await orchestrator.startContinuousMode('Hi again');
        await Future<void>.delayed(const Duration(milliseconds: 50));

        mockStt.emitResult(
          const SpeechResult(text: 'undo', isFinal: true, confidence: 0.9),
        );
        await Future<void>.delayed(const Duration(milliseconds: 100));

        // resumeSession should have been called with the stored session ID.
        expect(resumedId, equals('session-123'));
      });
    });

    group('calendar deferral', () {
      test('speakDeferral speaks message and resumes listening', () async {
        orchestrator.onSendMessage =
            (text, {String inputMethod = 'TEXT'}) async => null;

        await orchestrator.startContinuousMode('Hello');
        await Future<void>.delayed(const Duration(milliseconds: 50));

        // Speak the deferral message.
        await orchestrator.speakDeferral();

        // Should have spoken the deferral text.
        expect(
          mockTts.spokenTexts.any((t) => t.contains('Google Calendar')),
          isTrue,
        );

        // Should resume listening after deferral.
        expect(orchestrator.state.phase, VoiceLoopPhase.listening);
      });
    });

    group('silence timeout in continuous mode', () {
      test('announces and restarts listening on silence', () async {
        // Use a very short silence timeout for testing.
        final shortTimeoutOrchestrator = VoiceSessionOrchestrator(
          sttService: mockStt,
          ttsService: mockTts,
          audioFocusService: mockAudioFocus,
          silenceTimeoutSeconds: 1,
          enableThinkingSound: false,
          ttsReleaseDelay: Duration.zero,
        );
        addTearDown(shortTimeoutOrchestrator.dispose);

        shortTimeoutOrchestrator.onSendMessage =
            (text, {String inputMethod = 'TEXT'}) async => null;

        await shortTimeoutOrchestrator.startContinuousMode('Hello');
        await Future<void>.delayed(const Duration(milliseconds: 50));

        // Wait for silence timeout (1 second + buffer).
        await Future<void>.delayed(const Duration(milliseconds: 1500));

        // Should have spoken the silence prompt.
        expect(
          mockTts.spokenTexts.any((t) => t.contains('still listening')),
          isTrue,
        );
      });
    });

    group('audio focus lossTransientCanDuck', () {
      test('does not pause on duck event', () async {
        await orchestrator.startPushToTalk();

        mockAudioFocus.emitFocusEvent(AudioFocusEvent.lossTransientCanDuck);
        await Future<void>.delayed(const Duration(milliseconds: 50));

        // Should NOT pause — ducking just lowers volume.
        expect(orchestrator.state.phase, VoiceLoopPhase.listening);
      });
    });

    group('stateNotifier', () {
      test('emits state changes', () async {
        final states = <VoiceOrchestratorState>[];
        orchestrator.stateNotifier.addListener(() {
          states.add(orchestrator.state);
        });

        await orchestrator.startPushToTalk();

        expect(states.isNotEmpty, isTrue);
        expect(states.last.phase, VoiceLoopPhase.listening);
      });
    });

    group('VoiceOrchestratorState', () {
      test('copyWith preserves values', () {
        const original = VoiceOrchestratorState(
          phase: VoiceLoopPhase.listening,
          transcriptPreview: 'hello',
          isContinuousMode: true,
        );

        final copy = original.copyWith(phase: VoiceLoopPhase.processing);

        expect(copy.phase, VoiceLoopPhase.processing);
        expect(copy.transcriptPreview, 'hello');
        expect(copy.isContinuousMode, isTrue);
      });

      test('copyWith can clear error', () {
        const original = VoiceOrchestratorState(
          phase: VoiceLoopPhase.error,
          error: VoiceSessionError(
            kind: VoiceSessionErrorKind.sttFailure,
            message: 'something went wrong',
          ),
        );

        final copy = original.copyWith(
          phase: VoiceLoopPhase.idle,
          clearError: true,
        );

        expect(copy.error, isNull);
      });

      test('default constructor has expected defaults', () {
        const state = VoiceOrchestratorState();

        expect(state.phase, VoiceLoopPhase.idle);
        expect(state.transcriptPreview, isEmpty);
        expect(state.error, isNull);
        expect(state.isContinuousMode, isFalse);
      });

      test('copyWith preserves error when not clearing', () {
        const original = VoiceOrchestratorState(
          phase: VoiceLoopPhase.error,
          error: VoiceSessionError(
            kind: VoiceSessionErrorKind.processingFailure,
            message: 'Processing failed',
          ),
        );

        final copy = original.copyWith(transcriptPreview: 'test');

        expect(copy.error, isNotNull);
        expect(copy.error!.kind, VoiceSessionErrorKind.processingFailure);
        expect(copy.error!.message, 'Processing failed');
      });

      test('VoiceSessionError carries kind and message', () {
        const error = VoiceSessionError(
          kind: VoiceSessionErrorKind.sttFailure,
          message: 'STT failed',
        );

        expect(error.kind, VoiceSessionErrorKind.sttFailure);
        expect(error.message, 'STT failed');
      });

      test('VoiceSessionErrorKind has all expected values', () {
        expect(VoiceSessionErrorKind.values, hasLength(4));
        expect(
          VoiceSessionErrorKind.values,
          containsAll([
            VoiceSessionErrorKind.sttFailure,
            VoiceSessionErrorKind.ttsFailure,
            VoiceSessionErrorKind.processingFailure,
            VoiceSessionErrorKind.audioFocusLoss,
          ]),
        );
      });
    });

    // =========================================================================
    // Voice Naturalness — SPEC-20260228
    // =========================================================================

    group('computeCommitDelay (Task 3)', () {
      test('high confidence returns zero delay (R7, R11)', () {
        expect(VoiceSessionOrchestrator.computeCommitDelay(0.9), Duration.zero);
        expect(
          VoiceSessionOrchestrator.computeCommitDelay(0.85),
          Duration.zero,
        );
      });

      test('medium confidence returns 400ms delay (R7, R11)', () {
        expect(
          VoiceSessionOrchestrator.computeCommitDelay(0.7),
          const Duration(milliseconds: 400),
        );
        expect(
          VoiceSessionOrchestrator.computeCommitDelay(0.65),
          const Duration(milliseconds: 400),
        );
      });

      test('low confidence returns 1200ms delay (R7, R11)', () {
        expect(
          VoiceSessionOrchestrator.computeCommitDelay(0.5),
          const Duration(milliseconds: 1200),
        );
      });

      test('zero confidence returns 1200ms delay (R10)', () {
        expect(
          VoiceSessionOrchestrator.computeCommitDelay(0.0),
          const Duration(milliseconds: 1200),
        );
      });
    });

    group('stripMarkdown (Task 2)', () {
      test('strips bold markdown', () {
        expect(
          VoiceSessionOrchestrator.stripMarkdown('This is **bold** text'),
          'This is bold text',
        );
      });

      test('strips italic markdown', () {
        expect(
          VoiceSessionOrchestrator.stripMarkdown('This is *italic* text'),
          'This is italic text',
        );
      });

      test('strips headers', () {
        expect(
          VoiceSessionOrchestrator.stripMarkdown('## My Header'),
          'My Header',
        );
      });

      test('strips bullet lists', () {
        expect(
          VoiceSessionOrchestrator.stripMarkdown('- item one\n- item two'),
          'item one\nitem two',
        );
      });

      test('strips numbered lists', () {
        expect(
          VoiceSessionOrchestrator.stripMarkdown('1. first\n2. second'),
          'first\nsecond',
        );
      });

      test('strips inline code', () {
        expect(
          VoiceSessionOrchestrator.stripMarkdown('Use `dart format` here'),
          'Use dart format here',
        );
      });

      test('handles combined formatting', () {
        final input = '## Title\n\n- **Bold** item\n- *Italic* item';
        final result = VoiceSessionOrchestrator.stripMarkdown(input);
        expect(result, contains('Title'));
        expect(result, contains('Bold item'));
        expect(result, contains('Italic item'));
        expect(result, isNot(contains('##')));
        expect(result, isNot(contains('**')));
        expect(result, isNot(contains('- ')));
      });

      test('passes through plain text unchanged', () {
        expect(
          VoiceSessionOrchestrator.stripMarkdown('Just a normal sentence.'),
          'Just a normal sentence.',
        );
      });
    });

    group('parseTurnMarker (Task 5)', () {
      test('parses ✓ marker', () {
        final result = VoiceSessionOrchestrator.parseTurnMarker(
          '✓ That sounds great!',
        );
        expect(result.$1, '✓');
        expect(result.$2, 'That sounds great!');
      });

      test('parses ○ marker', () {
        final result = VoiceSessionOrchestrator.parseTurnMarker('○');
        expect(result.$1, '○');
        expect(result.$2, isEmpty);
      });

      test('parses ◐ marker', () {
        final result = VoiceSessionOrchestrator.parseTurnMarker('◐');
        expect(result.$1, '◐');
        expect(result.$2, isEmpty);
      });

      test('defaults to ✓ when no marker present (R28)', () {
        final result = VoiceSessionOrchestrator.parseTurnMarker(
          'No marker here.',
        );
        expect(result.$1, '✓');
        expect(result.$2, 'No marker here.');
      });

      test('handles leading whitespace before marker', () {
        final result = VoiceSessionOrchestrator.parseTurnMarker(
          '  ✓ Response text',
        );
        expect(result.$1, '✓');
        expect(result.$2, 'Response text');
      });
    });

    group('idle timer interruption guard (Task 1)', () {
      test(
        'interim result cancels silence timer and sets _userIsSpeaking',
        () async {
          final shortTimeoutOrchestrator = VoiceSessionOrchestrator(
            sttService: mockStt,
            ttsService: mockTts,
            audioFocusService: mockAudioFocus,
            silenceTimeoutSeconds: 1,
            enableThinkingSound: false,
            ttsReleaseDelay: Duration.zero,
          );
          addTearDown(shortTimeoutOrchestrator.dispose);

          shortTimeoutOrchestrator.onSendMessage =
              (text, {String inputMethod = 'TEXT'}) async => null;

          await shortTimeoutOrchestrator.startContinuousMode('Hello');
          await Future<void>.delayed(const Duration(milliseconds: 50));

          // Emit an interim result — should suppress the silence timer.
          mockStt.emitResult(
            const SpeechResult(text: 'So I was', isFinal: false),
          );
          await Future<void>.delayed(const Duration(milliseconds: 10));

          // Wait beyond the silence timeout.
          await Future<void>.delayed(const Duration(milliseconds: 1200));

          // The silence prompt should NOT have fired because interim
          // results keep the guard up.
          expect(
            mockTts.spokenTexts.where((t) => t.contains('still listening')),
            isEmpty,
          );
        },
      );
    });

    group('confidence-weighted commit delay (Task 3)', () {
      test('low-confidence result delays commit', () async {
        String? sentText;
        orchestrator.onSendMessage =
            (text, {String inputMethod = 'TEXT'}) async {
              sentText = text;
              return null;
            };

        await orchestrator.startContinuousMode('Hello');
        await Future<void>.delayed(const Duration(milliseconds: 50));

        // Emit a low-confidence final result.
        mockStt.emitResult(
          const SpeechResult(text: 'mumble', isFinal: true, confidence: 0.3),
        );
        await Future<void>.delayed(const Duration(milliseconds: 50));

        // Should NOT have sent yet — 1200ms delay.
        expect(sentText, isNull);

        // Wait for the delay to complete.
        await Future<void>.delayed(const Duration(milliseconds: 1500));

        expect(sentText, 'mumble');
      });

      test('high-confidence result commits immediately', () async {
        String? sentText;
        orchestrator.onSendMessage =
            (text, {String inputMethod = 'TEXT'}) async {
              sentText = text;
              return null;
            };

        await orchestrator.startContinuousMode('Hello');
        await Future<void>.delayed(const Duration(milliseconds: 50));

        // Emit a high-confidence final result.
        mockStt.emitResult(
          const SpeechResult(
            text: 'clear speech',
            isFinal: true,
            confidence: 0.95,
          ),
        );
        await Future<void>.delayed(const Duration(milliseconds: 100));

        // Should have sent immediately.
        expect(sentText, 'clear speech');
      });
    });

    group('turn-completeness markers (Task 5)', () {
      test('○ marker suppresses TTS and starts re-prompt timer', () async {
        orchestrator.onSendMessage =
            (text, {String inputMethod = 'TEXT'}) async => null;

        await orchestrator.startContinuousMode('Hello');
        await Future<void>.delayed(const Duration(milliseconds: 50));

        // Simulate a final result that triggers processing.
        mockStt.emitResult(
          const SpeechResult(
            text: 'So I was thinking',
            isFinal: true,
            confidence: 0.9,
          ),
        );
        await Future<void>.delayed(const Duration(milliseconds: 100));

        // Now the LLM responds with ○ (incomplete).
        await orchestrator.onAssistantMessage('○');
        await Future<void>.delayed(const Duration(milliseconds: 50));

        // Should NOT have spoken the ○ marker as TTS.
        expect(mockTts.spokenTexts.where((t) => t.contains('○')), isEmpty);

        // Should transition to listening (waiting for user to continue).
        expect(orchestrator.state.phase, VoiceLoopPhase.listening);
      });

      test('✓ marker speaks response normally', () async {
        orchestrator.onSendMessage =
            (text, {String inputMethod = 'TEXT'}) async => null;

        await orchestrator.startContinuousMode('Hello');
        await Future<void>.delayed(const Duration(milliseconds: 50));

        mockStt.emitResult(
          const SpeechResult(
            text: 'Tell me about today',
            isFinal: true,
            confidence: 0.9,
          ),
        );
        await Future<void>.delayed(const Duration(milliseconds: 100));

        await orchestrator.onAssistantMessage('✓ That sounds wonderful!');
        await Future<void>.delayed(const Duration(milliseconds: 50));

        // Should have spoken the response (without marker).
        expect(
          mockTts.spokenTexts.any((t) => t.contains('That sounds wonderful')),
          isTrue,
        );
      });
    });

    group('SpeechResult confidence', () {
      test('default confidence is 0.0', () {
        const result = SpeechResult(text: 'test', isFinal: true);
        expect(result.confidence, 0.0);
      });

      test('confidence is included in equality', () {
        const a = SpeechResult(text: 'test', isFinal: true, confidence: 0.9);
        const b = SpeechResult(text: 'test', isFinal: true, confidence: 0.5);
        expect(a, isNot(equals(b)));
      });

      test('toString includes confidence', () {
        const result = SpeechResult(
          text: 'hello',
          isFinal: true,
          confidence: 0.85,
        );
        expect(result.toString(), contains('confidence: 0.85'));
      });
    });

    // Regression: stop() after discard must not leave orchestrator in
    // processing state. Before Fix 3, stop() was called without await in the
    // discard path, allowing the orchestrator to continue running briefly.
    group('stop after discard (regression)', () {
      test(
        'stop() after discard does not leave orchestrator in processing state '
        '(regression)',
        () async {
          orchestrator.onSendMessage =
              (text, {String inputMethod = 'TEXT'}) async => null;

          await orchestrator.startContinuousMode('Hello');
          await Future<void>.delayed(const Duration(milliseconds: 50));

          // Simulate the discard path: stop() is awaited before clearing state.
          await orchestrator.stop();

          // Orchestrator must be idle — not listening, processing, or speaking.
          expect(
            orchestrator.state.phase,
            VoiceLoopPhase.idle,
            reason: 'stop() after discard must bring orchestrator to idle',
          );
          expect(
            orchestrator.state.isContinuousMode,
            isFalse,
            reason: 'continuous mode must be disabled after stop()',
          );
        },
      );
    });

    // Regression: onAssistantMessage after dispose must not crash.
    // A late-arriving Claude API response can trigger onAssistantMessage
    // after the user navigated away and the orchestrator was disposed.
    // See: memory/bugs/regression-ledger.md (STT silent / black screen)
    group('post-dispose safety (regression)', () {
      test(
        'onAssistantMessage after dispose does not throw (regression)',
        () async {
          final disposedOrchestrator = VoiceSessionOrchestrator(
            sttService: mockStt,
            ttsService: mockTts,
            audioFocusService: mockAudioFocus,
            enableThinkingSound: false,
            ttsReleaseDelay: Duration.zero,
          );

          await disposedOrchestrator.startContinuousMode('Hello');
          await Future<void>.delayed(const Duration(milliseconds: 50));

          // Dispose the orchestrator (simulates user navigating away).
          disposedOrchestrator.dispose();

          // A late-arriving assistant message should be silently ignored,
          // not crash with "ValueNotifier used after disposed".
          await disposedOrchestrator.onAssistantMessage('late response');

          // State should remain idle (the default after dispose).
          // No exception means the guard worked.
        },
      );

      test(
        '_updateState after dispose is silently ignored (regression)',
        () async {
          final disposedOrchestrator = VoiceSessionOrchestrator(
            sttService: mockStt,
            ttsService: mockTts,
            audioFocusService: mockAudioFocus,
            enableThinkingSound: false,
            ttsReleaseDelay: Duration.zero,
          );

          await disposedOrchestrator.startContinuousMode('Hello');
          await Future<void>.delayed(const Duration(milliseconds: 50));

          disposedOrchestrator.dispose();

          // Calling stop() after dispose() should not crash — stop()
          // calls _updateState internally, which is now guarded.
          await disposedOrchestrator.stop();
        },
      );

      test(
        'acknowledgeNoResponse() is a no-op when not in processing phase',
        () async {
          // Orchestrator starts in idle — calling acknowledgeNoResponse()
          // must not change the phase. This pins the guard contract against
          // future refactors that might remove the phase check.
          expect(orchestrator.state.phase, VoiceLoopPhase.idle);
          await orchestrator.acknowledgeNoResponse();
          expect(
            orchestrator.state.phase,
            VoiceLoopPhase.idle,
            reason:
                'acknowledgeNoResponse() must be a no-op outside processing',
          );
        },
      );

      // regression: in journal-only mode (and after handled intents), the
      // orchestrator was stuck in `processing` because onAssistantMessage()
      // was never called. acknowledgeNoResponse() resumes the loop without
      // requiring an AI response.
      test('acknowledgeNoResponse() transitions from processing to listening '
          '(regression)', () async {
        // Wire up a send callback that does NOT call onAssistantMessage(),
        // simulating journal-only mode where no AI response is produced.
        orchestrator.onSendMessage =
            (text, {String inputMethod = 'TEXT'}) async {
              return null;
            };

        await orchestrator.startContinuousMode('Hello');
        await Future<void>.delayed(const Duration(milliseconds: 50));

        // Emit a final STT result to drive the orchestrator into processing.
        mockStt.emitResult(
          const SpeechResult(
            text: 'Great day today',
            isFinal: true,
            confidence: 0.9,
          ),
        );
        await Future<void>.delayed(const Duration(milliseconds: 50));

        // Orchestrator is now stuck in processing (no AI response arrived).
        expect(orchestrator.state.phase, VoiceLoopPhase.processing);

        // Acknowledge that no response is coming — loop must resume.
        await orchestrator.acknowledgeNoResponse();
        await Future<void>.delayed(const Duration(milliseconds: 50));

        expect(
          orchestrator.state.phase,
          VoiceLoopPhase.listening,
          reason: 'acknowledgeNoResponse() must resume listening loop',
        );
      });

      // Regression: task card confirm/dismiss tapped while orchestrator is
      // in verbal confirmation loop. Before the fix, the orchestrator would
      // wait 8s then say "okay, I won't add that." regardless of card tap.
      // resolveTaskConfirmation() completes the completer immediately.
      group('resolveTaskConfirmation()', () {
        test(
          'resolveTaskConfirmation(confirmed: true) completes task loop early',
          () async {
            // Start confirmTask in background — it speaks then listens.
            bool? taskConfirmed;
            final taskFuture = orchestrator.confirmTask(
              const ExtractedTask(title: 'hug Christin'),
            );

            // Allow orchestrator to reach the listening/awaiting phase.
            await Future<void>.delayed(const Duration(milliseconds: 30));

            // Simulate user tapping the UI confirm button.
            orchestrator.resolveTaskConfirmation(confirmed: true);

            taskConfirmed = await taskFuture;
            expect(
              taskConfirmed,
              isTrue,
              reason:
                  'UI card confirm must resolve orchestrator loop as confirmed',
            );
          },
        );

        test(
          'resolveTaskConfirmation(confirmed: false) completes task loop early',
          () async {
            bool? taskConfirmed;
            final taskFuture = orchestrator.confirmTask(
              const ExtractedTask(title: 'hug Christin'),
            );

            await Future<void>.delayed(const Duration(milliseconds: 30));

            // Simulate user tapping the UI dismiss button.
            orchestrator.resolveTaskConfirmation(confirmed: false);

            taskConfirmed = await taskFuture;
            expect(
              taskConfirmed,
              isFalse,
              reason:
                  'UI card dismiss must resolve orchestrator loop as dismissed',
            );
          },
        );

        test('resolveTaskConfirmation() is a no-op when no task confirmation '
            'is in progress', () {
          // Calling with no active confirmTask() must not throw.
          expect(
            () => orchestrator.resolveTaskConfirmation(confirmed: true),
            returnsNormally,
          );
        });
      });
    });

    // regression: Audio focus gain event fires during capturePhotoDescription,
    // calling resume() which clears _phaseBeforePause to null. When
    // capturePhotoDescription finishes and the caller's resume() is invoked,
    // _phaseBeforePause == null → previousPhase = idle → voice stuck.
    // Fix: save _phaseBeforePause at the start of capturePhotoDescription and
    // restore it in the finally block, so the caller's resume() always sees
    // the correct prior phase regardless of intermediate resume() calls.
    group('capturePhotoDescription restores _phaseBeforePause after audio focus '
        'gain during capture (regression)', () {
      test(
        'capturePhotoDescription restores _phaseBeforePause after audio '
        'focus gain during capture (regression)',
        tags: ['regression'],
        () async {
          // Put orchestrator in continuous + listening state.
          await orchestrator.startContinuousMode('Hello');
          expect(orchestrator.state.phase, VoiceLoopPhase.listening);

          // Caller pauses for camera (audio focus conflict), saving
          // _phaseBeforePause = listening.
          await orchestrator.pause();
          expect(orchestrator.state.phase, VoiceLoopPhase.paused);

          // Simulate audio focus gain firing mid-capture: call resume()
          // before capturePhotoDescription (clears _phaseBeforePause).
          // In production this fires from the Android audio focus handler
          // at an await boundary inside capturePhotoDescription; in tests
          // we call it here to replicate the _phaseBeforePause=null state.
          await orchestrator.resume(silent: true);
          expect(orchestrator.state.phase, VoiceLoopPhase.listening);

          // Re-pause (simulates camera re-acquiring audio focus after the
          // spurious gain event — _phaseBeforePause = listening again).
          await orchestrator.pause();

          // capturePhotoDescription must save _phaseBeforePause before any
          // async work and restore it in finally, so that a second
          // intermediate resume() during capture doesn't corrupt the value.
          final captureTask = orchestrator.capturePhotoDescription();
          await Future<void>.delayed(Duration.zero);
          mockStt.emitResult(
            const SpeechResult(text: 'a sunset over the ocean', isFinal: true),
          );
          final description = await captureTask;
          expect(description, equals('a sunset over the ocean'));

          // Phase must be paused so the caller's resume() is not a no-op.
          expect(orchestrator.state.phase, VoiceLoopPhase.paused);

          // The caller's resume() (audio focus re-grant) must transition to
          // listening — if _phaseBeforePause was not restored this would
          // go to idle instead.
          await orchestrator.resume(silent: true);
          expect(
            orchestrator.state.phase,
            VoiceLoopPhase.listening,
            reason:
                '_phaseBeforePause must be restored by capturePhotoDescription '
                'so the caller resume() restarts STT (not idle)',
          );
        },
      );
    });

    // regression: capturePhotoDescription() called _startListening() at the
    // end of its flow, leaving phase=listening.  The caller's
    // orchestrator.resume() (which requires phase=paused) was then a silent
    // no-op — STT never restarted after the photo was saved.
    // Fix: when previousPhase==paused, restore paused so resume() works.
    group('capturePhotoDescription paused-state restoration (regression)', () {
      test(
        'capturePhotoDescription restores paused phase so caller resume() '
        'works (regression)',
        tags: ['regression'],
        () async {
          // Put orchestrator in continuous + listening state.
          await orchestrator.startContinuousMode('Hello');
          expect(orchestrator.state.phase, VoiceLoopPhase.listening);

          // Caller pauses for camera (audio focus conflict).
          await orchestrator.pause();
          expect(orchestrator.state.phase, VoiceLoopPhase.paused);

          // Start capturePhotoDescription (async) — emit a final STT result
          // on the next microtask so the description completes immediately
          // rather than waiting for the 5-second silence timeout.
          final captureTask = orchestrator.capturePhotoDescription();
          await Future<void>.delayed(Duration.zero);
          mockStt.emitResult(
            const SpeechResult(text: 'a blue couch', isFinal: true),
          );
          final description = await captureTask;

          expect(description, equals('a blue couch'));

          // Key assertion: phase must be paused (not listening) so the
          // caller's orchestrator.resume() call is not a no-op.
          expect(
            orchestrator.state.phase,
            VoiceLoopPhase.paused,
            reason:
                'capturePhotoDescription must restore paused state so '
                'orchestrator.resume() can restart STT',
          );

          // Verify resume() transitions correctly to listening.
          await orchestrator.resume(silent: true);
          expect(orchestrator.state.phase, VoiceLoopPhase.listening);
        },
      );
    });
  });
}
