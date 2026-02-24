import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/ui/widgets/photo_capture_sheet.dart';

void main() {
  group('PhotoCaptureSheet', () {
    testWidgets('shows camera and gallery options', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => ElevatedButton(
                onPressed: () => showPhotoCaptureSheet(context),
                child: const Text('Open'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Open'));
      await tester.pumpAndSettle();

      expect(find.text('Take Photo'), findsOneWidget);
      expect(find.text('Choose from Gallery'), findsOneWidget);
      expect(find.byIcon(Icons.camera_alt), findsOneWidget);
      expect(find.byIcon(Icons.photo_library), findsOneWidget);
    });

    testWidgets('returns camera when Take Photo is tapped', (tester) async {
      PhotoSource? selectedSource;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => ElevatedButton(
                onPressed: () async {
                  selectedSource = await showPhotoCaptureSheet(context);
                },
                child: const Text('Open'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Open'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Take Photo'));
      await tester.pumpAndSettle();

      expect(selectedSource, PhotoSource.camera);
    });

    testWidgets('returns gallery when Choose from Gallery is tapped', (
      tester,
    ) async {
      PhotoSource? selectedSource;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => ElevatedButton(
                onPressed: () async {
                  selectedSource = await showPhotoCaptureSheet(context);
                },
                child: const Text('Open'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Open'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Choose from Gallery'));
      await tester.pumpAndSettle();

      expect(selectedSource, PhotoSource.gallery);
    });
  });

  group('PhotoSource', () {
    test('has camera and gallery values', () {
      expect(PhotoSource.values.length, 2);
      expect(PhotoSource.values, contains(PhotoSource.camera));
      expect(PhotoSource.values, contains(PhotoSource.gallery));
    });
  });
}
