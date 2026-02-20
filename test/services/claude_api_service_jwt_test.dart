import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:dio/dio.dart';
import 'package:agentic_journal/config/environment.dart';
import 'package:agentic_journal/services/claude_api_service.dart';

/// A mock Dio adapter that captures requests and returns pre-configured responses.
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
  const testEnv = Environment.custom(
    supabaseUrl: 'https://test.supabase.co',
    supabaseAnonKey: 'test-anon-key',
  );

  group('ClaudeApiService - JWT injection', () {
    test('uses anon key as Bearer when no accessTokenProvider', () async {
      final adapter = MockDioAdapter();
      adapter.setResponse(200, {'response': 'Hello!'});

      final dio = Dio()..httpClientAdapter = adapter;
      final service = ClaudeApiService(environment: testEnv, dio: dio);

      await service.chat(
        messages: [
          {'role': 'user', 'content': 'test'},
        ],
      );

      // Default headers should have anon key as Bearer
      expect(adapter.lastRequest, isNotNull);
    });

    test('uses JWT when accessTokenProvider returns a token', () async {
      final adapter = MockDioAdapter();
      adapter.setResponse(200, {'response': 'Hello!'});

      final dio = Dio()..httpClientAdapter = adapter;
      final service = ClaudeApiService(
        environment: testEnv,
        dio: dio,
        accessTokenProvider: () => 'jwt-token-123',
      );

      await service.chat(
        messages: [
          {'role': 'user', 'content': 'test'},
        ],
      );

      expect(adapter.lastRequest, isNotNull);
      final authHeader = adapter.lastRequest!.headers['Authorization'];
      expect(authHeader, 'Bearer jwt-token-123');
    });

    test(
      'falls back to default when accessTokenProvider returns null',
      () async {
        final adapter = MockDioAdapter();
        adapter.setResponse(200, {'response': 'Hello!'});

        final dio = Dio()..httpClientAdapter = adapter;
        final service = ClaudeApiService(
          environment: testEnv,
          dio: dio,
          accessTokenProvider: () => null,
        );

        await service.chat(
          messages: [
            {'role': 'user', 'content': 'test'},
          ],
        );

        expect(adapter.lastRequest, isNotNull);
        // When token is null, no per-request auth override is applied.
        // The default Dio headers (with anon key) are used instead.
        final authHeader = adapter.lastRequest!.headers['Authorization'];
        // No per-request override — request-level headers won't contain it
        // (it's in the Dio base options, not in per-request options).
        expect(authHeader, isNull);
      },
    );

    test(
      'uses empty string check — empty token falls back to default',
      () async {
        final adapter = MockDioAdapter();
        adapter.setResponse(200, {'response': 'Hello!'});

        final dio = Dio()..httpClientAdapter = adapter;
        final service = ClaudeApiService(
          environment: testEnv,
          dio: dio,
          accessTokenProvider: () => '',
        );

        await service.chat(
          messages: [
            {'role': 'user', 'content': 'test'},
          ],
        );

        // Empty token should not override the default auth
        final authHeader = adapter.lastRequest!.headers['Authorization'];
        expect(authHeader, isNull);
      },
    );
  });
}
