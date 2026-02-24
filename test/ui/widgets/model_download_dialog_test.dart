// ===========================================================================
// file: test/ui/widgets/model_download_dialog_test.dart
// purpose: Widget tests for the model download dialog.
//
// Tests verify that:
//   - The dialog shows the initial prompt with download size
//   - The cancel button closes the dialog
//   - The download button starts the download on WiFi
//   - The cellular warning is shown when not on WiFi
//
// Note: Progress display, retry, and completion tests are omitted because
// LinearProgressIndicator's continuous animation prevents pumpAndSettle
// from ever settling. The download/progress logic is tested at the service
// layer in model_download_service_test.dart.
// ===========================================================================

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/services/model_download_service.dart';
import 'package:agentic_journal/ui/widgets/model_download_dialog.dart';

/// Mock ModelDownloadService for testing the dialog.
class MockModelDownloadService extends ModelDownloadService {
  final StreamController<ModelDownloadProgress> _controller =
      StreamController<ModelDownloadProgress>.broadcast();

  bool isOnWifiReturn = true;
  bool downloadModelCalled = false;
  bool cancelDownloadCalled = false;

  MockModelDownloadService() : super();

  @override
  Stream<ModelDownloadProgress> get downloadProgress => _controller.stream;

  @override
  Future<bool> isOnWifi() async => isOnWifiReturn;

  @override
  Future<String> downloadModel({bool forceOverCellular = false}) async {
    downloadModelCalled = true;
    return '/mock/model/path';
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
  group('ModelDownloadDialog', () {
    late MockModelDownloadService mockService;

    setUp(() {
      mockService = MockModelDownloadService();
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
                onPressed: () => showModelDownloadDialog(
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

      expect(find.text('Speech Model Required'), findsOneWidget);
      expect(find.textContaining('~43 MB'), findsOneWidget);
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
                  result = await showModelDownloadDialog(
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
                onPressed: () => showModelDownloadDialog(
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
      // Use pump() — after _hasStarted=true, the LinearProgressIndicator
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
                onPressed: () => showModelDownloadDialog(
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
      // WiFi download button should be disabled.
      expect(find.text('Download on Wi-Fi'), findsOneWidget);
    });
  });
}
