// coverage:ignore-file — migration paths require real versioned DB files; _openConnection uses path_provider.
// ===========================================================================
// file: lib/database/app_database.dart
// purpose: drift database class — single entry point for all local DB access.
//          Uses lazy initialization and includes migration strategy.
//
// Why drift? It provides type-safe SQL that feels familiar to SQL developers.
// Generated code (*.g.dart) is created by build_runner — run:
//   dart run build_runner build --delete-conflicting-outputs
//
// This file defines the database schema (which tables exist) and how to
// open/create the SQLite file on disk. The actual table definitions are
// in tables.dart.
// ===========================================================================

import 'dart:io';

import 'package:drift/drift.dart';
import 'package:drift/native.dart';
import 'package:path_provider/path_provider.dart';
import 'package:path/path.dart' as p;

import 'tables.dart';

// The "part" directive tells Dart that app_database.g.dart is part of this file.
// build_runner will generate that file with the _$AppDatabase base class.
part 'app_database.g.dart';

/// The main database class for the app.
///
/// This class is annotated with @DriftDatabase to tell the code generator
/// which tables to include. The generated _$AppDatabase base class provides
/// typed accessors for each table (e.g., this.journalSessions, this.journalMessages).
///
/// Usage:
///   final db = AppDatabase();          // production (file-based)
///   final db = AppDatabase.forTesting(NativeDatabase.memory());  // tests
@DriftDatabase(
  tables: [
    JournalSessions,
    JournalMessages,
    Photos,
    CalendarEvents,
    Videos,
    Tasks,
    QuestionnaireTemplates,
    QuestionnaireItems,
    CheckInResponses,
    CheckInAnswers,
  ],
)
class AppDatabase extends _$AppDatabase {
  /// Default constructor — uses a file-based SQLite database.
  /// The database file is created in the app's documents directory.
  AppDatabase() : super(_openConnection());

  /// Named constructor for testing — accepts any query executor.
  /// Pass NativeDatabase.memory() for an in-memory database that
  /// doesn't touch the filesystem.
  AppDatabase.forTesting(super.executor);

  /// Schema version — increment this whenever you change table definitions.
  /// When the version changes, the onUpgrade callback in MigrationStrategy
  /// handles migrating existing data to the new schema.
  @override
  int get schemaVersion => 10;

