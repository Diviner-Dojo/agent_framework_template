// ===========================================================================
// file: test/services/local_llm_service_test.dart
// purpose: Tests for LocalLlmService exception hierarchy and abstract contract.
//
// The real LlamadartLlmService is excluded from test coverage (requires
// native FFI). These tests verify the exception types, mock behavior,
// and abstract contract enforcement.
//
// See: SPEC-20260224-014525 §R1, §R8
// ===========================================================================

import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/services/local_llm_service.dart';

/// Mock implementation for testing the abstract contract.
class TestLlmService implements LocalLlmService {
  bool _isLoaded = false;

  @override
  bool get isModelLoaded => _isLoaded;

  @override
  Future<void> loadModel(String modelPath) async {
    _isLoaded = true;
  }

  @override
  Future<void> unloadModel() async {
    _isLoaded = false;
  }

  @override
  Future<String> generate({
    required List<Map<String, String>> messages,
    String? systemPrompt,
  }) async {
    if (!_isLoaded) throw const ModelNotLoadedException();
    return 'test response';
  }

  @override
  void dispose() {
    _isLoaded = false;
  }
}

void main() {
  group('Exception hierarchy', () {
    test('LocalLlmException has correct message', () {
      const ex = LocalLlmException('test error');
      expect(ex.message, 'test error');
      expect(ex.cause, isNull);
      expect(ex.toString(), 'LocalLlmException: test error');
    });

    test('LocalLlmException with cause', () {
      const cause = FormatException('bad format');
      const ex = LocalLlmException('test error', cause: cause);
      expect(ex.cause, isA<FormatException>());
    });

    test('ModelNotLoadedException has default message', () {
      const ex = ModelNotLoadedException();
      expect(ex.message, 'Model not loaded. Call loadModel() first.');
      expect(ex, isA<LocalLlmException>());
    });

    test('InferenceException has custom message', () {
      const ex = InferenceException('generation failed');
      expect(ex.message, 'generation failed');
      expect(ex, isA<LocalLlmException>());
    });

    test('InferenceException with cause', () {
      final cause = StateError('bad state');
      final ex = InferenceException('failed', cause: cause);
      expect(ex.cause, isA<StateError>());
    });

    test('exceptions are catchable as Exception', () {
      expect(
        () => throw const LocalLlmException('test'),
        throwsA(isA<Exception>()),
      );
    });
  });

  group('TestLlmService (abstract contract)', () {
    late TestLlmService service;

    setUp(() {
      service = TestLlmService();
    });

    test('isModelLoaded is false initially', () {
      expect(service.isModelLoaded, isFalse);
    });

    test('loadModel sets isModelLoaded to true', () async {
      await service.loadModel('/path/to/model.gguf');
      expect(service.isModelLoaded, isTrue);
    });

    test('unloadModel sets isModelLoaded to false', () async {
      await service.loadModel('/path');
      await service.unloadModel();
      expect(service.isModelLoaded, isFalse);
    });

    test('generate throws ModelNotLoadedException when not loaded', () {
      expect(
        () => service.generate(
          messages: [
            {'role': 'user', 'content': 'Hi'},
          ],
        ),
        throwsA(isA<ModelNotLoadedException>()),
      );
    });

    test('generate returns response when loaded', () async {
      await service.loadModel('/path');
      final response = await service.generate(
        messages: [
          {'role': 'user', 'content': 'Hi'},
        ],
      );
      expect(response, 'test response');
    });

    test('dispose sets isModelLoaded to false', () async {
      await service.loadModel('/path');
      service.dispose();
      expect(service.isModelLoaded, isFalse);
    });

    test('unloadModel is safe when no model loaded', () async {
      await service.unloadModel();
      expect(service.isModelLoaded, isFalse);
    });
  });
}
