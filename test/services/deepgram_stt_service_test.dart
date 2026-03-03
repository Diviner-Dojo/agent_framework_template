// ===========================================================================
// file: test/services/deepgram_stt_service_test.dart
// purpose: Unit tests for DeepgramSttService event parsing logic.
//
// The full WebSocket + AudioRecorder integration cannot run in CI (requires
// network and microphone). These tests verify the SpeechResult mapping
// logic per ADR-0031 using the service's public interface and
// @visibleForTesting hooks — they exercise the production parsing code
// directly rather than duplicating it in a test double.
//
// ADR-0031 SpeechResult mapping table (under test):
//   is_final: false                                    → isFinal: false
//   is_final: true, speech_final: false                → isFinal: false
//   is_final: true, speech_final: true                 → isFinal: true
//   UtteranceEnd (after is_final: true transcript)     → isFinal: true
// ===========================================================================

import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/services/deepgram_stt_service.dart';
import 'package:agentic_journal/services/speech_recognition_service.dart';

// ---------------------------------------------------------------------------
// Test helper: build a Deepgram Results JSON string.
// ---------------------------------------------------------------------------

String _resultsEvent({
  required String transcript,
  required bool isFinal,
  required bool speechFinal,
  double confidence = 0.9,
}) {
  return json.encode({
    'type': 'Results',
    'channel_index': [0, 1],
    'duration': 1.0,
    'start': 0.0,
    'is_final': isFinal,
    'speech_final': speechFinal,
    'channel': {
      'alternatives': [
        {'transcript': transcript, 'confidence': confidence, 'words': []},
      ],
    },
  });
}

String _utteranceEndEvent() {
  return json.encode({
    'type': 'UtteranceEnd',
    'last_word_end': 2.5,
    'channel': [0],
  });
}

// ---------------------------------------------------------------------------
// Testable subclass: uses @visibleForTesting hooks to exercise production
// parsing code without a real WebSocket connection.
// ---------------------------------------------------------------------------

/// Testable subclass that drives [DeepgramSttService] parsing via production
/// code paths, bypassing the WebSocket layer.
class _TestableDeepgramSttService extends DeepgramSttService {
  final List<SpeechResult> emitted = [];

  _TestableDeepgramSttService()
    : super(proxyWsUrl: 'wss://test', authToken: 'test-token') {
    // Wire production stream → emitted list via the @visibleForTesting hook.
    initStreamForTesting().stream.listen(emitted.add);
  }

