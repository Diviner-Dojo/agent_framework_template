import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/ui/widgets/photo_capture_sheet.dart';

void main() {
  group('MediaCaptureSheet', () {
    testWidgets('shows all four media options', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => ElevatedButton(
                onPressed: () => showMediaCaptureSheet(context),
                child: const Text('Open'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Open'));
      await tester.pumpAndSettle();

      expect(find.text('Take Photo'), findsOneWidget);
      expect(find.text('Choose Photo from Gallery'), findsOneWidget);
      expect(find.text('Record Video'), findsOneWidget);
      expect(find.text('Choose Video from Gallery'), findsOneWidget);
      expect(find.byIcon(Icons.camera_alt), findsOneWidget);
      expect(find.byIcon(Icons.photo_library), findsOneWidget);
      expect(find.byIcon(Icons.videocam), findsOneWidget);
      expect(find.byIcon(Icons.video_library), findsOneWidget);
    });

    testWidgets('shows 60 second limit subtitle on Record Video', (
      tester,
    ) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => ElevatedButton(
                onPressed: () => showMediaCaptureSheet(context),
                child: const Text('Open'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Open'));
      await tester.pumpAndSettle();

      expect(find.text('Up to 60 seconds'), findsOneWidget);
    });

    testWidgets('returns photoCamera when Take Photo is tapped', (
      tester,
    ) async {
      MediaSource? selected;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => ElevatedButton(
                onPressed: () async {
                  selected = await showMediaCaptureSheet(context);
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

      expect(selected, MediaSource.photoCamera);
    });

    testWidgets('returns photoGallery when Choose Photo is tapped', (
      tester,
    ) async {
      MediaSource? selected;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => ElevatedButton(
                onPressed: () async {
                  selected = await showMediaCaptureSheet(context);
                },
                child: const Text('Open'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Open'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Choose Photo from Gallery'));
      await tester.pumpAndSettle();

      expect(selected, MediaSource.photoGallery);
    });

    testWidgets('returns videoCamera when Record Video is tapped', (
      tester,
    ) async {
      MediaSource? selected;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => ElevatedButton(
                onPressed: () async {
                  selected = await showMediaCaptureSheet(context);
                },
                child: const Text('Open'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Open'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Record Video'));
      await tester.pumpAndSettle();

      expect(selected, MediaSource.videoCamera);
    });

    testWidgets('returns videoGallery when Choose Video is tapped', (
      tester,
    ) async {
      MediaSource? selected;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => ElevatedButton(
                onPressed: () async {
                  selected = await showMediaCaptureSheet(context);
                },
                child: const Text('Open'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Open'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Choose Video from Gallery'));
      await tester.pumpAndSettle();

      expect(selected, MediaSource.videoGallery);
    });

    testWidgets('showPhotoCaptureSheet legacy alias works', (tester) async {
      MediaSource? selected;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => ElevatedButton(
                onPressed: () async {
                  selected = await showPhotoCaptureSheet(context);
                },
                child: const Text('Open'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Open'));
      await tester.pumpAndSettle();

      // Legacy function should show the same media sheet.
      expect(find.text('Take Photo'), findsOneWidget);
      expect(find.text('Record Video'), findsOneWidget);

      await tester.tap(find.text('Take Photo'));
      await tester.pumpAndSettle();

      expect(selected, MediaSource.photoCamera);
    });
  });

  group('MediaSource', () {
    test('has four values', () {
      expect(MediaSource.values.length, 4);
      expect(MediaSource.values, contains(MediaSource.photoCamera));
      expect(MediaSource.values, contains(MediaSource.photoGallery));
      expect(MediaSource.values, contains(MediaSource.videoCamera));
      expect(MediaSource.values, contains(MediaSource.videoGallery));
    });
  });
}
