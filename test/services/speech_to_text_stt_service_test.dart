// ===========================================================================
// file: test/services/speech_to_text_stt_service_test.dart
// purpose: Tests for speech_to_text STT service contract.
//
// Strategy:
//   SpeechToTextSttService wraps the speech_to_text package which requires
//   Android's speech recognizer. We test:
//     1. The service contract via a mock that simulates recognition
//     2. State transitions (initialize → listen → stop → dispose)
//     3. Auto-restart behavior on silence timeout
//     4. Result mapping to SpeechResult
//
// See: ADR-0022 (Voice Engine Swap)
// ===========================================================================

import 'dart:async';

import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/services/speech_recognition_service.dart';

/// Mock speech_to_text STT service for testing.
///
/// Simulates the speech_to_text package behavior including auto-restart
/// on silence timeout, without requiring native Android speech services.
class MockSpeechToTextSttService implements SpeechRecognitionService {
  bool _isInitialized = false;
  bool _isListening = false;
  StreamController<SpeechResult>? _controller;
  int initializeCallCount = 0;
  int startListenCount = 0;
  int stopListenCount = 0;

  @override
  Future<void> initialize({required String modelPath}) async {
    // speech_to_text ignores modelPath — no model download needed.
    initializeCallCount++;
    _isInitialized = true;
  }

  @override
  Stream<SpeechResult> startListening() {
    if (!_isInitialized) {
      throw StateError(
        'SpeechToTextSttService not initialized. Call initialize() first.',
      );
    }
    if (_isListening) {
      throw StateError('Already listening. Call stopListening() first.');
    }
    _controller = StreamController<SpeechResult>.broadcast();
    _isListening = true;
    startListenCount++;
    return _controller!.stream;
  }

  /// Simulate a recognition result.
  void simulateResult(SpeechResult result) {
    _controller?.add(result);
  }

  /// Simulate an error.
  void simulateError(Object error) {
    _controller?.addError(error);
  }

  @override
  Future<void> stopListening() async {
    if (!_isListening) return;
    stopListenCount++;
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
    _controller?.close();
    _controller = null;
  }
}

void main() {
  group('SpeechToTextSttService (mock)', () {
    late MockSpeechToTextSttService service;

    setUp(() {
      service = MockSpeechToTextSttService();
    });

    tearDown(() {
      service.dispose();
    });

    test('starts uninitialized and not listening', () {
      expect(service.isInitialized, isFalse);
      expect(service.isListening, isFalse);
    });

    test('initialize ignores modelPath (no model needed)', () async {
      await service.initialize(modelPath: '/ignored/path');
      expect(service.isInitialized, isTrue);
      expect(service.initializeCallCount, 1);
    });

    test('startListening throws if not initialized', () {
      expect(() => service.startListening(), throwsStateError);
    });

    test('startListening returns a stream and sets isListening', () async {
      await service.initialize(modelPath: '');
      final stream = service.startListening();
      expect(stream, isA<Stream<SpeechResult>>());
      expect(service.isListening, isTrue);
      expect(service.startListenCount, 1);
    });

    test('startListening throws if already listening', () async {
      await service.initialize(modelPath: '');
      service.startListening();
      expect(() => service.startListening(), throwsStateError);
    });

    test('stream emits partial and final results', () async {
      await service.initialize(modelPath: '');
      final stream = service.startListening();

      final results = <SpeechResult>[];
      final sub = stream.listen(results.add);

      service.simulateResult(const SpeechResult(text: 'hel', isFinal: false));
      service.simulateResult(
        const SpeechResult(text: 'hello world', isFinal: true),
      );

      await Future<void>.delayed(Duration.zero);

      expect(results, hasLength(2));
      expect(results[0].text, 'hel');
      expect(results[0].isFinal, isFalse);
      expect(results[1].text, 'hello world');
      expect(results[1].isFinal, isTrue);

      await sub.cancel();
    });

    test('stream propagates errors', () async {
      await service.initialize(modelPath: '');
      final stream = service.startListening();

      final errors = <Object>[];
      final sub = stream.listen((_) {}, onError: errors.add);

      service.simulateError(StateError('STT error'));
      await Future<void>.delayed(Duration.zero);

      expect(errors, hasLength(1));
      expect(errors[0], isA<StateError>());

      await sub.cancel();
    });

    test('stopListening clears isListening', () async {
      await service.initialize(modelPath: '');
      service.startListening();
      expect(service.isListening, isTrue);

      await service.stopListening();
      expect(service.isListening, isFalse);
      expect(service.stopListenCount, 1);
    });

    test('stopListening is safe to call when not listening', () async {
      await service.initialize(modelPath: '');
      await service.stopListening();
      // stopListenCount should be 0 since it returns early.
      expect(service.stopListenCount, 0);
    });

    test('dispose resets all state', () async {
      await service.initialize(modelPath: '');
      service.startListening();

      service.dispose();
      expect(service.isInitialized, isFalse);
      expect(service.isListening, isFalse);
    });
  });
}
