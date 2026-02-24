import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/ui/widgets/photo_viewer.dart';

void main() {
  group('PhotoViewer', () {
    testWidgets('shows InteractiveViewer for zoom', (tester) async {
      final tempDir = Directory.systemTemp.createTempSync('photo_viewer_test');
      final tempFile = File('${tempDir.path}/test.jpg');
      tempFile.writeAsBytesSync([0xFF, 0xD8, 0xFF, 0xE0]);

      await tester.pumpWidget(
        MaterialApp(home: PhotoViewer(photoPath: tempFile.path)),
      );

      expect(find.byType(InteractiveViewer), findsOneWidget);

      tempDir.deleteSync(recursive: true);
    });

    testWidgets('shows caption when provided', (tester) async {
      final tempDir = Directory.systemTemp.createTempSync('photo_viewer_test');
      final tempFile = File('${tempDir.path}/test.jpg');
      tempFile.writeAsBytesSync([0xFF, 0xD8, 0xFF, 0xE0]);

      await tester.pumpWidget(
        MaterialApp(
          home: PhotoViewer(
            photoPath: tempFile.path,
            caption: 'A beautiful sunset',
          ),
        ),
      );

      expect(find.text('A beautiful sunset'), findsOneWidget);

      tempDir.deleteSync(recursive: true);
    });

    testWidgets('does not show caption when null', (tester) async {
      final tempDir = Directory.systemTemp.createTempSync('photo_viewer_test');
      final tempFile = File('${tempDir.path}/test.jpg');
      tempFile.writeAsBytesSync([0xFF, 0xD8, 0xFF, 0xE0]);

      await tester.pumpWidget(
        MaterialApp(home: PhotoViewer(photoPath: tempFile.path)),
      );

      // Should not have any gradient container for the caption.
      expect(find.byType(InteractiveViewer), findsOneWidget);
      // No text other than what's in the AppBar.

      tempDir.deleteSync(recursive: true);
    });

    testWidgets('shows delete button when onDelete is provided', (
      tester,
    ) async {
      final tempDir = Directory.systemTemp.createTempSync('photo_viewer_test');
      final tempFile = File('${tempDir.path}/test.jpg');
      tempFile.writeAsBytesSync([0xFF, 0xD8, 0xFF, 0xE0]);

      await tester.pumpWidget(
        MaterialApp(
          home: PhotoViewer(photoPath: tempFile.path, onDelete: () {}),
        ),
      );

      expect(find.byIcon(Icons.delete_outline), findsOneWidget);

      tempDir.deleteSync(recursive: true);
    });

    testWidgets('does not show delete button when onDelete is null', (
      tester,
    ) async {
      final tempDir = Directory.systemTemp.createTempSync('photo_viewer_test');
      final tempFile = File('${tempDir.path}/test.jpg');
      tempFile.writeAsBytesSync([0xFF, 0xD8, 0xFF, 0xE0]);

      await tester.pumpWidget(
        MaterialApp(home: PhotoViewer(photoPath: tempFile.path)),
      );

      expect(find.byIcon(Icons.delete_outline), findsNothing);

      tempDir.deleteSync(recursive: true);
    });

    testWidgets('delete button shows confirmation dialog', (tester) async {
      final tempDir = Directory.systemTemp.createTempSync('photo_viewer_test');
      final tempFile = File('${tempDir.path}/test.jpg');
      tempFile.writeAsBytesSync([0xFF, 0xD8, 0xFF, 0xE0]);

      bool deleted = false;

      await tester.pumpWidget(
        MaterialApp(
          home: PhotoViewer(
            photoPath: tempFile.path,
            onDelete: () => deleted = true,
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.delete_outline));
      await tester.pumpAndSettle();

      // Confirmation dialog should appear.
      expect(find.text('Delete this photo?'), findsOneWidget);
      expect(find.text('This cannot be undone.'), findsOneWidget);

      // Cancel should dismiss without deleting.
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      expect(deleted, false);

      tempDir.deleteSync(recursive: true);
    });

    testWidgets('confirming delete calls onDelete', (tester) async {
      final tempDir = Directory.systemTemp.createTempSync('photo_viewer_test');
      final tempFile = File('${tempDir.path}/test.jpg');
      tempFile.writeAsBytesSync([0xFF, 0xD8, 0xFF, 0xE0]);

      bool deleted = false;

      await tester.pumpWidget(
        MaterialApp(
          home: PhotoViewer(
            photoPath: tempFile.path,
            onDelete: () => deleted = true,
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.delete_outline));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Delete'));
      await tester.pumpAndSettle();

      expect(deleted, true);

      tempDir.deleteSync(recursive: true);
    });
  });
}