  /// Injects a message into the production _onSocketMessage handler.
  void processMessage(String message) {
    injectMessageForTesting(message);
  }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void main() {
  group('DeepgramSttService — SpeechResult mapping (ADR-0031)', () {
    late _TestableDeepgramSttService svc;

    setUp(() {
      svc = _TestableDeepgramSttService();
    });

    test('interim result (is_final: false) emits isFinal: false', () {
      svc.processMessage(
        _resultsEvent(
          transcript: 'hello',
          isFinal: false,
          speechFinal: false,
          confidence: 0.85,
        ),
      );

      expect(svc.emitted, hasLength(1));
      expect(svc.emitted.first.text, 'hello');
      expect(svc.emitted.first.isFinal, isFalse);
      expect(svc.emitted.first.confidence, closeTo(0.85, 0.001));
    });

    test(
      'is_final: true + speech_final: false (segment boundary) emits isFinal: false',
      () {
        svc.processMessage(
          _resultsEvent(
            transcript: 'hello world',
            isFinal: true,
            speechFinal: false,
          ),
        );

        expect(svc.emitted, hasLength(1));
        expect(svc.emitted.first.text, 'hello world');
        expect(svc.emitted.first.isFinal, isFalse);
      },
    );

    test(
      'is_final: true + speech_final: true (utterance end) emits isFinal: true',
      () {
        svc.processMessage(
          _resultsEvent(
            transcript: 'hello world',
            isFinal: true,
            speechFinal: true,
            confidence: 0.97,
          ),
        );

        expect(svc.emitted, hasLength(1));
        expect(svc.emitted.first.text, 'hello world');
        expect(svc.emitted.first.isFinal, isTrue);
        expect(svc.emitted.first.confidence, closeTo(0.97, 0.001));
      },
    );

    test('UtteranceEnd after is_final transcript emits isFinal: true', () {
      // First: a final-but-not-speech_final result (segment boundary).
      svc.processMessage(
        _resultsEvent(
          transcript: 'hello world',
          isFinal: true,
          speechFinal: false,
          confidence: 0.92,
        ),
      );
      // Then: UtteranceEnd fires as the fallback.
      svc.processMessage(_utteranceEndEvent());

      expect(svc.emitted, hasLength(2));
      // The UtteranceEnd re-emit is the final signal.
      expect(svc.emitted[1].text, 'hello world');
      expect(svc.emitted[1].isFinal, isTrue);
      expect(svc.emitted[1].confidence, closeTo(0.92, 0.001));
    });

    test('UtteranceEnd with no prior is_final transcript emits nothing', () {
      svc.processMessage(_utteranceEndEvent());

      expect(svc.emitted, isEmpty);
    });

    test('empty transcript is not emitted', () {
      svc.processMessage(
        _resultsEvent(transcript: '  ', isFinal: true, speechFinal: true),
      );

      expect(svc.emitted, isEmpty);
    });

    test('non-JSON frame is silently ignored', () {
      svc.processMessage('not valid json {{{');

      expect(svc.emitted, isEmpty);
    });

    test('unknown event type (Metadata, SpeechStarted) is ignored', () {
      svc.processMessage(
        json.encode({'type': 'Metadata', 'transaction_key': 'abc'}),
      );
      svc.processMessage(
        json.encode({'type': 'SpeechStarted', 'timestamp': 0.0}),
      );

      expect(svc.emitted, isEmpty);
    });

    test('multiple sequential Results → UtteranceEnd sequence works', () {
      // Three interim results.
      for (var i = 0; i < 3; i++) {
        svc.processMessage(
          _resultsEvent(
            transcript: 'word $i',
            isFinal: false,
            speechFinal: false,
          ),
        );
      }
      // One is_final (segment boundary, not yet speech_final).
      svc.processMessage(
        _resultsEvent(
          transcript: 'final segment',
          isFinal: true,
          speechFinal: false,
          confidence: 0.88,
        ),
      );
      // UtteranceEnd fires — should re-emit last is_final transcript.
      svc.processMessage(_utteranceEndEvent());

      final results = svc.emitted;
      expect(results, hasLength(5));
      expect(results.last.text, 'final segment');
      expect(results.last.isFinal, isTrue);
    });

    test(
      'UtteranceEnd clears the last transcript (second UtteranceEnd is noop)',
      () {
        svc.processMessage(
          _resultsEvent(transcript: 'first', isFinal: true, speechFinal: false),
        );
        svc.processMessage(_utteranceEndEvent()); // Should emit.
        svc.processMessage(_utteranceEndEvent()); // Should NOT emit (cleared).

        expect(
          svc.emitted.where((r) => r.isFinal).length,
          equals(1),
          reason: 'Only one final emit expected from two UtteranceEnd events',
        );
      },
    );
  });

  group('DeepgramSttService — lifecycle', () {
    test('isInitialized is false before initialize()', () {
      final svc = DeepgramSttService(
        proxyWsUrl: 'wss://test',
        authToken: 'test-token',
      );
      expect(svc.isInitialized, isFalse);
    });

    test('isInitialized is true after initialize()', () async {
      final svc = DeepgramSttService(
        proxyWsUrl: 'wss://test',
        authToken: 'test-token',
      );
      await svc.initialize(modelPath: '');
      expect(svc.isInitialized, isTrue);
    });

    test('isListening is false initially', () {
      final svc = DeepgramSttService(
        proxyWsUrl: 'wss://test',
        authToken: 'test-token',
      );
      expect(svc.isListening, isFalse);
    });

    test('startListening throws StateError if not initialized', () async {
      final svc = DeepgramSttService(
        proxyWsUrl: 'wss://test',
        authToken: 'test-token',
      );
      expect(() => svc.startListening(), throwsA(isA<StateError>()));
    });

    test('startListening throws StateError if already listening', () async {
      // Regression: second startListening() call must throw immediately,
      // not hang waiting for a network connection.
      final svc = DeepgramSttService(
        proxyWsUrl: 'wss://test',
        authToken: 'test-token',
      );
      await svc.initialize(modelPath: '');
      svc.startListening(); // First call: sets _isListening = true synchronously.
      expect(
        () => svc.startListening(), // Second call: must throw immediately.
        throwsA(isA<StateError>()),
      );
      // No cleanup needed: _connectAndCapture() will fail (no server) and the
      // error is swallowed by the catchError guard in startListening().
    });
  });
}
