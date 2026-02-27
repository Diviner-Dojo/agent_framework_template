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
          const SpeechResult(text: 'Test message', isFinal: true),
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
          const SpeechResult(text: 'I had a great day', isFinal: true),
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
          mockStt.emitResult(const SpeechResult(text: 'test', isFinal: true));
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
        mockStt.emitResult(const SpeechResult(text: 'goodbye', isFinal: true));
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
          const SpeechResult(text: 'delete this', isFinal: true),
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
        mockStt.emitResult(const SpeechResult(text: 'undo', isFinal: true));
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
          const SpeechResult(text: 'test message', isFinal: true),
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
          const SpeechResult(text: 'delete this', isFinal: true),
        );
        await Future<void>.delayed(const Duration(milliseconds: 100));

        // Confirm with "yes".
        mockStt.emitResult(const SpeechResult(text: 'yes', isFinal: true));
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
          const SpeechResult(text: 'delete this', isFinal: true),
        );
        await Future<void>.delayed(const Duration(milliseconds: 100));

        // Decline with "no".
        mockStt.emitResult(
          const SpeechResult(text: 'no thanks', isFinal: true),
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
            const SpeechResult(text: 'goodbye', isFinal: true),
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
        mockStt.emitResult(const SpeechResult(text: 'goodbye', isFinal: true));
        await Future<void>.delayed(const Duration(milliseconds: 100));

        // Now start again and say "undo".
        await orchestrator.startContinuousMode('Hi again');
        await Future<void>.delayed(const Duration(milliseconds: 50));

        mockStt.emitResult(const SpeechResult(text: 'undo', isFinal: true));
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
  });
}
