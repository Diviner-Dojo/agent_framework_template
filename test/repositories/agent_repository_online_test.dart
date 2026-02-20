import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:dio/dio.dart';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:agentic_journal/config/environment.dart';
import 'package:agentic_journal/models/agent_response.dart';
import 'package:agentic_journal/repositories/agent_repository.dart';
import 'package:agentic_journal/services/claude_api_service.dart';
import 'package:agentic_journal/services/connectivity_service.dart';

/// Mock dio adapter for controlling API responses in tests.
class MockDioAdapter implements HttpClientAdapter {
  late ResponseBody Function(RequestOptions) _handler;

  void setResponse(int statusCode, String jsonBody) {
    _handler = (options) {
      return ResponseBody.fromString(
        jsonBody,
        statusCode,
        headers: {
          'content-type': ['application/json'],
        },
      );
    };
  }

  void setError(DioExceptionType type) {
    _handler = (options) {
      throw DioException(type: type, requestOptions: options);
    };
  }

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<List<int>>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    return _handler(options);
  }

  @override
  void close({bool force = false}) {}
}

/// A ConnectivityService that always reports online.
/// Used to force AgentRepository into the Layer B (LLM) code path.
class AlwaysOnlineConnectivityService extends ConnectivityService {
  AlwaysOnlineConnectivityService()
    : super(
        connectivityStream:
            StreamController<List<ConnectivityResult>>.broadcast().stream,
      );

  @override
  bool get isOnline => true;
}

void main() {
  group('AgentRepository Layer A (offline)', () {
    late AgentRepository agent;

    setUp(() {
      // No services → Layer A only (same as Phase 1).
      agent = AgentRepository();
    });

    test('getGreeting returns ruleBasedLocal layer', () async {
      final response = await agent.getGreeting(
        now: DateTime(2026, 2, 19, 10, 0),
      );
      expect(response.layer, AgentLayer.ruleBasedLocal);
      expect(response.content, isNotEmpty);
    });

    test('getFollowUp returns ruleBasedLocal layer', () async {
      final response = await agent.getFollowUp(
        latestUserMessage: 'I feel stressed',
        conversationHistory: [],
        followUpCount: 0,
      );
      expect(response, isNotNull);
      expect(response!.layer, AgentLayer.ruleBasedLocal);
    });

    test('generateSummary returns ruleBasedLocal layer', () async {
      final response = await agent.generateSummary(
        userMessages: ['Had a great day.'],
      );
      expect(response.layer, AgentLayer.ruleBasedLocal);
      expect(response.content, 'Had a great day.');
    });

    test('metadata is null for Layer A responses', () async {
      final response = await agent.generateSummary(
        userMessages: ['Test message.'],
      );
      expect(response.metadata, isNull);
    });
  });

  group('AgentRepository with unconfigured environment', () {
    test('falls back to Layer A when environment is not configured', () async {
      final unconfiguredEnv = Environment.custom(
        supabaseUrl: '',
        supabaseAnonKey: '',
      );
      final dio = Dio();
      final claudeService = ClaudeApiService(
        environment: unconfiguredEnv,
        dio: dio,
      );
      // ConnectivityService not initialized → isOnline=false
      final connectivityService = ConnectivityService(
        connectivityStream:
            StreamController<List<ConnectivityResult>>.broadcast().stream,
      );

      final agent = AgentRepository(
        claudeService: claudeService,
        connectivityService: connectivityService,
      );

      final response = await agent.getGreeting(
        now: DateTime(2026, 2, 19, 14, 0),
      );

      // Should use Layer A because environment isn't configured.
      expect(response.layer, AgentLayer.ruleBasedLocal);
      expect(response.content, "How's your afternoon going?");
    });
  });

  group('AgentRepository with connectivity offline', () {
    test('uses Layer A when connectivity reports offline', () async {
      final env = Environment.custom(
        supabaseUrl: 'https://test.supabase.co',
        supabaseAnonKey: 'test-key',
      );
      final dio = Dio();
      final claudeService = ClaudeApiService(environment: env, dio: dio);

      // ConnectivityService not initialized → isOnline=false.
      final connectivityService = ConnectivityService(
        connectivityStream:
            StreamController<List<ConnectivityResult>>.broadcast().stream,
      );

      final agent = AgentRepository(
        claudeService: claudeService,
        connectivityService: connectivityService,
      );

      final response = await agent.getGreeting(
        now: DateTime(2026, 2, 19, 19, 0),
      );

      // Should use Layer A because connectivity is offline.
      expect(response.layer, AgentLayer.ruleBasedLocal);
      expect(response.content, 'How was your day?');
    });
  });

  group('AgentRepository Layer B fallback to Layer A on API error', () {
    late AgentRepository agent;
    late MockDioAdapter adapter;

    setUp(() {
      final env = Environment.custom(
        supabaseUrl: 'https://test.supabase.co',
        supabaseAnonKey: 'test-key',
      );
      final dio = Dio();
      adapter = MockDioAdapter();
      dio.httpClientAdapter = adapter;
      final claudeService = ClaudeApiService(environment: env, dio: dio);
      final connectivityService = AlwaysOnlineConnectivityService();

      agent = AgentRepository(
        claudeService: claudeService,
        connectivityService: connectivityService,
      );
    });

    test('getGreeting falls back to Layer A on timeout', () async {
      adapter.setError(DioExceptionType.connectionTimeout);

      final response = await agent.getGreeting(
        now: DateTime(2026, 2, 20, 10, 0),
      );

      expect(response.layer, AgentLayer.ruleBasedLocal);
      expect(response.content, isNotEmpty);
    });

    test('getGreeting falls back to Layer A on network error', () async {
      adapter.setError(DioExceptionType.connectionError);

      final response = await agent.getGreeting(
        now: DateTime(2026, 2, 20, 19, 0),
      );

      expect(response.layer, AgentLayer.ruleBasedLocal);
      expect(response.content, 'How was your day?');
    });

    test('generateSummary falls back to Layer A on server error', () async {
      adapter.setError(DioExceptionType.connectionTimeout);

      final response = await agent.generateSummary(
        userMessages: ['Had a productive day at work.'],
        allMessages: [
          {'role': 'user', 'content': 'Had a productive day at work.'},
        ],
      );

      expect(response.layer, AgentLayer.ruleBasedLocal);
      expect(response.content, 'Had a productive day at work.');
      expect(response.metadata, isNull);
    });

    test('getFollowUp falls back to Layer A on API error', () async {
      adapter.setError(DioExceptionType.connectionError);

      final response = await agent.getFollowUp(
        latestUserMessage: 'I feel stressed',
        conversationHistory: [],
        followUpCount: 0,
        allMessages: [
          {'role': 'user', 'content': 'I feel stressed'},
        ],
      );

      expect(response, isNotNull);
      expect(response!.layer, AgentLayer.ruleBasedLocal);
    });
  });

  group('AgentRepository shouldEndSession (layer-independent)', () {
    late AgentRepository agent;

    setUp(() {
      agent = AgentRepository();
    });

    test('returns true for done signals regardless of layer', () {
      expect(
        agent.shouldEndSession(followUpCount: 0, latestUserMessage: 'no'),
        isTrue,
      );
    });

    test('returns true when followUpCount exceeds max', () {
      expect(
        agent.shouldEndSession(followUpCount: 4, latestUserMessage: 'anything'),
        isTrue,
      );
    });

    test('returns false for normal messages', () {
      expect(
        agent.shouldEndSession(
          followUpCount: 0,
          latestUserMessage: 'I had a good day',
        ),
        isFalse,
      );
    });
  });
}
