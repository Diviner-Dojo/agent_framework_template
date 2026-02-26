// ===========================================================================
// file: test/services/speech_recognition_service_test.dart
// purpose: Tests for SpeechResult model and SpeechRecognitionService contract.
//
// Strategy:
//   The concrete SherpaOnnxSpeechRecognitionService cannot be tested in CI
//   (requires native sherpa_onnx libraries and a physical device). Instead,
//   we test:
//     1. SpeechResult model (equality, toString)
//     2. Service contract via a mock implementation
//     3. State transitions (initialize → listen → stop → dispose)
// ===========================================================================

import 'dart:async';

import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/services/audio_file_service.dart';
import 'package:agentic_journal/services/speech_recognition_service.dart';

/// Mock implementation of SpeechRecognitionService for testing.
///
/// Simulates the behavioral contract of the real sherpa_onnx service:
/// - [pendingText] simulates buffered audio that hasn't been emitted yet
/// - [stopListening] emits any pending text as a final result (matching
///   the silence-padding flush behavior added in E1)
class MockSpeechRecognitionService implements SpeechRecognitionService {
  bool _isInitialized = false;
  bool _isListening = false;
  StreamController<SpeechResult>? _controller;
  String? lastModelPath;

  /// Simulates buffered text in the recognizer that hasn't been emitted.
  /// When [stopListening] is called, this is emitted as a final result,
  /// mirroring the silence-padding flush in the real implementation.
  String? pendingText;

  @override
  Future<void> initialize({required String modelPath}) async {
    lastModelPath = modelPath;
    _isInitialized = true;
  }

  @override
  Stream<SpeechResult> startListening({AudioFileService? audioFileService}) {
    if (!_isInitialized) {
      throw StateError('Not initialized');
    }
    if (_isListening) {
      throw StateError('Already listening');
    }
    _controller = StreamController<SpeechResult>.broadcast();
    _isListening = true;
    return _controller!.stream;
  }

  /// Simulate a recognition result (for testing).
  void simulateResult(SpeechResult result) {
    _controller?.add(result);
  }

  /// Simulate an error (for testing).
  void simulateError(Object error) {
    _controller?.addError(error);
  }

  @override
  Future<void> stopListening() async {
    // Flush any pending text as a final result (mirrors silence-padding
    // behavior: the real service appends 0.5s silence, decodes remaining
    // frames, and emits the final text before closing).
    if (pendingText != null && pendingText!.isNotEmpty && _controller != null) {
      _controller!.add(SpeechResult(text: pendingText!, isFinal: true));
      pendingText = null;
    }
    _isListening = false;
    await _controller?.close();
    _controller = null;
  }

  @override
  bool get isListening => _isListening;

  @override
  bool get isInitialized => _isInitialized;

  @override
  void dispose() {
    _isListening = false;
    _isInitialized = false;
    pendingText = null;
    _controller?.close();
    _controller = null;
  }
}

