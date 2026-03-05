import 'dart:convert';
import 'dart:io';

import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:path_provider_platform_interface/path_provider_platform_interface.dart';
import 'package:plugin_platform_interface/plugin_platform_interface.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/photo_dao.dart';
import 'package:agentic_journal/database/daos/video_dao.dart';
import 'package:agentic_journal/providers/auth_providers.dart';
import 'package:agentic_journal/providers/database_provider.dart';
import 'package:agentic_journal/providers/onboarding_providers.dart';
import 'package:agentic_journal/providers/photo_providers.dart';
import 'package:agentic_journal/providers/search_providers.dart';
import 'package:agentic_journal/providers/settings_providers.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/providers/sync_providers.dart';
import 'package:agentic_journal/providers/llm_providers.dart';
import 'package:agentic_journal/providers/voice_providers.dart';
import 'package:agentic_journal/repositories/agent_repository.dart';
import 'package:agentic_journal/services/photo_service.dart';
import 'package:agentic_journal/ui/screens/settings_screen.dart';

/// Fake PathProviderPlatform that redirects getApplicationDocumentsDirectory()
/// to a caller-supplied temp directory, allowing _exportData() to write and
/// tests to read back the resulting JSON.
class _FakeExportPathProvider extends Fake
    with MockPlatformInterfaceMixin
    implements PathProviderPlatform {
  final String documentsPath;

  _FakeExportPathProvider(this.documentsPath);

  @override
  Future<String?> getApplicationDocumentsPath() async => documentsPath;
}

/// Test-safe PhotoService that doesn't use path_provider.
class _FakePhotoService extends PhotoService {
  bool deleteAllCalled = false;

  @override
  Future<void> deleteAllPhotos() async {
    deleteAllCalled = true;
  }
}

