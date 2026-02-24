// ===========================================================================
// file: test/services/llm_model_download_service_test.dart
// purpose: Tests for LlmModelDownloadService — model file info, WiFi check,
//          AccumulatorSink, and static helpers.
//
// Actual download tests require network mocking and are covered by
// integration tests. These unit tests verify the testable surface area.
//
// See: SPEC-20260224-014525 §R3, §R8
// ===========================================================================

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/services/llm_model_download_service.dart';

/// Mock Connectivity that returns configurable results.
class MockConnectivity implements Connectivity {
  final List<ConnectivityResult> _results;

  MockConnectivity(this._results);

  @override
  Future<List<ConnectivityResult>> checkConnectivity() async => _results;

  @override
  Stream<List<ConnectivityResult>> get onConnectivityChanged =>
      Stream.value(_results);
}

void main() {
  group('LlmModelDownloadService.modelFile', () {
    test('has non-empty SHA-256 checksum', () {
      expect(LlmModelDownloadService.modelFile.sha256, isNotEmpty);
      // SHA-256 is 64 hex characters.
      expect(LlmModelDownloadService.modelFile.sha256.length, 64);
    });

    test('has expected model name', () {
      expect(
        LlmModelDownloadService.modelFile.name,
        'qwen2.5-0.5b-instruct-q4_k_m',
      );
    });

    test('has HuggingFace URL', () {
      expect(LlmModelDownloadService.modelFile.url, contains('huggingface.co'));
      expect(LlmModelDownloadService.modelFile.url, contains('.gguf'));
    });

    test('has expected size around 380MB', () {
      // Expected size should be in the 350-420MB range.
      expect(
        LlmModelDownloadService.modelFile.expectedSize,
        greaterThan(350000000),
      );
      expect(
        LlmModelDownloadService.modelFile.expectedSize,
        lessThan(420000000),
      );
    });
  });

  group('isOnWifi', () {
    test('returns true when on WiFi', () async {
      final service = LlmModelDownloadService(
        connectivity: MockConnectivity([ConnectivityResult.wifi]),
      );
      addTearDown(service.dispose);

      expect(await service.isOnWifi(), isTrue);
    });

    test('returns false when on mobile only', () async {
      final service = LlmModelDownloadService(
        connectivity: MockConnectivity([ConnectivityResult.mobile]),
      );
      addTearDown(service.dispose);

      expect(await service.isOnWifi(), isFalse);
    });

    test('returns false when no connectivity', () async {
      final service = LlmModelDownloadService(
        connectivity: MockConnectivity([ConnectivityResult.none]),
      );
      addTearDown(service.dispose);

      expect(await service.isOnWifi(), isFalse);
    });

    test('returns false when empty result list', () async {
      final service = LlmModelDownloadService(
        connectivity: MockConnectivity([]),
      );
      addTearDown(service.dispose);

      expect(await service.isOnWifi(), isFalse);
    });

    test('returns true when WiFi + mobile (dual connectivity)', () async {
      final service = LlmModelDownloadService(
        connectivity: MockConnectivity([
          ConnectivityResult.wifi,
          ConnectivityResult.mobile,
        ]),
      );
      addTearDown(service.dispose);

      expect(await service.isOnWifi(), isTrue);
    });
  });

  group('AccumulatorSink', () {
    test('collects events', () {
      final sink = AccumulatorSink<int>();
      sink.add(1);
      sink.add(2);
      sink.add(3);
      sink.close();
      expect(sink.events, [1, 2, 3]);
    });

    test('single returns the single event', () {
      final sink = AccumulatorSink<String>();
      sink.add('only');
      sink.close();
      expect(sink.single, 'only');
    });

    test('single throws on multiple events', () {
      final sink = AccumulatorSink<int>();
      sink.add(1);
      sink.add(2);
      sink.close();
      expect(() => sink.single, throwsA(isA<StateError>()));
    });
  });

  group('downloadProgress stream', () {
    test('returns a broadcast stream', () {
      final service = LlmModelDownloadService();
      addTearDown(service.dispose);

      final stream = service.downloadProgress;
      expect(stream.isBroadcast, isTrue);
    });

    test('returns broadcast stream on multiple accesses', () {
      final service = LlmModelDownloadService();
      addTearDown(service.dispose);

      final stream1 = service.downloadProgress;
      final stream2 = service.downloadProgress;
      // Both should be broadcast streams (multiple listeners allowed).
      expect(stream1.isBroadcast, isTrue);
      expect(stream2.isBroadcast, isTrue);
    });
  });

  group('cancelDownload', () {
    test('is safe to call when no download is in progress', () {
      final service = LlmModelDownloadService();
      addTearDown(service.dispose);

      // Should not throw.
      service.cancelDownload();
    });
  });

  group('dispose', () {
    test('is safe to call multiple times', () {
      final service = LlmModelDownloadService();
      service.dispose();
      // Should not throw.
      service.dispose();
    });
  });
}
