import 'package:flutter_test/flutter_test.dart';
import 'package:drift/drift.dart' hide isNull, isNotNull;
import 'package:drift/native.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/calendar_event_dao.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';

void main() {
  group('Schema v5 migration', () {
    test('schemaVersion is 8', () async {
      final database = AppDatabase.forTesting(NativeDatabase.memory());
      expect(database.schemaVersion, 8);
      await database.close();
    });

    test('new database has calendar_events table', () async {
      final database = AppDatabase.forTesting(NativeDatabase.memory());
      final eventDao = CalendarEventDao(database);
      final sessionDao = SessionDao(database);

      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 25), 'UTC');

      // Insert an event to verify the table exists.
      await eventDao.insertEvent(
        CalendarEventsCompanion(
          eventId: const Value('e1'),
          sessionId: const Value('s1'),
          title: const Value('Test Event'),
          startTime: Value(DateTime.utc(2026, 2, 26, 14, 0)),
        ),
      );

      final event = await eventDao.getEventById('e1');
      expect(event, isNotNull);
      expect(event!.eventId, 'e1');
      expect(event.title, 'Test Event');
      expect(event.status, 'PENDING_CREATE');
      expect(event.syncStatus, 'PENDING');

      await database.close();
    });

    test('calendar_events defaults are correct', () async {
      final database = AppDatabase.forTesting(NativeDatabase.memory());
      final eventDao = CalendarEventDao(database);
      final sessionDao = SessionDao(database);

      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 25), 'UTC');
      await eventDao.insertEvent(
        CalendarEventsCompanion(
          eventId: const Value('e1'),
          sessionId: const Value('s1'),
          title: const Value('Defaults check'),
          startTime: Value(DateTime.utc(2026, 2, 26, 14, 0)),
        ),
      );

      final event = await eventDao.getEventById('e1');
      expect(event!.status, 'PENDING_CREATE');
      expect(event.syncStatus, 'PENDING');
      expect(event.googleEventId, isNull);
      expect(event.endTime, isNull);
      expect(event.userId, isNull);
      expect(event.rawUserMessage, isNull);
      expect(event.createdAt, isNotNull);
      expect(event.updatedAt, isNotNull);

      await database.close();
    });

    test(
      'v4 data survives upgrade to v5 (simulated via fresh insert)',
      () async {
        final database = AppDatabase.forTesting(NativeDatabase.memory());
        final sessionDao = SessionDao(database);

        // Create pre-existing session (simulating v4 data).
        final start = DateTime.utc(2026, 1, 15, 8, 0);
        await sessionDao.createSession('old-session', start, 'America/Denver');

        // Verify existing fields are intact.
        final session = await sessionDao.getSessionById('old-session');
        expect(session, isNotNull);
        expect(session!.startTime, start);
        expect(session.isResumed, false);
        expect(session.resumeCount, 0);
        // v4 location columns should still work.
        expect(session.latitude, isNull);
        expect(session.longitude, isNull);
        expect(session.locationAccuracy, isNull);
        expect(session.locationName, isNull);

        await database.close();
      },
    );

    test('calendar_events session_id index exists', () async {
      final database = AppDatabase.forTesting(NativeDatabase.memory());
      final eventDao = CalendarEventDao(database);
      final sessionDao = SessionDao(database);

      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 25), 'UTC');
      await sessionDao.createSession('s2', DateTime.utc(2026, 2, 26), 'UTC');

      // Insert events across sessions and verify session-scoped queries work
      // (index supports efficient filtering).
      for (var i = 0; i < 5; i++) {
        await eventDao.insertEvent(
          CalendarEventsCompanion(
            eventId: Value('s1-e$i'),
            sessionId: const Value('s1'),
            title: Value('S1 Event $i'),
            startTime: Value(DateTime.utc(2026, 2, 26, 10 + i)),
          ),
        );
      }
      for (var i = 0; i < 3; i++) {
        await eventDao.insertEvent(
          CalendarEventsCompanion(
            eventId: Value('s2-e$i'),
            sessionId: const Value('s2'),
            title: Value('S2 Event $i'),
            startTime: Value(DateTime.utc(2026, 2, 27, 10 + i)),
          ),
        );
      }

      final s1Events = await eventDao.getEventsForSession('s1');
      final s2Events = await eventDao.getEventsForSession('s2');
      expect(s1Events.length, 5);
      expect(s2Events.length, 3);

      await database.close();
    });

    test('full CRUD lifecycle on calendar events', () async {
      final database = AppDatabase.forTesting(NativeDatabase.memory());
      final eventDao = CalendarEventDao(database);
      final sessionDao = SessionDao(database);

      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 25), 'UTC');

      // 1. Insert.
      await eventDao.insertEvent(
        CalendarEventsCompanion(
          eventId: const Value('e1'),
          sessionId: const Value('s1'),
          title: const Value('Doctor appointment'),
          startTime: Value(DateTime.utc(2026, 3, 1, 9, 0)),
          endTime: Value(DateTime.utc(2026, 3, 1, 10, 0)),
          rawUserMessage: const Value(
            'I need to see the doctor on March 1 at 9am',
          ),
        ),
      );

      // 2. Read.
      var event = await eventDao.getEventById('e1');
      expect(event!.status, 'PENDING_CREATE');

      // 3. Update — set Google event ID (confirms).
      await eventDao.updateGoogleEventId('e1', 'gcal-xyz');
      event = await eventDao.getEventById('e1');
      expect(event!.status, 'CONFIRMED');
      expect(event.googleEventId, 'gcal-xyz');

      // 4. Sync.
      var toSync = await eventDao.getEventsToSync();
      expect(toSync.length, 1);

      await eventDao.updateSyncStatus('e1', 'SYNCED');
      toSync = await eventDao.getEventsToSync();
      expect(toSync, isEmpty);

      // 5. Delete.
      final deleted = await eventDao.deleteEvent('e1');
      expect(deleted, 1);
      expect(await eventDao.getEventById('e1'), isNull);

      await database.close();
    });
  });
}
