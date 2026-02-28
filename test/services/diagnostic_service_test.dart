import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:agentic_journal/config/environment.dart';
import 'package:agentic_journal/repositories/agent_repository.dart';
import 'package:agentic_journal/services/connectivity_service.dart';
import 'package:agentic_journal/services/diagnostic_service.dart';

/// A ConnectivityService that always reports online.
class _OnlineConnectivityService extends ConnectivityService {
  _OnlineConnectivityService()
    : super(
        connectivityStream:
            StreamController<List<ConnectivityResult>>.broadcast().stream,
      );

  @override
  bool get isOnline => true;
}

/// A ConnectivityService that always reports offline.
class _OfflineConnectivityService extends ConnectivityService {
  _OfflineConnectivityService()
    : super(
        connectivityStream:
            StreamController<List<ConnectivityResult>>.broadcast().stream,
      );

  @override
  bool get isOnline => false;
}

/// A Dio HTTP adapter that returns a fixed response.
class _MockDioAdapter implements HttpClientAdapter {
  final int statusCode;
  final String body;

  _MockDioAdapter({this.statusCode = 200}) : body = '{}';

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<List<int>>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    return ResponseBody.fromString(body, statusCode);
  }

  @override
  void close({bool force = false}) {}
}

/// A Dio HTTP adapter that always throws a timeout error.
class _TimeoutDioAdapter implements HttpClientAdapter {
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

Dio _createMockDio(HttpClientAdapter adapter) {
  final dio = Dio();
  dio.httpClientAdapter = adapter;
  return dio;
}

void main() {
  group('DiagnosticService', () {
    group('environment check', () {
      test('passes when configured', () async {
        final service = DiagnosticService(
          env: const Environment.custom(
            supabaseUrl: 'https://test.supabase.co',
            supabaseAnonKey: 'test-key',
          ),
          dio: _createMockDio(_MockDioAdapter()),
        );

        final results = await service.runAll();
        final envResult = results.firstWhere(
          (r) => r.name == 'Environment Config',
        );
        expect(envResult.passed, isTrue);
        expect(envResult.detail, contains('set'));
      });

      test('fails when not configured', () async {
        final service = DiagnosticService(
          env: const Environment.custom(supabaseUrl: '', supabaseAnonKey: ''),
          dio: _createMockDio(_MockDioAdapter()),
        );

        final results = await service.runAll();
        final envResult = results.firstWhere(
          (r) => r.name == 'Environment Config',
        );
        expect(envResult.passed, isFalse);
        expect(envResult.detail, contains('empty'));
      });
    });

    group('connectivity check', () {
      test('passes when online', () async {
        final service = DiagnosticService(
          connectivityService: _OnlineConnectivityService(),
          dio: _createMockDio(_MockDioAdapter()),
        );

        final results = await service.runAll();
        final check = results.firstWhere(
          (r) => r.name == 'Network Connectivity',
        );
        expect(check.passed, isTrue);
        expect(check.detail, 'Online');
      });

      test('fails when offline', () async {
        final service = DiagnosticService(
          connectivityService: _OfflineConnectivityService(),
          dio: _createMockDio(_MockDioAdapter()),
        );

        final results = await service.runAll();
        final check = results.firstWhere(
          (r) => r.name == 'Network Connectivity',
        );
        expect(check.passed, isFalse);
        expect(check.detail, contains('Offline'));
      });

      test('fails when service not available', () async {
        final service = DiagnosticService(
          dio: _createMockDio(_MockDioAdapter()),
        );

        final results = await service.runAll();
        final check = results.firstWhere(
          (r) => r.name == 'Network Connectivity',
        );
        expect(check.passed, isFalse);
        expect(check.detail, contains('not available'));
      });
    });

    group('supabase reachability check', () {
      test('passes with 200 response', () async {
        final service = DiagnosticService(
          env: const Environment.custom(
            supabaseUrl: 'https://test.supabase.co',
            supabaseAnonKey: 'test-key',
          ),
          dio: _createMockDio(_MockDioAdapter(statusCode: 200)),
        );

        final results = await service.runAll();
        final check = results.firstWhere(
          (r) => r.name == 'Supabase Reachability',
        );
        expect(check.passed, isTrue);
        expect(check.detail, contains('200'));
      });

      test('fails on timeout', () async {
        final service = DiagnosticService(
          env: const Environment.custom(
            supabaseUrl: 'https://test.supabase.co',
            supabaseAnonKey: 'test-key',
          ),
          dio: _createMockDio(_TimeoutDioAdapter()),
        );

        final results = await service.runAll();
        final check = results.firstWhere(
          (r) => r.name == 'Supabase Reachability',
        );
        expect(check.passed, isFalse);
        expect(check.detail, contains('timeout'));
      });

      test('skips when env not configured', () async {
        final service = DiagnosticService(
          env: const Environment.custom(supabaseUrl: '', supabaseAnonKey: ''),
          dio: _createMockDio(_MockDioAdapter()),
        );

        final results = await service.runAll();
        final check = results.firstWhere(
          (r) => r.name == 'Supabase Reachability',
        );
        expect(check.passed, isFalse);
        expect(check.detail, contains('not configured'));
      });
    });

    group('claude proxy check', () {
      test('passes with 200 response', () async {
        final service = DiagnosticService(
          env: const Environment.custom(
            supabaseUrl: 'https://test.supabase.co',
            supabaseAnonKey: 'test-key',
          ),
          dio: _createMockDio(_MockDioAdapter(statusCode: 200)),
        );

        final results = await service.runAll();
        final check = results.firstWhere((r) => r.name == 'Claude API Proxy');
        expect(check.passed, isTrue);
      });

      test('fails on timeout', () async {
        final service = DiagnosticService(
          env: const Environment.custom(
            supabaseUrl: 'https://test.supabase.co',
            supabaseAnonKey: 'test-key',
          ),
          dio: _createMockDio(_TimeoutDioAdapter()),
        );

        final results = await service.runAll();
        final check = results.firstWhere((r) => r.name == 'Claude API Proxy');
        expect(check.passed, isFalse);
        expect(check.detail, contains('timeout'));
      });

      test('skips when env not configured', () async {
        final service = DiagnosticService(
          env: const Environment.custom(supabaseUrl: '', supabaseAnonKey: ''),
          dio: _createMockDio(_MockDioAdapter()),
        );

        final results = await service.runAll();
        final check = results.firstWhere((r) => r.name == 'Claude API Proxy');
        expect(check.passed, isFalse);
        expect(check.detail, contains('not configured'));
      });
    });

    group('layer selection check', () {
      test('reports active layer when agent repository provided', () async {
        final repo = AgentRepository();
        final service = DiagnosticService(
          agentRepository: repo,
          dio: _createMockDio(_MockDioAdapter()),
        );

        final results = await service.runAll();
        final check = results.firstWhere((r) => r.name == 'Layer Selection');
        expect(check.detail, contains('Offline'));
      });

      test('fails when agent repository not available', () async {
        final service = DiagnosticService(
          dio: _createMockDio(_MockDioAdapter()),
        );

        final results = await service.runAll();
        final check = results.firstWhere((r) => r.name == 'Layer Selection');
        expect(check.passed, isFalse);
        expect(check.detail, contains('not available'));
      });
    });

    group('shared preferences check', () {
      test('passes when loaded', () async {
        SharedPreferences.setMockInitialValues({
          'preferClaude': true,
          'journalOnlyMode': false,
        });
        final prefs = await SharedPreferences.getInstance();

        final service = DiagnosticService(
          prefs: prefs,
          dio: _createMockDio(_MockDioAdapter()),
        );

        final results = await service.runAll();
        final check = results.firstWhere((r) => r.name == 'SharedPreferences');
        expect(check.passed, isTrue);
        expect(check.detail, contains('preferClaude=true'));
        expect(check.detail, contains('journalOnlyMode=false'));
      });

      test('fails when not loaded', () async {
        final service = DiagnosticService(
          dio: _createMockDio(_MockDioAdapter()),
        );

        final results = await service.runAll();
        final check = results.firstWhere((r) => r.name == 'SharedPreferences');
        expect(check.passed, isFalse);
        expect(check.detail, 'Not loaded');
      });
    });

    group('TTS proxy check', () {
      test('passes when reachable', () async {
        final service = DiagnosticService(
          env: const Environment.custom(
            supabaseUrl: 'https://test.supabase.co',
            supabaseAnonKey: 'test-key',
          ),
          dio: _createMockDio(_MockDioAdapter(statusCode: 405)),
        );

        final results = await service.runAll();
        final check = results.firstWhere((r) => r.name == 'TTS Proxy');
        expect(check.passed, isTrue);
        expect(check.detail, contains('Reachable'));
      });

      test('fails on timeout', () async {
        final service = DiagnosticService(
          env: const Environment.custom(
            supabaseUrl: 'https://test.supabase.co',
            supabaseAnonKey: 'test-key',
          ),
          dio: _createMockDio(_TimeoutDioAdapter()),
        );

        final results = await service.runAll();
        final check = results.firstWhere((r) => r.name == 'TTS Proxy');
        expect(check.passed, isFalse);
        expect(check.detail, contains('timeout'));
      });
    });

    group('runAll', () {
      test('returns results for all 8 checks', () async {
        final service = DiagnosticService(
          dio: _createMockDio(_MockDioAdapter()),
        );

        final results = await service.runAll();
        expect(results, hasLength(8));

        final names = results.map((r) => r.name).toSet();
        expect(
          names,
          containsAll([
            'Environment Config',
            'Network Connectivity',
            'Supabase Reachability',
            'Claude API Proxy',
            'Layer Selection',
            'SharedPreferences',
            'TTS Proxy',
            'Local LLM',
          ]),
        );
      });

      test('all results have non-negative elapsed time', () async {
        final service = DiagnosticService(
          dio: _createMockDio(_MockDioAdapter()),
        );

        final results = await service.runAll();
        for (final result in results) {
          expect(
            result.elapsed.inMicroseconds,
            greaterThanOrEqualTo(0),
            reason: '${result.name} elapsed time should be non-negative',
          );
        }
      });
    });
  });
}
