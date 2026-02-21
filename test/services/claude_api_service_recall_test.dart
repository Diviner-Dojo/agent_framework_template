import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:dio/dio.dart';
import 'package:agentic_journal/config/environment.dart';
import 'package:agentic_journal/services/claude_api_service.dart';

/// A mock Dio adapter for recall tests.
class MockDioAdapter implements HttpClientAdapter {
  RequestOptions? lastRequest;
  late ResponseBody Function(RequestOptions) _handler;

  void setResponse(int statusCode, Map<String, dynamic> data) {
    _handler = (options) {
      lastRequest = options;
      return ResponseBody.fromString(
        jsonEncode(data),
        statusCode,
        headers: {
          'content-type': ['application/json'],
        },
      );
    };
  }

  void setServerError(int statusCode, Map<String, dynamic>? body) {
    _handler = (options) {
      throw DioException(
        type: DioExceptionType.badResponse,
        requestOptions: options,
        response: Response(
          statusCode: statusCode,
          data: body,
          requestOptions: options,
        ),
      );
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
  late Dio dio;
  late MockDioAdapter adapter;
  late ClaudeApiService service;

  setUp(() {
    dio = Dio();
    adapter = MockDioAdapter();
    dio.httpClientAdapter = adapter;

    final environment = Environment.custom(
      supabaseUrl: 'https://test.supabase.co',
      supabaseAnonKey: 'test-anon-key',
    );

    service = ClaudeApiService(environment: environment, dio: dio);
  });

  group('ClaudeApiService.recall', () {
    test('successful recall with cited sessions', () async {
      adapter.setResponse(200, {
        'response': 'You talked about work stress on Feb 19.',
        'cited_sessions': ['session-1', 'session-2'],
      });

      final result = await service.recall(
        question: 'When did I feel stressed?',
        contextEntries: [
          {
            'session_id': 'session-1',
            'session_date': '2026-02-19T10:00:00.000Z',
            'summary': 'Stressful day at work',
            'snippets': ['I felt really stressed about the deadline'],
          },
        ],
      );

      expect(result.answer, 'You talked about work stress on Feb 19.');
      expect(result.citedSessionIds, ['session-1', 'session-2']);
    });

    test('missing cited_sessions returns empty list, not exception', () async {
      adapter.setResponse(200, {
        'response': 'You mentioned exercise in a few entries.',
        // No cited_sessions field at all.
      });

      final result = await service.recall(
        question: 'When did I exercise?',
        contextEntries: [
          {
            'session_id': 's1',
            'session_date': '2026-02-19T10:00:00.000Z',
            'summary': 'Morning workout',
            'snippets': [],
          },
        ],
      );

      expect(result.answer, isNotEmpty);
      expect(result.citedSessionIds, isEmpty);
    });

    test('cited_sessions with wrong types are filtered out', () async {
      adapter.setResponse(200, {
        'response': 'You mentioned that.',
        'cited_sessions': ['valid-id', 123, null, 'another-valid-id'],
      });

      final result = await service.recall(question: 'Test', contextEntries: []);

      // Only string items should be kept.
      expect(result.citedSessionIds, ['valid-id', 'another-valid-id']);
    });

    test('empty response string throws ClaudeApiParseException', () async {
      adapter.setResponse(200, {'response': ''});

      expect(
        () => service.recall(question: 'Test', contextEntries: []),
        throwsA(isA<ClaudeApiParseException>()),
      );
    });

    test('missing response field throws ClaudeApiParseException', () async {
      adapter.setResponse(200, {'some_other_field': 'data'});

      expect(
        () => service.recall(question: 'Test', contextEntries: []),
        throwsA(isA<ClaudeApiParseException>()),
      );
    });

    test('server error throws ClaudeApiServerException', () async {
      adapter.setServerError(500, {'error': 'Internal error'});

      expect(
        () => service.recall(question: 'Test', contextEntries: []),
        throwsA(isA<ClaudeApiServerException>()),
      );
    });

    test('sends correct request body', () async {
      adapter.setResponse(200, {
        'response': 'Answer here.',
        'cited_sessions': [],
      });

      await service.recall(
        question: 'What did I do?',
        contextEntries: [
          {
            'session_id': 's1',
            'session_date': '2026-02-19T10:00:00.000Z',
            'summary': 'Test',
            'snippets': ['msg1'],
          },
        ],
      );

      // Verify the request body structure.
      final requestData = adapter.lastRequest?.data as Map<String, dynamic>;
      expect(requestData['mode'], 'recall');
      expect(requestData['messages'], isA<List>());
      expect(requestData['context_entries'], isA<List>());
      expect(
        (requestData['messages'] as List).first['content'],
        'What did I do?',
      );
    });
  });
}
