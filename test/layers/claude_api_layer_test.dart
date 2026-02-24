import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:dio/dio.dart';
import 'package:agentic_journal/config/environment.dart';
import 'package:agentic_journal/layers/claude_api_layer.dart';
import 'package:agentic_journal/models/agent_response.dart';
import 'package:agentic_journal/services/claude_api_service.dart';

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

void main() {
  late ClaudeApiLayer layer;
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

    layer = ClaudeApiLayer(claudeService: claudeService);
  });

  group('ClaudeApiLayer getGreeting', () {
    test('returns llmRemote layer on successful API call', () async {
      adapter.setResponse(
        200,
        '{"response": "Hello there! Ready to journal?"}',
      );

      final response = await layer.getGreeting(
        now: DateTime(2026, 2, 23, 10, 0),
        sessionCount: 5,
      );

      expect(response.layer, AgentLayer.llmRemote);
      expect(response.content, 'Hello there! Ready to journal?');
    });

    test('throws ClaudeApiException on timeout', () async {
      adapter.setError(DioExceptionType.connectionTimeout);

      await expectLater(
        layer.getGreeting(now: DateTime(2026, 2, 23, 10, 0)),
        throwsA(isA<ClaudeApiException>()),
      );
    });

    test('throws ClaudeApiException on network error', () async {
      adapter.setError(DioExceptionType.connectionError);

      await expectLater(
        layer.getGreeting(now: DateTime(2026, 2, 23, 10, 0)),
        throwsA(isA<ClaudeApiException>()),
      );
    });
  });

  group('ClaudeApiLayer getFollowUp', () {
    test('returns llmRemote response on success', () async {
      adapter.setResponse(200, '{"response": "Tell me more about that."}');

      final response = await layer.getFollowUp(
        latestUserMessage: 'I feel stressed',
        conversationHistory: [],
        followUpCount: 0,
        allMessages: [
          {'role': 'user', 'content': 'I feel stressed'},
        ],
      );

      expect(response, isNotNull);
      expect(response!.layer, AgentLayer.llmRemote);
      expect(response.content, 'Tell me more about that.');
    });

    test('returns null when allMessages is null', () async {
      final response = await layer.getFollowUp(
        latestUserMessage: 'test',
        conversationHistory: [],
        followUpCount: 0,
      );
      expect(response, isNull);
    });

    test('returns null when allMessages is empty', () async {
      final response = await layer.getFollowUp(
        latestUserMessage: 'test',
        conversationHistory: [],
        followUpCount: 0,
        allMessages: [],
      );
      expect(response, isNull);
    });

    test('throws ClaudeApiException on API error', () async {
      adapter.setError(DioExceptionType.connectionTimeout);

      await expectLater(
        layer.getFollowUp(
          latestUserMessage: 'test',
          conversationHistory: [],
          followUpCount: 0,
          allMessages: [
            {'role': 'user', 'content': 'test'},
          ],
        ),
        throwsA(isA<ClaudeApiException>()),
      );
    });
  });

  group('ClaudeApiLayer generateSummary', () {
    test('returns metadata from Claude on success', () async {
      // extractMetadata expects { "metadata": { ... } } in the response.
      adapter.setResponse(200, '''
        {
          "metadata": {
            "summary": "User discussed their stressful day at work.",
            "mood_tags": ["stressed", "tired"],
            "people": ["coworker"],
            "topic_tags": ["work", "stress"]
          }
        }
      ''');

      final response = await layer.generateSummary(
        userMessages: ['Work was really stressful today.'],
        allMessages: [
          {'role': 'user', 'content': 'Work was really stressful today.'},
        ],
      );

      expect(response.layer, AgentLayer.llmRemote);
      expect(response.metadata, isNotNull);
      expect(response.content, 'User discussed their stressful day at work.');
    });

    test('uses fallback summary when allMessages is null', () async {
      final response = await layer.generateSummary(
        userMessages: ['Had a good day.'],
      );

      expect(response.layer, AgentLayer.llmRemote);
      expect(response.content, 'Had a good day.');
    });

    test('throws ClaudeApiException on API error', () async {
      adapter.setError(DioExceptionType.connectionTimeout);

      await expectLater(
        layer.generateSummary(
          userMessages: ['test'],
          allMessages: [
            {'role': 'user', 'content': 'test'},
          ],
        ),
        throwsA(isA<ClaudeApiException>()),
      );
    });
  });

  group('ClaudeApiLayer getResumeGreeting', () {
    test('returns fixed resume greeting', () async {
      final response = await layer.getResumeGreeting();
      expect(
        response.content,
        "Welcome back! Let's continue where you left off.",
      );
      expect(response.layer, AgentLayer.llmRemote);
    });
  });
}
