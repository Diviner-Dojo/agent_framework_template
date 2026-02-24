import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:dio/dio.dart';
import 'package:agentic_journal/config/environment.dart';
import 'package:agentic_journal/layers/conversation_layer.dart';
import 'package:agentic_journal/models/agent_response.dart';
import 'package:agentic_journal/repositories/agent_repository.dart';
import 'package:agentic_journal/services/claude_api_service.dart';
import 'package:agentic_journal/services/connectivity_service.dart';

/// A ConnectivityService that always reports online.
class AlwaysOnlineConnectivityService extends ConnectivityService {
  AlwaysOnlineConnectivityService()
    : super(
        connectivityStream:
            StreamController<List<ConnectivityResult>>.broadcast().stream,
      );

  @override
  bool get isOnline => true;
}

/// Mock dio adapter that always times out (to simulate Claude failure).
class _FailingDioAdapter implements HttpClientAdapter {
  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<List<int>>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    throw DioException(
      type: DioExceptionType.connectionTimeout,
      requestOptions: options,
    );
  }

  @override
  void close({bool force = false}) {}
}

/// A fake local LLM layer for testing.
class FakeLocalLlmLayer implements ConversationLayer {
  @override
  Future<AgentResponse> getGreeting({
    DateTime? lastSessionDate,
    DateTime? now,
    int sessionCount = 0,
  }) async {
    return const AgentResponse(
      content: 'Local LLM greeting',
      layer: AgentLayer.llmLocal,
    );
  }

  @override
  Future<AgentResponse?> getFollowUp({
    required String latestUserMessage,
    required List<String> conversationHistory,
    required int followUpCount,
    List<Map<String, String>>? allMessages,
  }) async {
    return const AgentResponse(
      content: 'Local LLM follow-up',
      layer: AgentLayer.llmLocal,
    );
  }

  @override
  Future<AgentResponse> generateSummary({
    required List<String> userMessages,
    List<Map<String, String>>? allMessages,
  }) async {
    return const AgentResponse(
      content: 'Local LLM summary',
      layer: AgentLayer.llmLocal,
    );
  }

  @override
  Future<AgentResponse> getResumeGreeting() async {
    return const AgentResponse(
      content: 'Local LLM resume greeting',
      layer: AgentLayer.llmLocal,
    );
  }
}

