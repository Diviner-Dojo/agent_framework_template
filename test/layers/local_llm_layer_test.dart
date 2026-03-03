// ===========================================================================
// file: test/layers/local_llm_layer_test.dart
// purpose: Tests for LocalLlmLayer conversation layer.
//
// Uses MockLocalLlmService (deterministic mock) to verify that the layer
// correctly delegates to the LLM service, passes system prompts, and
// returns AgentLayer.llmLocal on all methods.
//
// Contains Phase 2A ADHD gap-shaming removal regression tests (lines 118-154).
// See: memory/bugs/regression-ledger.md — Phase 2A gap-shaming removal.
//
// See: SPEC-20260224-014525 §R2, §R8
// ===========================================================================

@Tags(['regression'])
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/layers/local_llm_layer.dart';
import 'package:agentic_journal/models/agent_response.dart';
import 'package:agentic_journal/services/local_llm_service.dart';

/// Mock implementation of LocalLlmService for deterministic testing.
///
/// Returns configurable responses via [nextResponse]. Tracks calls
/// in [lastMessages] and [lastSystemPrompt] for assertion.
class MockLocalLlmService implements LocalLlmService {
  String nextResponse = 'mock response';
  List<Map<String, String>>? lastMessages;
  String? lastSystemPrompt;
  bool _isLoaded = true;

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
    lastMessages = messages;
    lastSystemPrompt = systemPrompt;
    return nextResponse;
  }

  @override
  void dispose() {
    _isLoaded = false;
  }
}

/// Mock that always throws LocalLlmException on generate().
class ThrowingLocalLlmService implements LocalLlmService {
  @override
  bool get isModelLoaded => true;

  @override
  Future<void> loadModel(String modelPath) async {}

  @override
  Future<void> unloadModel() async {}

  @override
  Future<String> generate({
    required List<Map<String, String>> messages,
    String? systemPrompt,
  }) async {
    throw const InferenceException('Test inference failure');
  }

  @override
  void dispose() {}
}