void main() {
  group('SpeechResult', () {
    test('creates with required fields', () {
      const result = SpeechResult(text: 'hello', isFinal: false);
      expect(result.text, 'hello');
      expect(result.isFinal, isFalse);
    });

    test('equality works correctly', () {
      const a = SpeechResult(text: 'hello', isFinal: true);
      const b = SpeechResult(text: 'hello', isFinal: true);
      const c = SpeechResult(text: 'hello', isFinal: false);
      const d = SpeechResult(text: 'world', isFinal: true);

      expect(a, equals(b));
      expect(a, isNot(equals(c)));
      expect(a, isNot(equals(d)));
    });

    test('hashCode is consistent with equality', () {
      const a = SpeechResult(text: 'hello', isFinal: true);
      const b = SpeechResult(text: 'hello', isFinal: true);
      expect(a.hashCode, equals(b.hashCode));
    });

    test('toString includes fields', () {
      const result = SpeechResult(text: 'test', isFinal: true);
      expect(result.toString(), contains('test'));
      expect(result.toString(), contains('true'));
    });
  });

  group('SpeechRecognitionService (mock)', () {
    late MockSpeechRecognitionService service;

    setUp(() {
      service = MockSpeechRecognitionService();
    });

    tearDown(() {
      service.dispose();
    });

    test('starts uninitialized and not listening', () {
      expect(service.isInitialized, isFalse);
      expect(service.isListening, isFalse);
    });

    test('initialize sets isInitialized and records model path', () async {
      await service.initialize(modelPath: '/test/model');
      expect(service.isInitialized, isTrue);
      expect(service.lastModelPath, '/test/model');
    });

    test('startListening throws if not initialized', () {
      expect(() => service.startListening(), throwsStateError);
    });

    test('startListening returns a stream and sets isListening', () async {
      await service.initialize(modelPath: '/test');
      final stream = service.startListening();
      expect(stream, isA<Stream<SpeechResult>>());
      expect(service.isListening, isTrue);
    });

    test('startListening throws if already listening', () async {
      await service.initialize(modelPath: '/test');
      service.startListening();
      expect(() => service.startListening(), throwsStateError);
    });

    test('stream emits partial and final results', () async {
      await service.initialize(modelPath: '/test');
      final stream = service.startListening();

      final results = <SpeechResult>[];
      final sub = stream.listen(results.add);

      service.simulateResult(const SpeechResult(text: 'hel', isFinal: false));
      service.simulateResult(const SpeechResult(text: 'hello', isFinal: true));

      // Allow stream events to propagate.
      await Future<void>.delayed(Duration.zero);

      expect(results, hasLength(2));
      expect(results[0].text, 'hel');
      expect(results[0].isFinal, isFalse);
      expect(results[1].text, 'hello');
      expect(results[1].isFinal, isTrue);

      await sub.cancel();
    });

    test('stream propagates errors', () async {
      await service.initialize(modelPath: '/test');
      final stream = service.startListening();

      final errors = <Object>[];
      final sub = stream.listen((_) {}, onError: errors.add);

      service.simulateError(StateError('mic failed'));
      await Future<void>.delayed(Duration.zero);

      expect(errors, hasLength(1));
      expect(errors[0], isA<StateError>());

      await sub.cancel();
    });

    test('stopListening clears isListening', () async {
      await service.initialize(modelPath: '/test');
      service.startListening();
      expect(service.isListening, isTrue);

      await service.stopListening();
      expect(service.isListening, isFalse);
    });

    test('dispose resets all state', () async {
      await service.initialize(modelPath: '/test');
      service.startListening();

      service.dispose();
      expect(service.isInitialized, isFalse);
      expect(service.isListening, isFalse);
    });

    test('stopListening is safe to call when not listening', () async {
      await service.initialize(modelPath: '/test');
      // Should not throw.
      await service.stopListening();
    });
  });

  group('Silence padding flush (E1 behavioral contract)', () {
    late MockSpeechRecognitionService service;

    setUp(() {
      service = MockSpeechRecognitionService();
    });

    tearDown(() {
      service.dispose();
    });

    test('stopListening emits pending text as final result', () async {
      await service.initialize(modelPath: '/test');
      final stream = service.startListening();

      final results = <SpeechResult>[];
      final sub = stream.listen(results.add);

      // Simulate partial recognition in progress.
      service.simulateResult(
        const SpeechResult(text: 'today I fe', isFinal: false),
      );
      await Future<void>.delayed(Duration.zero);

      // Set pending text (simulates buffered audio in recognizer).
      service.pendingText = 'today I feel grateful';

      // stopListening should flush the pending text as final.
      await service.stopListening();
      await Future<void>.delayed(Duration.zero);

      expect(results, hasLength(2));
      expect(results[0].text, 'today I fe');
      expect(results[0].isFinal, isFalse);
      expect(results[1].text, 'today I feel grateful');
      expect(results[1].isFinal, isTrue);

      await sub.cancel();
    });

    test('stopListening with no pending text emits nothing extra', () async {
      await service.initialize(modelPath: '/test');
      final stream = service.startListening();

      final results = <SpeechResult>[];
      final sub = stream.listen(results.add);

      service.simulateResult(const SpeechResult(text: 'done', isFinal: true));
      await Future<void>.delayed(Duration.zero);

      // No pending text — stop should not add extra results.
      await service.stopListening();
      await Future<void>.delayed(Duration.zero);

      expect(results, hasLength(1));
      expect(results[0].text, 'done');
      expect(results[0].isFinal, isTrue);

      await sub.cancel();
    });

    test('stopListening with empty pending text emits nothing', () async {
      await service.initialize(modelPath: '/test');
      final stream = service.startListening();

      final results = <SpeechResult>[];
      final sub = stream.listen(results.add);

      service.pendingText = '';
      await service.stopListening();
      await Future<void>.delayed(Duration.zero);

      expect(results, isEmpty);

      await sub.cancel();
    });
  });
}
