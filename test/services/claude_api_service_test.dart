import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:dio/dio.dart';
import 'package:agentic_journal/config/environment.dart';
import 'package:agentic_journal/services/claude_api_service.dart';

/// A mock Dio adapter that returns pre-configured responses.
///
/// This replaces the real HTTP layer so tests never hit the network.
/// Each test configures the adapter with a specific response or error.
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

  void setError(DioExceptionType type, {String? message}) {
    _handler = (options) {
      throw DioException(type: type, requestOptions: options, message: message);
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
  late Environment environment;
  late ClaudeApiService service;

  setUp(() {
    dio = Dio();
    adapter = MockDioAdapter();
    dio.httpClientAdapter = adapter;

    environment = Environment.custom(
      supabaseUrl: 'https://test.supabase.co',
      supabaseAnonKey: 'test-anon-key',
    );

    service = ClaudeApiService(environment: environment, dio: dio);
  });

  group('isConfigured', () {
    test('returns true when environment is configured and secure', () {
      expect(service.isConfigured, isTrue);
    });

    test('returns false when environment has empty URL', () {
      final unconfiguredEnv = Environment.custom(
        supabaseUrl: '',
        supabaseAnonKey: 'key',
      );
      final unconfiguredService = ClaudeApiService(
        environment: unconfiguredEnv,
        dio: dio,
      );
      expect(unconfiguredService.isConfigured, isFalse);
    });

    test('returns false when environment has HTTP URL', () {
      final insecureEnv = Environment.custom(
        supabaseUrl: 'http://test.supabase.co',
        supabaseAnonKey: 'key',
      );
      final insecureService = ClaudeApiService(
        environment: insecureEnv,
        dio: dio,
      );
      expect(insecureService.isConfigured, isFalse);
    });
  });

  group('chat', () {
    test('returns response text on success', () async {
      adapter.setResponse(200, {'response': 'How was your day?'});

      final result = await service.chat(
        messages: [
          {'role': 'user', 'content': 'Hello'},
        ],
      );

      expect(result, 'How was your day?');
    });

    test('sends messages and context in request body', () async {
      adapter.setResponse(200, {'response': 'Hi!'});

      await service.chat(
        messages: [
          {'role': 'user', 'content': 'Hello'},
        ],
        context: {'time_of_day': 'morning'},
      );

      expect(adapter.lastRequest, isNotNull);
      final body = adapter.lastRequest!.data as Map<String, dynamic>;
      expect(body['mode'], 'chat');
      expect(body['messages'], isNotNull);
      expect(body['context'], isNotNull);
    });

    test(
      'throws ClaudeApiParseException when response field is missing',
      () async {
        adapter.setResponse(200, {'other': 'data'});

        await expectLater(
          () => service.chat(
            messages: [
              {'role': 'user', 'content': 'Hello'},
            ],
          ),
          throwsA(isA<ClaudeApiParseException>()),
        );
      },
    );

    test(
      'throws ClaudeApiParseException when response is empty string',
      () async {
        adapter.setResponse(200, {'response': ''});

        await expectLater(
          () => service.chat(
            messages: [
              {'role': 'user', 'content': 'Hello'},
            ],
          ),
          throwsA(isA<ClaudeApiParseException>()),
        );
      },
    );

    test('throws ClaudeApiTimeoutException on timeout', () async {
      adapter.setError(DioExceptionType.connectionTimeout);

      await expectLater(
        () => service.chat(
          messages: [
            {'role': 'user', 'content': 'Hello'},
          ],
        ),
        throwsA(isA<ClaudeApiTimeoutException>()),
      );
    });

    test('throws ClaudeApiTimeoutException on receive timeout', () async {
      adapter.setError(DioExceptionType.receiveTimeout);

      await expectLater(
        () => service.chat(
          messages: [
            {'role': 'user', 'content': 'Hello'},
          ],
        ),
        throwsA(isA<ClaudeApiTimeoutException>()),
      );
    });

    test('throws ClaudeApiNetworkException on connection error', () async {
      adapter.setError(
        DioExceptionType.connectionError,
        message: 'Connection refused',
      );

      await expectLater(
        () => service.chat(
          messages: [
            {'role': 'user', 'content': 'Hello'},
          ],
        ),
        throwsA(isA<ClaudeApiNetworkException>()),
      );
    });

    test('throws ClaudeApiServerException on 429 rate limit', () async {
      adapter.setServerError(429, {'error': 'Rate limit exceeded'});

      await expectLater(
        () => service.chat(
          messages: [
            {'role': 'user', 'content': 'Hello'},
          ],
        ),
        throwsA(
          isA<ClaudeApiServerException>().having(
            (e) => e.statusCode,
            'statusCode',
            429,
          ),
        ),
      );
    });

    test(
      'throws ClaudeApiNotConfiguredException when not configured',
      () async {
        final unconfiguredService = ClaudeApiService(
          environment: Environment.custom(supabaseUrl: '', supabaseAnonKey: ''),
          dio: dio,
        );

        await expectLater(
          () => unconfiguredService.chat(
            messages: [
              {'role': 'user', 'content': 'Hello'},
            ],
          ),
          throwsA(isA<ClaudeApiNotConfiguredException>()),
        );
      },
    );
  });

  group('extractMetadata', () {
    test('falls back to text parsing when metadata key is not a Map', () async {
      // Simulate Edge Function returning raw text (METADATA_PARSE_ERROR path):
      // metadata is null, but response contains parseable JSON.
      adapter.setResponse(200, {
        'response':
            '{"summary":"A good day","mood_tags":["happy"],"people":["Alice"],"topic_tags":["work"]}',
        'metadata': null,
      });

      final result = await service.extractMetadata(
        messages: [
          {'role': 'user', 'content': 'Today was great'},
        ],
      );

      expect(result.summary, 'A good day');
      expect(result.moodTags, ['happy']);
      expect(result.people, ['Alice']);
      expect(result.topicTags, ['work']);
    });

    test(
      'returns empty metadata when text fallback has unparseable JSON',
      () async {
        adapter.setResponse(200, {
          'response': 'This is not JSON at all',
          'metadata': null,
        });

        final result = await service.extractMetadata(
          messages: [
            {'role': 'user', 'content': 'test'},
          ],
        );

        expect(result.summary, isNull);
        expect(result.moodTags, isNull);
      },
    );

    test('parses structured metadata from response', () async {
      adapter.setResponse(200, {
        'metadata': {
          'summary': 'Had a productive day at work',
          'mood_tags': ['focused', 'energetic'],
          'people': ['Sarah'],
          'topic_tags': ['work', 'meetings'],
        },
      });

      final result = await service.extractMetadata(
        messages: [
          {'role': 'user', 'content': 'Today was productive'},
        ],
      );

      expect(result.summary, 'Had a productive day at work');
      expect(result.moodTags, ['focused', 'energetic']);
      expect(result.people, ['Sarah']);
      expect(result.topicTags, ['work', 'meetings']);
    });

    test('returns empty metadata when metadata key is missing', () async {
      adapter.setResponse(200, {'other': 'data'});

      final result = await service.extractMetadata(
        messages: [
          {'role': 'user', 'content': 'test'},
        ],
      );

      expect(result.summary, isNull);
      expect(result.moodTags, isNull);
    });

    test('handles metadata with wrong type gracefully', () async {
      adapter.setResponse(200, {
        'metadata': {'summary': 'test', 'mood_tags': 'not-an-array'},
      });

      final result = await service.extractMetadata(
        messages: [
          {'role': 'user', 'content': 'test'},
        ],
      );

      expect(result.summary, 'test');
      expect(result.moodTags, isNull);
    });
  });
}
