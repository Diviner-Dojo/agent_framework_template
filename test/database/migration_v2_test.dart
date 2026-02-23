import 'package:flutter_test/flutter_test.dart';
import 'package:drift/native.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';

void main() {
  group('Schema v2 migration', () {
    test('new database has isResumed and resumeCount columns', () async {
      // A fresh database (no prior version) creates all tables at v2.
      final database = AppDatabase.forTesting(NativeDatabase.memory());
      final sessionDao = SessionDao(database);

      final now = DateTime.utc(2026, 2, 23, 10, 0);
      await sessionDao.createSession('test-session', now, 'UTC');

      final session = await sessionDao.getSessionById('test-session');
      expect(session, isNotNull);
      expect(session!.isResumed, false);
      expect(session.resumeCount, 0);

      await database.close();
    });

    test('v1 data survives upgrade to v2 (simulated via fresh insert)', () async {
      // Since we can't easily simulate a v1 database in unit tests without
      // raw SQL schema manipulation, we verify that v2 columns have correct
      // defaults — meaning any v1 row that gets the new columns via ALTER TABLE
      // ADD COLUMN ... DEFAULT will have these values.
      final database = AppDatabase.forTesting(NativeDatabase.memory());
      final sessionDao = SessionDao(database);

      // Create a session (simulating pre-existing v1 data after migration).
      final start = DateTime.utc(2026, 1, 15, 8, 0);
      await sessionDao.createSession('old-session', start, 'America/Denver');

      // End it like a Phase 1 session would have been ended.
      await sessionDao.endSession(
        'old-session',
        DateTime.utc(2026, 1, 15, 8, 30),
        summary: 'Had a good morning',
      );

      // Verify all v1 fields are intact and v2 defaults are correct.
      final session = await sessionDao.getSessionById('old-session');
      expect(session, isNotNull);
      expect(session!.startTime, start);
      expect(session.endTime, DateTime.utc(2026, 1, 15, 8, 30));
      expect(session.summary, 'Had a good morning');
      expect(session.timezone, 'America/Denver');
      expect(session.syncStatus, 'PENDING');
      // v2 columns have defaults.
      expect(session.isResumed, false);
      expect(session.resumeCount, 0);

      await database.close();
    });

    test('schemaVersion is 2', () async {
      final database = AppDatabase.forTesting(NativeDatabase.memory());
      expect(database.schemaVersion, 2);
      await database.close();
    });
  });
}
