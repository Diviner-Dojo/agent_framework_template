import 'package:flutter_test/flutter_test.dart';
import 'package:drift/native.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';

void main() {
  late AppDatabase database;
  late SessionDao sessionDao;

  setUp(() async {
    database = AppDatabase.forTesting(NativeDatabase.memory());
    sessionDao = SessionDao(database);
  });

  tearDown(() async {
    await database.close();
  });

  group('updateSessionLocation', () {
    test('writes all location fields and sets syncStatus to PENDING', () async {
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 25), 'UTC');

      // Mark as SYNCED first, then verify location update resets to PENDING.
      await sessionDao.updateSyncStatus(
        's1',
        'SYNCED',
        DateTime.utc(2026, 2, 25),
      );

      final updated = await sessionDao.updateSessionLocation(
        's1',
        latitude: 39.74,
        longitude: -104.99,
        locationAccuracy: 25.0,
        locationName: 'Denver, Colorado',
      );
      expect(updated, 1);

      final session = await sessionDao.getSessionById('s1');
      expect(session!.latitude, 39.74);
      expect(session.longitude, -104.99);
      expect(session.locationAccuracy, 25.0);
      expect(session.locationName, 'Denver, Colorado');
      expect(session.syncStatus, 'PENDING');
    });

    test('returns 0 for non-existent session', () async {
      final updated = await sessionDao.updateSessionLocation(
        'no-such-session',
        latitude: 0.0,
        longitude: 0.0,
      );
      expect(updated, 0);
    });

    test('handles negative coordinates', () async {
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 25), 'UTC');

      await sessionDao.updateSessionLocation(
        's1',
        latitude: -33.87,
        longitude: 151.21,
        locationName: 'Sydney, Australia',
      );

      final session = await sessionDao.getSessionById('s1');
      expect(session!.latitude, -33.87);
      expect(session.longitude, 151.21);
    });

    test('handles coordinates at boundary values', () async {
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 25), 'UTC');

      // Maximum latitude/longitude values.
      await sessionDao.updateSessionLocation(
        's1',
        latitude: 90.0,
        longitude: -180.0,
      );

      final session = await sessionDao.getSessionById('s1');
      expect(session!.latitude, 90.0);
      expect(session.longitude, -180.0);
    });

    test('overwrites previous location data', () async {
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 25), 'UTC');

      await sessionDao.updateSessionLocation(
        's1',
        latitude: 39.74,
        longitude: -104.99,
        locationName: 'Denver, Colorado',
      );

      // Overwrite with new location.
      await sessionDao.updateSessionLocation(
        's1',
        latitude: 40.71,
        longitude: -74.01,
        locationName: 'New York, New York',
      );

      final session = await sessionDao.getSessionById('s1');
      expect(session!.latitude, 40.71);
      expect(session.longitude, -74.01);
      expect(session.locationName, 'New York, New York');
    });
  });

  group('clearAllLocationData', () {
    test('nullifies location on sessions that have location data', () async {
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 25), 'UTC');
      await sessionDao.createSession('s2', DateTime.utc(2026, 2, 25, 1), 'UTC');

      await sessionDao.updateSessionLocation(
        's1',
        latitude: 39.74,
        longitude: -104.99,
        locationName: 'Denver, Colorado',
      );

      final cleared = await sessionDao.clearAllLocationData();
      expect(cleared, 1); // Only s1 had location data.

      final s1 = await sessionDao.getSessionById('s1');
      expect(s1!.latitude, isNull);
      expect(s1.longitude, isNull);
      expect(s1.locationAccuracy, isNull);
      expect(s1.locationName, isNull);
      expect(s1.syncStatus, 'PENDING');

      // s2 was not affected.
      final s2 = await sessionDao.getSessionById('s2');
      expect(s2!.latitude, isNull);
    });

    test('returns 0 when no sessions have location data', () async {
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 25), 'UTC');

      final cleared = await sessionDao.clearAllLocationData();
      expect(cleared, 0);
    });

    test('clears multiple sessions with location data', () async {
      for (int i = 1; i <= 3; i++) {
        await sessionDao.createSession(
          's$i',
          DateTime.utc(2026, 2, 25, i),
          'UTC',
        );
        await sessionDao.updateSessionLocation(
          's$i',
          latitude: 39.74 + i,
          longitude: -104.99 + i,
          locationName: 'City $i',
        );
      }

      final cleared = await sessionDao.clearAllLocationData();
      expect(cleared, 3);

      for (int i = 1; i <= 3; i++) {
        final session = await sessionDao.getSessionById('s$i');
        expect(session!.latitude, isNull);
        expect(session.longitude, isNull);
        expect(session.locationName, isNull);
      }
    });

    test('does not affect non-location fields', () async {
      await sessionDao.createSession(
        's1',
        DateTime.utc(2026, 2, 25),
        'America/Denver',
      );

      // End the session with a summary.
      await sessionDao.endSession(
        's1',
        DateTime.utc(2026, 2, 25, 1),
        summary: 'Had a great day',
      );

      // Add location.
      await sessionDao.updateSessionLocation(
        's1',
        latitude: 39.74,
        longitude: -104.99,
        locationName: 'Denver, Colorado',
      );

      // Clear location data.
      await sessionDao.clearAllLocationData();

      final session = await sessionDao.getSessionById('s1');
      expect(session!.summary, 'Had a great day');
      expect(session.timezone, 'America/Denver');
      expect(session.endTime, isNotNull);
      // Location columns should be nullified.
      expect(session.latitude, isNull);
      expect(session.locationName, isNull);
    });

    test(
      'sets syncStatus to PENDING on cleared sessions (for re-sync)',
      () async {
        await sessionDao.createSession('s1', DateTime.utc(2026, 2, 25), 'UTC');
        await sessionDao.updateSessionLocation(
          's1',
          latitude: 39.74,
          longitude: -104.99,
          locationName: 'Denver',
        );
        // Mark as synced.
        await sessionDao.updateSyncStatus(
          's1',
          'SYNCED',
          DateTime.utc(2026, 2, 25),
        );

        await sessionDao.clearAllLocationData();

        final session = await sessionDao.getSessionById('s1');
        expect(session!.syncStatus, 'PENDING');
      },
    );
  });
}