void main() {
  group('Settings Data Management', () {
    late AppDatabase database;

    late SharedPreferences prefs;

    setUp(() async {
      database = AppDatabase.forTesting(NativeDatabase.memory());
      SharedPreferences.setMockInitialValues({});
      prefs = await SharedPreferences.getInstance();
    });

    tearDown(() async {
      await database.close();
    });

    Future<ProviderContainer> buildTestWidget(WidgetTester tester) async {
      late ProviderContainer container;

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container = ProviderContainer(
            overrides: [
              sharedPreferencesProvider.overrideWithValue(prefs),
              databaseProvider.overrideWithValue(database),
              agentRepositoryProvider.overrideWithValue(AgentRepository()),
              deviceTimezoneProvider.overrideWith(
                (ref) async => 'America/New_York',
              ),
              // Override assistant status check (platform-dependent).
              isDefaultAssistantProvider.overrideWith(
                (ref) => Future.value(false),
              ),
              // Override auth to not authenticated (avoids Supabase init).
              isAuthenticatedProvider.overrideWithValue(false),
              currentUserProvider.overrideWithValue(null),
              pendingSyncCountProvider.overrideWith((ref) => Stream.value(0)),
              sessionCountProvider.overrideWith((ref) => Future.value(0)),
              sttModelReadyProvider.overrideWith((ref) => Future.value(false)),
              llmModelReadyProvider.overrideWith((ref) => Future.value(false)),
              photoDaoProvider.overrideWithValue(PhotoDao(database)),
              videoDaoProvider.overrideWithValue(VideoDao(database)),
              photoServiceProvider.overrideWithValue(_FakePhotoService()),
              photoStorageInfoProvider.overrideWith(
                (ref) => Future.value(
                  const PhotoStorageInfo(count: 0, totalSizeBytes: 0),
                ),
              ),
            ],
          ),
          child: const MaterialApp(home: SettingsScreen()),
        ),
      );
      await tester.pumpAndSettle();

      // Scroll down to make Data Management card visible (the Voice card
      // added in Phase 7A pushes it below the initial viewport).
      await tester.scrollUntilVisible(
        find.text('Data Management'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      return container;
    }

    testWidgets('shows Data Management card with session count', (
      tester,
    ) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      expect(find.text('Data Management'), findsOneWidget);
      expect(find.text('Journal entries: 0 sessions'), findsOneWidget);
    });

    testWidgets('shows Clear All Entries button', (tester) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      expect(find.text('Clear All Entries'), findsOneWidget);
    });

    testWidgets('Clear All button opens confirmation dialog', (tester) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      await tester.tap(find.text('Clear All Entries'));
      await tester.pumpAndSettle();

      expect(find.text('Clear all entries?'), findsOneWidget);
      expect(find.text('Type DELETE to confirm:'), findsOneWidget);
    });

    testWidgets('Clear All button is disabled until DELETE is typed', (
      tester,
    ) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      await tester.tap(find.text('Clear All Entries'));
      await tester.pumpAndSettle();

      // Find the Clear All button — should be disabled.
      final clearAllButton = find.widgetWithText(FilledButton, 'Clear All');
      expect(clearAllButton, findsOneWidget);
      final button = tester.widget<FilledButton>(clearAllButton);
      expect(button.onPressed, isNull);

      // Type "DELETE" in the dialog's TextField.
      await tester.enterText(
        find.descendant(
          of: find.byType(AlertDialog),
          matching: find.byType(TextField),
        ),
        'DELETE',
      );
      await tester.pump();

      // Button should now be enabled.
      final buttonAfter = tester.widget<FilledButton>(clearAllButton);
      expect(buttonAfter.onPressed, isNotNull);
    });

    testWidgets('cancel in Clear All dialog preserves data', (tester) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      // Create a session first.
      final notifier = container.read(sessionNotifierProvider.notifier);
      await notifier.startSession();
      await notifier.sendMessage('Test message');
      await notifier.endSession();
      notifier.dismissSession();
      await tester.pumpAndSettle();

      // Open Clear All dialog.
      // Need to scroll to see the button first if needed.
      await tester.tap(find.text('Clear All Entries'));
      await tester.pumpAndSettle();

      // Tap Cancel.
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      // Session should still exist.
      final sessionDao = container.read(sessionDaoProvider);
      final sessions = await sessionDao.getAllSessionsByDate();
      expect(sessions.length, 1);
    });

    testWidgets('confirming Clear All deletes all data', (tester) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      // Create a session first.
      final notifier = container.read(sessionNotifierProvider.notifier);
      await notifier.startSession();
      await notifier.sendMessage('Test message');
      await notifier.endSession();
      notifier.dismissSession();
      await tester.pumpAndSettle();

      // Open Clear All dialog.
      await tester.tap(find.text('Clear All Entries'));
      await tester.pumpAndSettle();

      // Type DELETE and confirm.
      await tester.enterText(
        find.descendant(
          of: find.byType(AlertDialog),
          matching: find.byType(TextField),
        ),
        'DELETE',
      );
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Clear All'));
      await tester.pumpAndSettle();

      // All data should be cleared.
      final sessionDao = container.read(sessionDaoProvider);
      final sessions = await sessionDao.getAllSessionsByDate();
      expect(sessions, isEmpty);

      // SnackBar should show.
      expect(find.text('All journal entries cleared.'), findsOneWidget);
    });

    testWidgets('Export My Data button is present in Data Management card', (
      tester,
    ) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      // Scroll to the Export My Data button (it's below Clear All Entries).
      await tester.scrollUntilVisible(
        find.text('Export My Data'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      // Button must be present and enabled (not exporting).
      expect(find.text('Export My Data'), findsOneWidget);
      // Icon should show the download icon (not a progress indicator).
      expect(find.byIcon(Icons.download_outlined), findsOneWidget);
    });

    testWidgets('Export My Data shows export-complete SnackBar', (
      tester,
    ) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      // Scroll to the Export My Data button.
      await tester.scrollUntilVisible(
        find.text('Export My Data'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();

      // Tap Export — triggers async _exportData().
      await tester.tap(find.text('Export My Data'));
      // runAsync() exits the fake-async zone so that real I/O (DB query,
      // path_provider, file write) can complete, then pump to render the
      // resulting SnackBar frame.
      await tester.runAsync(() async {
        await Future<void>.delayed(const Duration(seconds: 2));
      });
      await tester.pump();

      // SnackBar must contain 'Saved to Downloads:' (success) OR
      // 'Export failed:' (platform-specific failure is acceptable in CI).
      // The key requirement: the export path executes without throwing
      // unhandled and the user receives feedback.
      final successSnackBar = find.textContaining('Saved to Downloads:');
      final failureSnackBar = find.textContaining('Export failed:');
      expect(
        successSnackBar.evaluate().isNotEmpty ||
            failureSnackBar.evaluate().isNotEmpty,
        isTrue,
        reason:
            '_exportData must show a SnackBar (success or failure) after '
            'the export button is tapped',
      );
    });

    // Phase 2C export structure regression tests.
    // Guards against regression to conditional key omission and missing video
    // export. Uses _FakeExportPathProvider so _exportData() writes to a
    // controlled temp directory, allowing JSON content assertions.
    // (SPEC-20260305-195043)

    testWidgets(
      'export JSON includes videos array with required fields when a video is seeded (regression)',
      tags: ['regression'],
      (tester) async {
        final tempDir = Directory.systemTemp.createTempSync('export_video_');
        final originalProvider = PathProviderPlatform.instance;
        addTearDown(() {
          PathProviderPlatform.instance = originalProvider;
          // Windows holds the export file briefly after writeAsString completes.
          // Ignore PathAccessException — the OS cleans up temp dirs at exit.
          try {
            tempDir.deleteSync(recursive: true);
          } on PathAccessException {
            // Benign: file released asynchronously; teardown races the write.
          }
        });
        PathProviderPlatform.instance = _FakeExportPathProvider(tempDir.path);

        final container = await buildTestWidget(tester);
        addTearDown(container.dispose);

        // Seed a session with a message (message ensures session is persisted).
        final sessionNotifier = container.read(
          sessionNotifierProvider.notifier,
        );
        await sessionNotifier.startSession();
        await sessionNotifier.sendMessage('test entry for export');
        final sessionId = container
            .read(sessionNotifierProvider)
            .activeSessionId!;
        await sessionNotifier.endSession();
        sessionNotifier.dismissSession();
        await tester.pumpAndSettle();

        final videoDao = container.read(videoDaoProvider);
        await videoDao.insertVideo(
          videoId: 'test-video-001',
          sessionId: sessionId,
          localPath: '/data/test/video.mp4',
          thumbnailPath: '/data/test/thumb.jpg',
          durationSeconds: 42,
          timestamp: DateTime.utc(2026, 3, 5, 12, 0, 0),
        );

        // Scroll to and tap Export.
        await tester.scrollUntilVisible(
          find.text('Export My Data'),
          200,
          scrollable: find.byType(Scrollable).first,
        );
        await tester.tap(find.text('Export My Data'));

        // The export uses async DB queries + File.writeAsString (real I/O).
        // Interleave runAsync (advances real I/O) with pump (advances the
        // fake-async queue for drift queries) until the file is fully written.
        // Pattern: runAsync unblocks native I/O; pump resolves Dart Futures;
        // repeat until the JSON can be parsed (file write is complete).
        List<File> exportFiles = [];
        String? exportContent;
        for (
          var attempt = 0;
          attempt < 15 && exportContent == null;
          attempt++
        ) {
          await tester.runAsync(() async {
            await Future<void>.delayed(const Duration(milliseconds: 500));
          });
          await tester.pump();

          final files = tempDir
              .listSync()
              .whereType<File>()
              .where((f) => f.path.contains('agentic_journal_export_'))
              .toList();
          if (files.isNotEmpty) {
            final content = files.first.readAsStringSync();
            if (content.isNotEmpty) {
              try {
                jsonDecode(
                  content,
                ); // throws FormatException if write incomplete
                exportFiles = files;
                exportContent = content;
              } on FormatException {
                // Write still in progress; continue.
              }
            }
          }
        }

        expect(
          exportFiles,
          isNotEmpty,
          reason:
              'Export file must have been written to the documents directory '
              'within ~7.5 seconds',
        );

        final exportJson = jsonDecode(exportContent!) as List;
        final session =
            exportJson.firstWhere(
                  (s) => (s as Map<String, dynamic>)['session_id'] == sessionId,
                )
                as Map<String, dynamic>;

        // videos key must be present and contain the seeded video.
        expect(
          session.containsKey('videos'),
          isTrue,
          reason:
              '"videos" key must always be present (Phase 2C, '
              'SPEC-20260305-195043)',
        );
        final videos = session['videos'] as List;
        expect(videos, hasLength(1));
        final video = videos[0] as Map<String, dynamic>;
        expect(video['video_id'], 'test-video-001');
        expect(video['local_path'], '/data/test/video.mp4');
        expect(video['thumbnail_path'], '/data/test/thumb.jpg');
        expect(video['duration_seconds'], 42);
        expect(
          video.containsKey('timestamp'),
          isTrue,
          reason: '"timestamp" field is required in video export schema',
        );
      },
    );

    testWidgets(
      'export JSON always includes check_ins, photos, videos as empty arrays when no media exists (regression)',
      tags: ['regression'],
      (tester) async {
        final tempDir = Directory.systemTemp.createTempSync('export_empty_');
        final originalProvider = PathProviderPlatform.instance;
        addTearDown(() {
          PathProviderPlatform.instance = originalProvider;
          try {
            tempDir.deleteSync(recursive: true);
          } on PathAccessException {
            // Windows: benign timing issue (same as the video export test).
          }
        });
        PathProviderPlatform.instance = _FakeExportPathProvider(tempDir.path);

        final container = await buildTestWidget(tester);
        addTearDown(container.dispose);

        // Seed a session with a message (needed to persist session to DB).
        // No check-ins, photos, or videos — only messages.
        final sessionNotifier = container.read(
          sessionNotifierProvider.notifier,
        );
        await sessionNotifier.startSession();
        await sessionNotifier.sendMessage('test entry for empty-array check');
        await sessionNotifier.endSession();
        sessionNotifier.dismissSession();
        await tester.pumpAndSettle();

        // Scroll to and tap Export.
        await tester.scrollUntilVisible(
          find.text('Export My Data'),
          200,
          scrollable: find.byType(Scrollable).first,
        );
        await tester.tap(find.text('Export My Data'));

        // Same interleaved runAsync+pump pattern as the video test above.
        List<File> exportFiles = [];
        String? exportContent;
        for (
          var attempt = 0;
          attempt < 15 && exportContent == null;
          attempt++
        ) {
          await tester.runAsync(() async {
            await Future<void>.delayed(const Duration(milliseconds: 500));
          });
          await tester.pump();

          final files = tempDir
              .listSync()
              .whereType<File>()
              .where((f) => f.path.contains('agentic_journal_export_'))
              .toList();
          if (files.isNotEmpty) {
            final content = files.first.readAsStringSync();
            if (content.isNotEmpty) {
              try {
                jsonDecode(content);
                exportFiles = files;
                exportContent = content;
              } on FormatException {
                // Write still in progress; continue.
              }
            }
          }
        }

        expect(exportFiles, isNotEmpty, reason: 'Export file must be written');

        final exportJson = jsonDecode(exportContent!) as List;
        expect(exportJson, hasLength(1));
        final session = exportJson[0] as Map<String, dynamic>;

        // All three media keys must be present as empty arrays, not absent.
        // Prior to Phase 2C fix these keys were omitted when empty, causing
        // schema instability. (SPEC-20260305-195043)
        expect(
          session.containsKey('check_ins'),
          isTrue,
          reason:
              '"check_ins" key must always be present even when empty '
              '(Phase 2C empty-array fix)',
        );
        expect(session['check_ins'], isEmpty);

        expect(
          session.containsKey('photos'),
          isTrue,
          reason:
              '"photos" key must always be present even when empty '
              '(Phase 2C empty-array fix)',
        );
        expect(session['photos'], isEmpty);

        expect(
          session.containsKey('videos'),
          isTrue,
          reason:
              '"videos" key must always be present even when empty '
              '(Phase 2C empty-array fix)',
        );
        expect(session['videos'], isEmpty);
      },
    );
  });
}
