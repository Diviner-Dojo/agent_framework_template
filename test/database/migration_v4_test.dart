import 'package:flutter_test/flutter_test.dart';
import 'package:drift/native.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';

void main() {
  group('Schema v4 migration', () {
    test('schemaVersion is 6', () async {
      final database = AppDatabase.forTesting(NativeDatabase.memory());
      expect(database.schemaVersion, 6);
      await database.close();
    });

    test('new database has location columns on sessions', () async {
      final database = AppDatabase.forTesting(NativeDatabase.memory());
      final sessionDao = SessionDao(database);

      final now = DateTime.utc(2026, 2, 25, 10, 0);
      await sessionDao.createSession('loc-session', now, 'UTC');

      // Verify location columns default to null.
      final session = await sessionDao.getSessionById('loc-session');
      expect(session, isNotNull);
      expect(session!.latitude, isNull);
      expect(session.longitude, isNull);
      expect(session.locationAccuracy, isNull);
      expect(session.locationName, isNull);

      await database.close();
    });

    test('updateSessionLocation writes all 4 location columns', () async {
      final database = AppDatabase.forTesting(NativeDatabase.memory());
      final sessionDao = SessionDao(database);

      final now = DateTime.utc(2026, 2, 25, 10, 0);
      await sessionDao.createSession('loc-session', now, 'UTC');

      final updated = await sessionDao.updateSessionLocation(
        'loc-session',
        latitude: 39.74,
        longitude: -104.99,
        locationAccuracy: 50.0,
        locationName: 'Denver, Colorado',
      );
      expect(updated, 1);

      final session = await sessionDao.getSessionById('loc-session');
      expect(session!.latitude, 39.74);
      expect(session.longitude, -104.99);
      expect(session.locationAccuracy, 50.0);
      expect(session.locationName, 'Denver, Colorado');
      // Sync status should be PENDING after location update.
      expect(session.syncStatus, 'PENDING');

      await database.close();
    });

    test('updateSessionLocation without optional fields', () async {
      final database = AppDatabase.forTesting(NativeDatabase.memory());
      final sessionDao = SessionDao(database);

      final now = DateTime.utc(2026, 2, 25, 10, 0);
      await sessionDao.createSession('loc-session', now, 'UTC');

      await sessionDao.updateSessionLocation(
        'loc-session',
        latitude: 39.74,
        longitude: -104.99,
      );

      final session = await sessionDao.getSessionById('loc-session');
      expect(session!.latitude, 39.74);
      expect(session.longitude, -104.99);
      expect(session.locationAccuracy, isNull);
      expect(session.locationName, isNull);

      await database.close();
    });

    test(
      'v3 data survives upgrade to v4 (simulated via fresh insert)',
      () async {
        final database = AppDatabase.forTesting(NativeDatabase.memory());
        final sessionDao = SessionDao(database);

        // Create pre-existing session (simulating v3 data).
        final start = DateTime.utc(2026, 1, 15, 8, 0);
        await sessionDao.createSession('old-session', start, 'America/Denver');

        // Verify existing fields are intact.
        final session = await sessionDao.getSessionById('old-session');
        expect(session, isNotNull);
        expect(session!.startTime, start);
        expect(session.isResumed, false);
        expect(session.resumeCount, 0);

        // New location columns should be null (not breaking existing data).
        expect(session.latitude, isNull);
        expect(session.longitude, isNull);
        expect(session.locationAccuracy, isNull);
        expect(session.locationName, isNull);

        await database.close();
      },
    );
  });
}
