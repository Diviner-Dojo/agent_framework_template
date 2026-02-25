// ===========================================================================
// file: lib/services/local_llm_service.dart
// purpose: Abstract interface and llamadart implementation for local LLM
//          inference. Follows the same abstract-class-for-testability pattern
//          as SpeechRecognitionService (ADR-0015).
//
// The abstract class defines the contract; the real implementation wraps
// llamadart's LlamaEngine. Tests use MockLocalLlmService.
//
// Exception hierarchy:
//   LocalLlmException (base)
//   ├── ModelNotLoadedException — generate() called before loadModel()
//   └── InferenceException — model loaded but generation failed
//
// See: ADR-0017 (Local LLM Layer Architecture)
// ===========================================================================

import 'package:llamadart/llamadart.dart';

/// Base exception for local LLM operations.
///
/// All native/FFI exceptions are caught and wrapped into this type
/// by [LlamadartLlmService], ensuring the fallback chain in
/// [AgentRepository] always catches cleanly.
class LocalLlmException implements Exception {
  /// Human-readable error message.
  final String message;

  /// Optional underlying exception.
  final Object? cause;

  /// Creates a local LLM exception.
  const LocalLlmException(this.message, {this.cause});

  @override
  String toString() => 'LocalLlmException: $message';
}

/// Thrown when [generate] is called before [loadModel].
class ModelNotLoadedException extends LocalLlmException {
  /// Creates a model-not-loaded exception.
  const ModelNotLoadedException()
    : super('Model not loaded. Call loadModel() first.');
}

/// Thrown when model is loaded but inference fails.
class InferenceException extends LocalLlmException {
  /// Creates an inference exception.
  const InferenceException(super.message, {super.cause});
}

/// Abstract interface for local LLM inference.
///
/// Implementations:
/// - [LlamadartLlmService] — real llamadart wrapper (coverage:ignore)
/// - MockLocalLlmService (in tests) — deterministic mock
///
/// Streaming is intentionally NOT on this interface. It is an internal
/// implementation detail of [LlamadartLlmService]. Promote to abstract
/// only when a streaming UI consumer exists (e.g., voice mode streaming TTS).
abstract class LocalLlmService {
  /// Load a GGUF model from the given [modelPath].
  ///
  /// Wraps all native exceptions into [LocalLlmException].
  /// Returns when the model is ready for inference.
  Future<void> loadModel(String modelPath);

  /// Unload the current model, freeing RAM.
  ///
  /// Safe to call even if no model is loaded.
  Future<void> unloadModel();

  /// Whether a model is currently loaded and ready for inference.
  bool get isModelLoaded;

  /// Generate a response from the local LLM.
  ///
  /// [messages] — conversation history as role/content pairs.
  /// [systemPrompt] — optional system prompt (personality).
  ///
  /// Throws [ModelNotLoadedException] if no model is loaded.
  /// Throws [InferenceException] if generation fails.
  Future<String> generate({
    required List<Map<String, String>> messages,
    String? systemPrompt,
  });

  /// Release all resources. Called on provider dispose.
  void dispose();
}

// coverage:ignore-start
/// Real llamadart-based implementation.
///
/// Wraps [LlamaEngine] for on-device inference using the stateless chat
/// completion API. Runs inference in a background isolate internally
/// (llamadart feature).
///
/// This class is excluded from test coverage because it requires native
/// FFI bindings that are not available in the Dart test environment.
class LlamadartLlmService implements LocalLlmService {
  /// LLM inference parameters.
  final double temperature;
  final double topP;
  final int maxTokens;

  LlamaEngine? _engine;
  bool _isLoaded = false;

  /// Creates a llamadart LLM service.
  ///
  /// Parameters default to the spec values: temperature=0.7, top_p=0.9,
  /// max_tokens=150.
  LlamadartLlmService({
    this.temperature = 0.7,
    this.topP = 0.9,
    this.maxTokens = 150,
  });

  @override
  bool get isModelLoaded => _isLoaded;

  @override
  Future<void> loadModel(String modelPath) async {
    try {
      _engine = LlamaEngine(LlamaBackend());
      await _engine!.setLogLevel(LlamaLogLevel.none);
      await _engine!.loadModel(
        modelPath,
        modelParams: const ModelParams(
          gpuLayers: 0,
          preferredBackend: GpuBackend.cpu,
        ),
      );
      _isLoaded = true;
    } on LlamaException catch (e) {
      _isLoaded = false;
      _engine = null;
      throw LocalLlmException('Failed to load model', cause: e);
    } on Exception catch (e) {
      _isLoaded = false;
      _engine = null;
      throw LocalLlmException('Failed to load model', cause: e);
    }
  }

  @override
  Future<void> unloadModel() async {
    try {
      await _engine?.dispose();
      _engine = null;
      _isLoaded = false;
    } on Exception catch (e) {
      _engine = null;
      _isLoaded = false;
      throw LocalLlmException('Failed to unload model', cause: e);
    }
  }

  @override
  Future<String> generate({
    required List<Map<String, String>> messages,
    String? systemPrompt,
  }) async {
    if (!_isLoaded || _engine == null) {
      throw const ModelNotLoadedException();
    }

    try {
      final chatMessages = <LlamaChatMessage>[];

      // Add system prompt as the first message if provided.
      if (systemPrompt != null) {
        chatMessages.add(
          LlamaChatMessage.fromText(
            role: LlamaChatRole.system,
            text: systemPrompt,
          ),
        );
      }

      // Convert role/content maps to LlamaChatMessage objects.
      for (final msg in messages) {
        final role = switch (msg['role']) {
          'user' => LlamaChatRole.user,
          'assistant' => LlamaChatRole.assistant,
          'system' => LlamaChatRole.system,
          _ => LlamaChatRole.user,
        };
        chatMessages.add(
          LlamaChatMessage.fromText(role: role, text: msg['content'] ?? ''),
        );
      }

      final buffer = StringBuffer();
      await for (final chunk in _engine!.create(
        chatMessages,
        params: GenerationParams(
          temp: temperature,
          topP: topP,
          maxTokens: maxTokens,
        ),
        enableThinking: false,
      )) {
        final content = chunk.choices.first.delta.content;
        if (content != null) buffer.write(content);
      }

      return buffer.toString().trim();
    } on LlamaException catch (e) {
      throw InferenceException('Inference failed', cause: e);
    } on Exception catch (e) {
      throw InferenceException('Inference failed', cause: e);
    }
  }

  @override
  void dispose() {
    _engine?.dispose();
    _engine = null;
    _isLoaded = false;
  }
}

// coverage:ignore-end
