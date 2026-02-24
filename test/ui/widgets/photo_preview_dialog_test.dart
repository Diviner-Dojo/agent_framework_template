import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/ui/widgets/photo_preview_dialog.dart';

void main() {
  group('PhotoPreviewDialog', () {
    testWidgets('shows Add and Cancel buttons', (tester) async {
      // Create a temporary file for the test.
      final tempDir = Directory.systemTemp.createTempSync('photo_test');
      final tempFile = File('${tempDir.path}/test.jpg');
      // Write minimal JPEG bytes (just enough to not crash Image.file).
      tempFile.writeAsBytesSync([
        0xFF, 0xD8, 0xFF, 0xE0, // JPEG header
      ]);

      bool? result;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => ElevatedButton(
                onPressed: () async {
                  result = await showPhotoPreviewDialog(
                    context: context,
                    photoFile: tempFile,
                  );
                },
                child: const Text('Preview'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Preview'));
      await tester.pumpAndSettle();

      expect(find.text('Add'), findsOneWidget);
      expect(find.text('Cancel'), findsOneWidget);

      // Tap Cancel.
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      expect(result, false);

      // Cleanup.
      tempDir.deleteSync(recursive: true);
    });

    testWidgets('shows processing indicator when isProcessing is true', (
      tester,
    ) async {
      final tempDir = Directory.systemTemp.createTempSync('photo_test');
      final tempFile = File('${tempDir.path}/test.jpg');
      tempFile.writeAsBytesSync([0xFF, 0xD8, 0xFF, 0xE0]);

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => ElevatedButton(
                onPressed: () async {
                  await showPhotoPreviewDialog(
                    context: context,
                    photoFile: tempFile,
                    isProcessing: true,
                  );
                },
                child: const Text('Preview'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Preview'));
      // Use pump() instead of pumpAndSettle() because
      // CircularProgressIndicator keeps animating.
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.text('Processing...'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      // Buttons should be disabled during processing.
      final addButton = tester.widget<FilledButton>(
        find.widgetWithText(FilledButton, 'Add'),
      );
      expect(addButton.onPressed, isNull);

      // Dismiss via navigator for cleanup.
      Navigator.of(tester.element(find.text('Processing...'))).pop();
      await tester.pump();

      tempDir.deleteSync(recursive: true);
    });

    testWidgets('returns true when Add is tapped', (tester) async {
      final tempDir = Directory.systemTemp.createTempSync('photo_test');
      final tempFile = File('${tempDir.path}/test.jpg');
      tempFile.writeAsBytesSync([0xFF, 0xD8, 0xFF, 0xE0]);

      bool? result;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => ElevatedButton(
                onPressed: () async {
                  result = await showPhotoPreviewDialog(
                    context: context,
                    photoFile: tempFile,
                  );
                },
                child: const Text('Preview'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Preview'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Add'));
      await tester.pumpAndSettle();

      expect(result, true);

      tempDir.deleteSync(recursive: true);
    });
  });
}
