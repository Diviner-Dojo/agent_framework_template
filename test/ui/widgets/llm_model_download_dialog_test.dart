// ===========================================================================
// file: test/ui/widgets/llm_model_download_dialog_test.dart
// purpose: Widget tests for the LLM model download dialog.
//
// Tests verify the initial prompt, cancel behavior, download trigger,
// and cellular warning. Uses pump() not pumpAndSettle after download
// starts to avoid LinearProgressIndicator animation deadlock.
//
// See: SPEC-20260224-014525 §R4, §R8
// ===========================================================================

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/services/llm_model_download_service.dart';
import 'package:agentic_journal/services/model_download_service.dart'
    show ModelDownloadProgress;
import 'package:agentic_journal/ui/widgets/llm_model_download_dialog.dart';

/// Mock LlmModelDownloadService for testing the dialog.
class MockLlmDownloadService extends LlmModelDownloadService {
  final StreamController<ModelDownloadProgress> _controller =
      StreamController<ModelDownloadProgress>.broadcast();

  bool isOnWifiReturn = true;
  bool downloadModelCalled = false;
  bool cancelDownloadCalled = false;

  MockLlmDownloadService() : super();

  @override
  Stream<ModelDownloadProgress> get downloadProgress => _controller.stream;

  @override
  Future<bool> isOnWifi() async => isOnWifiReturn;

  @override
  Future<String> downloadModel({bool forceOverCellular = false}) async {
    downloadModelCalled = true;
    return '/mock/llm/model/path';
  }

  @override
  void cancelDownload() {
    cancelDownloadCalled = true;
  }

  @override
  void dispose() {
    _controller.close();
    super.dispose();
  }
}

void main() {
  group('LlmModelDownloadDialog', () {
    late MockLlmDownloadService mockService;

    setUp(() {
      mockService = MockLlmDownloadService();
    });

    tearDown(() {
      mockService.dispose();
    });

    testWidgets('shows initial prompt with download info', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (context) => Scaffold(
              body: ElevatedButton(
                onPressed: () => showLlmModelDownloadDialog(
                  context: context,
                  downloadService: mockService,
                ),
                child: const Text('Open Dialog'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Open Dialog'));
      await tester.pumpAndSettle();

      expect(find.text('Local AI Model'), findsOneWidget);
      expect(find.textContaining('~380 MB'), findsOneWidget);
      expect(find.text('Download'), findsOneWidget);
      expect(find.text('Cancel'), findsOneWidget);
    });

    testWidgets('cancel button closes dialog and returns false', (
      tester,
    ) async {
      bool? result;

      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (context) => Scaffold(
              body: ElevatedButton(
                onPressed: () async {
                  result = await showLlmModelDownloadDialog(
                    context: context,
                    downloadService: mockService,
                  );
                },
                child: const Text('Open Dialog'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Open Dialog'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      expect(result, false);
      expect(mockService.cancelDownloadCalled, true);
    });

    testWidgets('download button starts download when on WiFi', (tester) async {
      mockService.isOnWifiReturn = true;

      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (context) => Scaffold(
              body: ElevatedButton(
                onPressed: () => showLlmModelDownloadDialog(
                  context: context,
                  downloadService: mockService,
                ),
                child: const Text('Open Dialog'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Open Dialog'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Download'));
      // Use pump() — after _hasStarted=true, LinearProgressIndicator
      // animates continuously, preventing pumpAndSettle from settling.
      await tester.pump();
      await tester.pump();

      expect(mockService.downloadModelCalled, true);
    });

    testWidgets('shows cellular warning when not on WiFi', (tester) async {
      mockService.isOnWifiReturn = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (context) => Scaffold(
              body: ElevatedButton(
                onPressed: () => showLlmModelDownloadDialog(
                  context: context,
                  downloadService: mockService,
                ),
                child: const Text('Open Dialog'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Open Dialog'));
      await tester.pumpAndSettle();

      expect(find.textContaining('cellular data'), findsOneWidget);
      expect(find.text('Download Now'), findsOneWidget);
      expect(find.text('Download on Wi-Fi'), findsOneWidget);
    });
  });
}
