import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/providers/photo_providers.dart';
import 'package:agentic_journal/ui/screens/photo_gallery_screen.dart';

void main() {
  group('PhotoGalleryScreen', () {
    Widget buildApp({List<Photo> photos = const []}) {
      return ProviderScope(
        overrides: [
          allPhotosProvider.overrideWith((_) => Stream.value(photos)),
        ],
        child: const MaterialApp(home: PhotoGalleryScreen()),
      );
    }

    testWidgets('shows empty state when no photos exist', (tester) async {
      await tester.pumpWidget(buildApp());
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.text('No photos yet'), findsOneWidget);
      expect(
        find.text('Photos you add to journal entries will appear here.'),
        findsOneWidget,
      );
      expect(find.byIcon(Icons.photo_library_outlined), findsOneWidget);
    });

    testWidgets('shows photo grid when photos exist', (tester) async {
      // Create a temp image file.
      final tempDir = Directory.systemTemp.createTempSync(
        'gallery_screen_test',
      );
      addTearDown(() => tempDir.deleteSync(recursive: true));

      final tempFile = File('${tempDir.path}/test.jpg');
      tempFile.writeAsBytesSync([0xFF, 0xD8, 0xFF, 0xE0]);

      final photo = Photo(
        photoId: 'photo-1',
        sessionId: 'sess-1',
        messageId: null,
        localPath: tempFile.path,
        cloudUrl: null,
        description: 'Test photo',
        timestamp: DateTime.now(),
        syncStatus: 'PENDING',
        width: null,
        height: null,
        fileSizeBytes: null,
        createdAt: DateTime.now(),
        updatedAt: DateTime.now(),
      );

      await tester.pumpWidget(buildApp(photos: [photo]));
      await tester.pump(const Duration(milliseconds: 100));

      // Should not show empty state.
      expect(find.text('No photos yet'), findsNothing);
      // Should have a GridView.
      expect(find.byType(GridView), findsOneWidget);
    });

    testWidgets('shows app bar with title', (tester) async {
      await tester.pumpWidget(buildApp());
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.text('Photo Gallery'), findsOneWidget);
    });

    testWidgets('shows loading indicator initially', (tester) async {
      // Use a stream that never emits to stay in loading state.
      final app = ProviderScope(
        overrides: [
          allPhotosProvider.overrideWith(
            (_) => const Stream<List<Photo>>.empty(),
          ),
        ],
        child: const MaterialApp(home: PhotoGalleryScreen()),
      );

      await tester.pumpWidget(app);
      await tester.pump();

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('shows error state when provider errors', (tester) async {
      final app = ProviderScope(
        overrides: [
          allPhotosProvider.overrideWith(
            (_) => Stream<List<Photo>>.error('Database error'),
          ),
        ],
        child: const MaterialApp(home: PhotoGalleryScreen()),
      );

      await tester.pumpWidget(app);
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.textContaining('Error:'), findsOneWidget);
    });

    testWidgets('tapping photo navigates to PhotoViewer', (tester) async {
      final tempDir = Directory.systemTemp.createTempSync('gallery_tap_test');
      addTearDown(() => tempDir.deleteSync(recursive: true));

      final tempFile = File('${tempDir.path}/test.jpg');
      tempFile.writeAsBytesSync([0xFF, 0xD8, 0xFF, 0xE0]);

      final photo = Photo(
        photoId: 'photo-1',
        sessionId: 'sess-1',
        messageId: null,
        localPath: tempFile.path,
        cloudUrl: null,
        description: 'Tappable photo',
        timestamp: DateTime.now(),
        syncStatus: 'PENDING',
        width: null,
        height: null,
        fileSizeBytes: null,
        createdAt: DateTime.now(),
        updatedAt: DateTime.now(),
      );

      await tester.pumpWidget(buildApp(photos: [photo]));
      await tester.pump(const Duration(milliseconds: 100));

      // Tap the photo in the grid.
      await tester.tap(find.byType(GestureDetector).first);
      await tester.pumpAndSettle();

      // Should navigate to a new screen (PhotoViewer) with InteractiveViewer.
      expect(find.byType(InteractiveViewer), findsOneWidget);
    });
  });
}