  @override
  MigrationStrategy get migration => MigrationStrategy(
    // onCreate runs when the database file is first created.
    // It creates all tables defined in the @DriftDatabase annotation.
    onCreate: (Migrator m) async {
      await m.createAll();
      // Index for paginated landing page (startTime DESC).
      // Also created in onUpgrade for v1→v2 upgrades.
      await m.createIndex(
        Index(
          'journal_sessions',
          'CREATE INDEX IF NOT EXISTS idx_sessions_start_time_desc '
              'ON journal_sessions (start_time DESC)',
        ),
      );
      // Index for efficient photo retrieval by session (Phase 9).
      await m.createIndex(
        Index(
          'photos',
          'CREATE INDEX IF NOT EXISTS idx_photos_session_id '
              'ON photos (session_id)',
        ),
      );
      // Index for efficient event retrieval by session (Phase 11).
      await m.createIndex(
        Index(
          'calendar_events',
          'CREATE INDEX IF NOT EXISTS idx_calendar_events_session_id '
              'ON calendar_events (session_id)',
        ),
      );
      // Index for efficient video retrieval by session (Phase 12).
      await m.createIndex(
        Index(
          'videos',
          'CREATE INDEX IF NOT EXISTS idx_videos_session_id '
              'ON videos (session_id)',
        ),
      );
      // Indexes for task queries (Phase 13).
      await m.createIndex(
        Index(
          'tasks',
          'CREATE INDEX IF NOT EXISTS idx_tasks_status '
              'ON tasks (status)',
        ),
      );
      await m.createIndex(
        Index(
          'tasks',
          'CREATE INDEX IF NOT EXISTS idx_tasks_due_date '
              'ON tasks (due_date)',
        ),
      );
      // Index for check-in response retrieval by session (Phase 1 ADHD — ADR-0032).
      await m.createIndex(
        Index(
          'check_in_responses',
          'CREATE INDEX IF NOT EXISTS idx_checkin_responses_session_id '
              'ON check_in_responses (session_id)',
        ),
      );
      // Index for check-in answer retrieval by response.
      await m.createIndex(
        Index(
          'check_in_answers',
          'CREATE INDEX IF NOT EXISTS idx_checkin_answers_response_id '
              'ON check_in_answers (response_id)',
        ),
      );
    },
    // onUpgrade handles schema changes between versions.
    onUpgrade: (Migrator m, int from, int to) async {
      if (from < 2) {
        // Phase 6: Add resume tracking columns (ADR-0014).
        await m.addColumn(journalSessions, journalSessions.isResumed);
        await m.addColumn(journalSessions, journalSessions.resumeCount);
        // Index for paginated landing page (startTime DESC).
        await m.createIndex(
          Index(
            'journal_sessions',
            'CREATE INDEX idx_sessions_start_time_desc '
                'ON journal_sessions (start_time DESC)',
          ),
        );
      }
      if (from < 3) {
        // Phase 9: Photo integration (ADR-0018).
        await m.createTable(photos);
        await m.addColumn(journalMessages, journalMessages.photoId);
        // Index for efficient photo retrieval by session.
        await m.createIndex(
          Index(
            'photos',
            'CREATE INDEX IF NOT EXISTS idx_photos_session_id '
                'ON photos (session_id)',
          ),
        );
      }
      if (from < 4) {
        // Phase 10: Location awareness (ADR-0019).
        await m.addColumn(journalSessions, journalSessions.latitude);
        await m.addColumn(journalSessions, journalSessions.longitude);
        await m.addColumn(journalSessions, journalSessions.locationAccuracy);
        await m.addColumn(journalSessions, journalSessions.locationName);
      }
      if (from < 5) {
        // Phase 11: Calendar events (ADR-0020).
        await m.createTable(calendarEvents);
        // Index for efficient event retrieval by session.
        await m.createIndex(
          Index(
            'calendar_events',
            'CREATE INDEX IF NOT EXISTS idx_calendar_events_session_id '
                'ON calendar_events (session_id)',
          ),
        );
      }
      if (from < 6) {
        // Phase 12: Video capture (ADR-0021).
        await m.createTable(videos);
        await m.addColumn(journalMessages, journalMessages.videoId);
        // Index for efficient video retrieval by session.
        await m.createIndex(
          Index(
            'videos',
            'CREATE INDEX IF NOT EXISTS idx_videos_session_id '
                'ON videos (session_id)',
          ),
        );
      }
      if (from < 7) {
        // E7: Raw audio preservation (ADR-0024).
        await m.addColumn(journalSessions, journalSessions.audioFilePath);
      }
      if (from < 8) {
        // E14: Journaling mode templates (ADR-0025).
        await m.addColumn(journalSessions, journalSessions.journalingMode);
      }
      if (from < 9) {
        // Phase 13: Tasks table.
        await m.createTable(tasks);
        await m.createIndex(
          Index(
            'tasks',
            'CREATE INDEX IF NOT EXISTS idx_tasks_status '
                'ON tasks (status)',
          ),
        );
        await m.createIndex(
          Index(
            'tasks',
            'CREATE INDEX IF NOT EXISTS idx_tasks_due_date '
                'ON tasks (due_date)',
          ),
        );
      }
      if (from < 10) {
        // ADHD Roadmap Phase 1: Pulse Check-In tables (ADR-0032).
        await m.createTable(questionnaireTemplates);
        await m.createTable(questionnaireItems);
        await m.createTable(checkInResponses);
        await m.createTable(checkInAnswers);
        // Index for retrieving responses by session.
        await m.createIndex(
          Index(
            'check_in_responses',
            'CREATE INDEX IF NOT EXISTS idx_checkin_responses_session_id '
                'ON check_in_responses (session_id)',
          ),
        );
        // Index for retrieving answers by response.
        await m.createIndex(
          Index(
            'check_in_answers',
            'CREATE INDEX IF NOT EXISTS idx_checkin_answers_response_id '
                'ON check_in_answers (response_id)',
          ),
        );
      }
    },
  );
}

/// Creates a lazily-opened connection to the SQLite database file.
///
/// LazyDatabase delays the actual file creation until the first query,
/// which avoids blocking app startup with I/O.
///
/// The database file is stored in the app's documents directory:
///   - Android: /data/data/com.divinerdojo.agentic_journal/files/
///   - iOS: NSDocumentDirectory
///
/// Note: This file is NOT encrypted in Phase 1. The AndroidManifest.xml
/// has android:allowBackup="false" to prevent extraction via backup.
/// SQLCipher encryption is planned for Phase 4 (see product brief).
LazyDatabase _openConnection() {
  return LazyDatabase(() async {
    final dbFolder = await getApplicationDocumentsDirectory();
    final file = File(p.join(dbFolder.path, 'agentic_journal.sqlite'));
    return NativeDatabase.createInBackground(file);
  });
}