void main() {
  late MockLocalLlmService mockService;
  late LocalLlmLayer layer;
  const testSystemPrompt = 'You are a test assistant.';

  setUp(() {
    mockService = MockLocalLlmService();
    layer = LocalLlmLayer(
      llmService: mockService,
      systemPrompt: testSystemPrompt,
    );
  });

  group('getGreeting', () {
    test('returns greeting with llmLocal layer', () async {
      mockService.nextResponse = 'Good morning!';
      final response = await layer.getGreeting(
        now: DateTime(2026, 2, 23, 10, 0),
      );
      expect(response.content, 'Good morning!');
      expect(response.layer, AgentLayer.llmLocal);
    });

    test('passes system prompt to service', () async {
      await layer.getGreeting(now: DateTime(2026, 2, 23, 10, 0));
      expect(mockService.lastSystemPrompt, testSystemPrompt);
    });

    test('includes time-of-day context in prompt', () async {
      await layer.getGreeting(now: DateTime(2026, 2, 23, 10, 0));
      final userMsg = mockService.lastMessages!.first['content']!;
      expect(userMsg, contains('morning'));
    });

    // Phase 2A — ADHD UX: gap duration is NEVER injected into context hints.
    // These tests were previously "includes days-since-last when >= 2 days"
    // and "includes days-since-last when exactly 2 days (boundary)" —
    // both reversed after Phase 2A removal. See gap_shaming_removal_test.dart.
    test(
      'does not include days-since-last after 3-day gap (Phase 2A)',
      () async {
        await layer.getGreeting(
          now: DateTime(2026, 2, 23, 10, 0),
          lastSessionDate: DateTime(2026, 2, 20, 10, 0),
        );
        final userMsg = mockService.lastMessages!.first['content']!;
        expect(userMsg, isNot(contains('3 days')));
        expect(userMsg, isNot(contains('days since')));
      },
    );

    test(
      'does not include days-since-last after 2-day gap (Phase 2A)',
      () async {
        await layer.getGreeting(
          now: DateTime(2026, 2, 23, 10, 0),
          lastSessionDate: DateTime(2026, 2, 21, 10, 0),
        );
        final userMsg = mockService.lastMessages!.first['content']!;
        expect(userMsg, isNot(contains('2 days')));
        expect(userMsg, isNot(contains('days since')));
      },
    );

    test(
      'does not include days-since-last for any gap length (Phase 2A)',
      () async {
        await layer.getGreeting(
          now: DateTime(2026, 2, 23, 10, 0),
          lastSessionDate: DateTime(2026, 2, 22, 10, 0),
        );
        final userMsg = mockService.lastMessages!.first['content']!;
        expect(userMsg, isNot(contains('days since')));
      },
    );

    test('includes first-session context when sessionCount=0', () async {
      await layer.getGreeting(
        now: DateTime(2026, 2, 23, 10, 0),
        sessionCount: 0,
      );
      final userMsg = mockService.lastMessages!.first['content']!;
      expect(userMsg, contains('first session'));
    });

    test('throws LocalLlmException on service failure', () async {
      final throwingLayer = LocalLlmLayer(
        llmService: ThrowingLocalLlmService(),
        systemPrompt: testSystemPrompt,
      );
      await expectLater(
        throwingLayer.getGreeting(now: DateTime(2026, 2, 23, 10, 0)),
        throwsA(isA<LocalLlmException>()),
      );
    });

    test('uses DateTime.now() when now is not provided', () async {
      mockService.nextResponse = 'Hello!';
      final response = await layer.getGreeting();
      expect(response.content, 'Hello!');
      expect(response.layer, AgentLayer.llmLocal);
    });
  });

  group('getFollowUp', () {
    test('returns follow-up with llmLocal layer', () async {
      mockService.nextResponse = 'Tell me more about that.';
      final response = await layer.getFollowUp(
        latestUserMessage: 'I had a good day.',
        conversationHistory: [],
        followUpCount: 0,
        allMessages: [
          {'role': 'assistant', 'content': 'Hi!'},
          {'role': 'user', 'content': 'I had a good day.'},
        ],
      );
      expect(response, isNotNull);
      expect(response!.content, 'Tell me more about that.');
      expect(response.layer, AgentLayer.llmLocal);
    });

    test('passes allMessages to service', () async {
      final messages = [
        {'role': 'assistant', 'content': 'Hi!'},
        {'role': 'user', 'content': 'Hello.'},
      ];
      await layer.getFollowUp(
        latestUserMessage: 'Hello.',
        conversationHistory: [],
        followUpCount: 0,
        allMessages: messages,
      );
      expect(mockService.lastMessages, messages);
    });

    test('passes system prompt to service', () async {
      await layer.getFollowUp(
        latestUserMessage: 'Hi',
        conversationHistory: [],
        followUpCount: 0,
        allMessages: [
          {'role': 'user', 'content': 'Hi'},
        ],
      );
      expect(mockService.lastSystemPrompt, testSystemPrompt);
    });

    test('returns null when allMessages is null', () async {
      final response = await layer.getFollowUp(
        latestUserMessage: 'Hi',
        conversationHistory: [],
        followUpCount: 0,
      );
      expect(response, isNull);
    });

    test('returns null when allMessages is empty', () async {
      final response = await layer.getFollowUp(
        latestUserMessage: 'Hi',
        conversationHistory: [],
        followUpCount: 0,
        allMessages: [],
      );
      expect(response, isNull);
    });

    test('throws LocalLlmException on service failure', () async {
      final throwingLayer = LocalLlmLayer(
        llmService: ThrowingLocalLlmService(),
        systemPrompt: testSystemPrompt,
      );
      await expectLater(
        throwingLayer.getFollowUp(
          latestUserMessage: 'Hi',
          conversationHistory: [],
          followUpCount: 0,
          allMessages: [
            {'role': 'user', 'content': 'Hi'},
          ],
        ),
        throwsA(isA<LocalLlmException>()),
      );
    });
  });

  group('generateSummary', () {
    test('returns summary with llmLocal layer', () async {
      mockService.nextResponse = 'User had a productive day.';
      final response = await layer.generateSummary(
        userMessages: ['I had a good day.'],
        allMessages: [
          {'role': 'assistant', 'content': 'Hi!'},
          {'role': 'user', 'content': 'I had a good day.'},
        ],
      );
      expect(response.content, 'User had a productive day.');
      expect(response.layer, AgentLayer.llmLocal);
    });

    test('appends summary prompt to messages', () async {
      await layer.generateSummary(
        userMessages: ['I had a good day.'],
        allMessages: [
          {'role': 'user', 'content': 'I had a good day.'},
        ],
      );
      final lastMsg = mockService.lastMessages!.last;
      expect(lastMsg['role'], 'user');
      expect(lastMsg['content'], contains('summary'));
    });

    test('falls back to concatenation when allMessages is null', () async {
      final response = await layer.generateSummary(
        userMessages: ['One.', 'Two.'],
      );
      expect(response.content, 'One.. Two.');
      expect(response.layer, AgentLayer.llmLocal);
    });

    test('falls back to concatenation when allMessages is empty', () async {
      final response = await layer.generateSummary(
        userMessages: ['One.'],
        allMessages: [],
      );
      expect(response.content, 'One.');
      expect(response.layer, AgentLayer.llmLocal);
    });

    test('throws LocalLlmException on service failure', () async {
      final throwingLayer = LocalLlmLayer(
        llmService: ThrowingLocalLlmService(),
        systemPrompt: testSystemPrompt,
      );
      await expectLater(
        throwingLayer.generateSummary(
          userMessages: ['Hi'],
          allMessages: [
            {'role': 'user', 'content': 'Hi'},
          ],
        ),
        throwsA(isA<LocalLlmException>()),
      );
    });
  });

  group('getResumeGreeting', () {
    test('returns resume greeting with llmLocal layer', () async {
      mockService.nextResponse = 'Welcome back!';
      final response = await layer.getResumeGreeting();
      expect(response.content, 'Welcome back!');
      expect(response.layer, AgentLayer.llmLocal);
    });

    test('passes system prompt to service', () async {
      await layer.getResumeGreeting();
      expect(mockService.lastSystemPrompt, testSystemPrompt);
    });

    test('throws LocalLlmException on service failure', () async {
      final throwingLayer = LocalLlmLayer(
        llmService: ThrowingLocalLlmService(),
        systemPrompt: testSystemPrompt,
      );
      await expectLater(
        throwingLayer.getResumeGreeting(),
        throwsA(isA<LocalLlmException>()),
      );
    });
  });

  group('System prompt immutability', () {
    test('captures system prompt at construction', () async {
      const prompt = 'Original prompt.';
      final service = MockLocalLlmService();
      final testLayer = LocalLlmLayer(
        llmService: service,
        systemPrompt: prompt,
      );

      await testLayer.getGreeting(now: DateTime(2026, 2, 23, 10, 0));
      expect(service.lastSystemPrompt, prompt);
    });

    test('with custom prompt in effective system prompt', () async {
      const basePrompt = 'Base prompt.';
      const customPrompt = 'Be extra gentle.';
      const effectivePrompt = '$basePrompt\n\n$customPrompt';
      final service = MockLocalLlmService();
      final testLayer = LocalLlmLayer(
        llmService: service,
        systemPrompt: effectivePrompt,
      );

      await testLayer.getGreeting(now: DateTime(2026, 2, 23, 10, 0));
      expect(service.lastSystemPrompt, effectivePrompt);
      expect(service.lastSystemPrompt, contains('Be extra gentle.'));
    });
  });
}