void main() {
  group('Layer selection', () {
    test('no services configured → rule-based layer', () async {
      final agent = AgentRepository();
      final response = await agent.getGreeting(
        now: DateTime(2026, 2, 23, 10, 0),
      );
      expect(response.layer, AgentLayer.ruleBasedLocal);
    });

    test('prefer-Claude ON + Claude available → Claude serves', () async {
      final env = Environment.custom(
        supabaseUrl: 'https://test.supabase.co',
        supabaseAnonKey: 'test-key',
      );
      final dio = Dio();
      // Mock successful response
      dio.httpClientAdapter = _SuccessDioAdapter();
      final claudeService = ClaudeApiService(environment: env, dio: dio);
      final connectivity = AlwaysOnlineConnectivityService();

      final agent = AgentRepository(
        claudeService: claudeService,
        connectivityService: connectivity,
      );
      agent.setPreferClaude(true);

      final response = await agent.getGreeting(
        now: DateTime(2026, 2, 23, 10, 0),
      );
      expect(response.layer, AgentLayer.llmRemote);
    });

    test(
      'prefer-Claude OFF + local LLM available → local LLM serves',
      () async {
        final agent = AgentRepository(localLlmLayer: FakeLocalLlmLayer());

        final response = await agent.getGreeting(
          now: DateTime(2026, 2, 23, 10, 0),
        );
        expect(response.layer, AgentLayer.llmLocal);
        expect(response.content, 'Local LLM greeting');
      },
    );

    test(
      'prefer-Claude OFF + no local LLM + Claude available → Claude',
      () async {
        final env = Environment.custom(
          supabaseUrl: 'https://test.supabase.co',
          supabaseAnonKey: 'test-key',
        );
        final dio = Dio();
        dio.httpClientAdapter = _SuccessDioAdapter();
        final claudeService = ClaudeApiService(environment: env, dio: dio);
        final connectivity = AlwaysOnlineConnectivityService();

        final agent = AgentRepository(
          claudeService: claudeService,
          connectivityService: connectivity,
        );
        // preferClaude defaults to false

        final response = await agent.getGreeting(
          now: DateTime(2026, 2, 23, 10, 0),
        );
        expect(response.layer, AgentLayer.llmRemote);
      },
    );

    test(
      'prefer-Claude ON + local LLM available → Claude (preference wins)',
      () async {
        final env = Environment.custom(
          supabaseUrl: 'https://test.supabase.co',
          supabaseAnonKey: 'test-key',
        );
        final dio = Dio();
        dio.httpClientAdapter = _SuccessDioAdapter();
        final claudeService = ClaudeApiService(environment: env, dio: dio);
        final connectivity = AlwaysOnlineConnectivityService();

        final agent = AgentRepository(
          claudeService: claudeService,
          connectivityService: connectivity,
          localLlmLayer: FakeLocalLlmLayer(),
        );
        agent.setPreferClaude(true);

        final response = await agent.getGreeting(
          now: DateTime(2026, 2, 23, 10, 0),
        );
        expect(response.layer, AgentLayer.llmRemote);
      },
    );
  });

  group('Session lock', () {
    test('locked layer persists for session duration', () async {
      final env = Environment.custom(
        supabaseUrl: 'https://test.supabase.co',
        supabaseAnonKey: 'test-key',
      );
      final dio = Dio();
      dio.httpClientAdapter = _SuccessDioAdapter();
      final claudeService = ClaudeApiService(environment: env, dio: dio);
      final connectivity = AlwaysOnlineConnectivityService();

      final agent = AgentRepository(
        claudeService: claudeService,
        connectivityService: connectivity,
        localLlmLayer: FakeLocalLlmLayer(),
      );

      // Lock on local LLM (default preference, local > Claude in fallback).
      agent.lockLayerForSession();

      final r1 = await agent.getGreeting(now: DateTime(2026, 2, 23, 10, 0));
      expect(r1.layer, AgentLayer.llmLocal);

      // Change preference to Claude — but lock should persist.
      agent.setPreferClaude(true);

      final r2 = await agent.getGreeting(now: DateTime(2026, 2, 23, 10, 0));
      expect(r2.layer, AgentLayer.llmLocal);
    });

    test('unlock clears session lock', () async {
      final env = Environment.custom(
        supabaseUrl: 'https://test.supabase.co',
        supabaseAnonKey: 'test-key',
      );
      final dio = Dio();
      dio.httpClientAdapter = _SuccessDioAdapter();
      final claudeService = ClaudeApiService(environment: env, dio: dio);
      final connectivity = AlwaysOnlineConnectivityService();

      final agent = AgentRepository(
        claudeService: claudeService,
        connectivityService: connectivity,
        localLlmLayer: FakeLocalLlmLayer(),
      );

      // Lock on local LLM.
      agent.lockLayerForSession();
      agent.unlockLayer();

      // After unlock, preference change takes effect.
      agent.setPreferClaude(true);

      final response = await agent.getGreeting(
        now: DateTime(2026, 2, 23, 10, 0),
      );
      expect(response.layer, AgentLayer.llmRemote);
    });
  });

  group('Fallback on error', () {
    test('Claude fails → Layer A fallback', () async {
      final env = Environment.custom(
        supabaseUrl: 'https://test.supabase.co',
        supabaseAnonKey: 'test-key',
      );
      final dio = Dio();
      dio.httpClientAdapter = _FailingDioAdapter();
      final claudeService = ClaudeApiService(environment: env, dio: dio);
      final connectivity = AlwaysOnlineConnectivityService();

      final agent = AgentRepository(
        claudeService: claudeService,
        connectivityService: connectivity,
      );

      final response = await agent.getGreeting(
        now: DateTime(2026, 2, 23, 10, 0),
      );
      expect(response.layer, AgentLayer.ruleBasedLocal);
    });

    test(
      'session locked on Claude, Claude fails → Layer A (not switch)',
      () async {
        final env = Environment.custom(
          supabaseUrl: 'https://test.supabase.co',
          supabaseAnonKey: 'test-key',
        );
        final dio = Dio();
        dio.httpClientAdapter = _FailingDioAdapter();
        final claudeService = ClaudeApiService(environment: env, dio: dio);
        final connectivity = AlwaysOnlineConnectivityService();

        final agent = AgentRepository(
          claudeService: claudeService,
          connectivityService: connectivity,
          localLlmLayer: FakeLocalLlmLayer(),
        );

        // Lock on Claude (prefer Claude).
        agent.setPreferClaude(true);
        agent.lockLayerForSession();

        // Claude fails — should fall back to rule-based, NOT local LLM.
        final response = await agent.getGreeting(
          now: DateTime(2026, 2, 23, 10, 0),
        );
        expect(response.layer, AgentLayer.ruleBasedLocal);
      },
    );
  });

  group('Journal-only mode', () {
    test('skip greeting, skip follow-up, Layer A summary', () async {
      final agent = AgentRepository();
      agent.setJournalOnlyMode(true);

      final greeting = await agent.getGreeting(
        now: DateTime(2026, 2, 23, 10, 0),
      );
      expect(greeting.content, 'Session started.');

      final followUp = await agent.getFollowUp(
        latestUserMessage: 'I feel great',
        conversationHistory: [],
        followUpCount: 0,
      );
      expect(followUp, isNull);

      final summary = await agent.generateSummary(
        userMessages: ['Had a good day.'],
      );
      expect(summary.content, 'Had a good day.');
      expect(summary.layer, AgentLayer.ruleBasedLocal);
    });
  });

  group('LocalLlmLayer fallback — all 4 methods', () {
    late AgentRepository agent;

    setUp(() {
      agent = AgentRepository(localLlmLayer: ThrowingLocalLlmLayer());
    });

    test('getGreeting falls back to rule-based on LocalLlmException', () async {
      final response = await agent.getGreeting(
        now: DateTime(2026, 2, 23, 10, 0),
      );
      expect(response.layer, AgentLayer.ruleBasedLocal);
    });

    test('getFollowUp falls back to rule-based on LocalLlmException', () async {
      final response = await agent.getFollowUp(
        latestUserMessage: 'I had a good day.',
        conversationHistory: [],
        followUpCount: 0,
        allMessages: [
          {'role': 'user', 'content': 'I had a good day.'},
        ],
      );
      // Rule-based layer still produces a follow-up.
      expect(response, isNotNull);
      expect(response!.layer, AgentLayer.ruleBasedLocal);
    });

    test(
      'generateSummary falls back to rule-based on LocalLlmException',
      () async {
        final response = await agent.generateSummary(
          userMessages: ['Had a good day.'],
          allMessages: [
            {'role': 'user', 'content': 'Had a good day.'},
          ],
        );
        expect(response.layer, AgentLayer.ruleBasedLocal);
      },
    );

    test(
      'getResumeGreeting falls back to rule-based on LocalLlmException',
      () async {
        final response = await agent.getResumeGreeting();
        expect(response.layer, AgentLayer.ruleBasedLocal);
      },
    );
  });

  group('getResumeGreeting fallback', () {
    test('getResumeGreeting exception falls back to ruleBasedLocal', () async {
      final agent = AgentRepository(localLlmLayer: ThrowingLocalLlmLayer());
      final response = await agent.getResumeGreeting();
      expect(response.layer, AgentLayer.ruleBasedLocal);
      expect(
        response.content,
        "Welcome back! Let's continue where you left off.",
      );
    });
  });

  group('Layer priority with local LLM and Claude', () {
    test(
      'prefer-Claude OFF + local LLM + Claude available → local LLM wins',
      () async {
        final env = Environment.custom(
          supabaseUrl: 'https://test.supabase.co',
          supabaseAnonKey: 'test-key',
        );
        final dio = Dio();
        dio.httpClientAdapter = _SuccessDioAdapter();
        final claudeService = ClaudeApiService(environment: env, dio: dio);
        final connectivity = AlwaysOnlineConnectivityService();

        final agent = AgentRepository(
          claudeService: claudeService,
          connectivityService: connectivity,
          localLlmLayer: FakeLocalLlmLayer(),
        );
        // preferClaude defaults to false — local LLM should win.

        final response = await agent.getGreeting(
          now: DateTime(2026, 2, 23, 10, 0),
        );
        expect(response.layer, AgentLayer.llmLocal);
        expect(response.content, 'Local LLM greeting');
      },
    );
  });

  group('Prompt isolation', () {
    test('custom prompt does not leak into rule-based fallback', () async {
      // When LocalLlmLayer fails and falls back to RuleBasedLayer,
      // the rule-based response should not contain any custom prompt text.
      final agent = AgentRepository(localLlmLayer: ThrowingLocalLlmLayer());

      final response = await agent.getGreeting(
        now: DateTime(2026, 2, 23, 10, 0),
      );
      expect(response.layer, AgentLayer.ruleBasedLocal);
      // Rule-based greetings are fixed strings — no custom prompt leakage.
      expect(response.content, isNot(contains('custom')));
    });
  });
}

/// A local LLM layer that always throws (for fallback testing).
class ThrowingLocalLlmLayer implements ConversationLayer {
  @override
  Future<AgentResponse> getGreeting({
    DateTime? lastSessionDate,
    DateTime? now,
    int sessionCount = 0,
  }) async {
    throw Exception('Local LLM failed');
  }

  @override
  Future<AgentResponse?> getFollowUp({
    required String latestUserMessage,
    required List<String> conversationHistory,
    required int followUpCount,
    List<Map<String, String>>? allMessages,
  }) async {
    throw Exception('Local LLM failed');
  }

  @override
  Future<AgentResponse> generateSummary({
    required List<String> userMessages,
    List<Map<String, String>>? allMessages,
  }) async {
    throw Exception('Local LLM failed');
  }

  @override
  Future<AgentResponse> getResumeGreeting() async {
    throw Exception('Local LLM failed');
  }
}

/// Mock adapter that returns a successful Claude response.
class _SuccessDioAdapter implements HttpClientAdapter {
  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<List<int>>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    return ResponseBody.fromString(
      '{"response": "Claude greeting"}',
      200,
      headers: {
        'content-type': ['application/json'],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}
