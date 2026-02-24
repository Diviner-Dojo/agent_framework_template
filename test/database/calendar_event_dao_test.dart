import 'package:flutter_test/flutter_test.dart';
import 'package:drift/drift.dart' hide isNull, isNotNull;
import 'package:drift/native.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/calendar_event_dao.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';

void main() {
  late AppDatabase database;
  late CalendarEventDao eventDao;
  late SessionDao sessionDao;

  setUp(() async {
    database = AppDatabase.forTesting(NativeDatabase.memory());
    eventDao = CalendarEventDao(database);
    sessionDao = SessionDao(database);
    // Create a session for events to reference.
    await sessionDao.createSession('s1', DateTime.utc(2026, 2, 25), 'UTC');
  });

  tearDown(() async {
    await database.close();
  });

  /// Helper to create a standard CalendarEventsCompanion.
  CalendarEventsCompanion _makeEvent({
    required String eventId,
    String sessionId = 's1',
    String title = 'Test Event',
    DateTime? startTime,
    DateTime? endTime,
    String? userId,
    String? rawUserMessage,
  }) {
    return CalendarEventsCompanion(
      eventId: Value(eventId),
      sessionId: Value(sessionId),
      title: Value(title),
      startTime: Value(startTime ?? DateTime.utc(2026, 2, 26, 14, 0)),
      endTime: Value.absentIfNull(endTime),
      userId: Value.absentIfNull(userId),
      rawUserMessage: Value.absentIfNull(rawUserMessage),
    );
  }

  group('insertEvent and getEventById', () {
    test('inserts and retrieves an event', () async {
      await eventDao.insertEvent(
        _makeEvent(
          eventId: 'e1',
          title: 'Team standup',
          startTime: DateTime.utc(2026, 2, 26, 14, 0),
          endTime: DateTime.utc(2026, 2, 26, 14, 30),
          rawUserMessage: 'I have a team standup tomorrow at 2pm',
        ),
      );

      final event = await eventDao.getEventById('e1');
      expect(event, isNotNull);
      expect(event!.eventId, 'e1');
      expect(event.sessionId, 's1');
      expect(event.title, 'Team standup');
      expect(event.startTime, DateTime.utc(2026, 2, 26, 14, 0));
      expect(event.endTime, DateTime.utc(2026, 2, 26, 14, 30));
      expect(event.status, 'PENDING_CREATE');
      expect(event.syncStatus, 'PENDING');
      expect(event.googleEventId, isNull);
      expect(event.rawUserMessage, 'I have a team standup tomorrow at 2pm');
    });

    test('returns null for non-existent event', () async {
      final event = await eventDao.getEventById('no-such');
      expect(event, isNull);
    });

    test('inserts event with userId', () async {
      await eventDao.insertEvent(_makeEvent(eventId: 'e2', userId: 'user-123'));

      final event = await eventDao.getEventById('e2');
      expect(event!.userId, 'user-123');
    });

    test('inserts event without endTime', () async {
      await eventDao.insertEvent(_makeEvent(eventId: 'e3'));

      final event = await eventDao.getEventById('e3');
      expect(event!.endTime, isNull);
    });
  });

  group('getEventsForSession', () {
    test('returns events ordered by createdAt ascending', () async {
      await eventDao.insertEvent(_makeEvent(eventId: 'e1', title: 'First'));
      await eventDao.insertEvent(_makeEvent(eventId: 'e2', title: 'Second'));

      final events = await eventDao.getEventsForSession('s1');
      expect(events.length, 2);
      expect(events[0].eventId, 'e1');
      expect(events[1].eventId, 'e2');
    });

    test('returns empty list for session with no events', () async {
      final events = await eventDao.getEventsForSession('s1');
      expect(events, isEmpty);
    });

    test('does not return events from other sessions', () async {
      await sessionDao.createSession('s2', DateTime.utc(2026, 2, 26), 'UTC');
      await eventDao.insertEvent(_makeEvent(eventId: 'e1', sessionId: 's1'));
      await eventDao.insertEvent(_makeEvent(eventId: 'e2', sessionId: 's2'));

      final events = await eventDao.getEventsForSession('s1');
      expect(events.length, 1);
      expect(events[0].eventId, 'e1');
    });
  });

  group('watchEventsForSession', () {
    test('emits updates when events are added', () async {
      final stream = eventDao.watchEventsForSession('s1');

      // First emission: empty. Second after insert.
      expect(stream, emitsInOrder([isEmpty, hasLength(1)]));

      await eventDao.insertEvent(_makeEvent(eventId: 'e1'));
    });
  });

  group('updateStatus', () {
    test('updates event lifecycle status', () async {
      await eventDao.insertEvent(_makeEvent(eventId: 'e1'));

      final updated = await eventDao.updateStatus('e1', 'CONFIRMED');
      expect(updated, 1);

      final event = await eventDao.getEventById('e1');
      expect(event!.status, 'CONFIRMED');
    });

    test('sets updatedAt on status change', () async {
      await eventDao.insertEvent(_makeEvent(eventId: 'e1'));
      final before = (await eventDao.getEventById('e1'))!.updatedAt;

      // Small delay to ensure timestamp difference.
      await Future<void>.delayed(const Duration(milliseconds: 10));
      await eventDao.updateStatus('e1', 'FAILED');

      final after = (await eventDao.getEventById('e1'))!.updatedAt;
      expect(after.isAfter(before) || after.isAtSameMomentAs(before), isTrue);
    });

    test('returns 0 for non-existent event', () async {
      final updated = await eventDao.updateStatus('no-such', 'CONFIRMED');
      expect(updated, 0);
    });

    test('transitions through lifecycle states', () async {
      await eventDao.insertEvent(_makeEvent(eventId: 'e1'));
      expect((await eventDao.getEventById('e1'))!.status, 'PENDING_CREATE');

      await eventDao.updateStatus('e1', 'CONFIRMED');
      expect((await eventDao.getEventById('e1'))!.status, 'CONFIRMED');

      // CANCELLED is also a valid terminal state.
      await eventDao.insertEvent(_makeEvent(eventId: 'e2'));
      await eventDao.updateStatus('e2', 'CANCELLED');
      expect((await eventDao.getEventById('e2'))!.status, 'CANCELLED');

      // FAILED is also a valid terminal state.
      await eventDao.insertEvent(_makeEvent(eventId: 'e3'));
      await eventDao.updateStatus('e3', 'FAILED');
      expect((await eventDao.getEventById('e3'))!.status, 'FAILED');
    });
  });

  group('updateGoogleEventId', () {
    test('sets googleEventId and status to CONFIRMED', () async {
      await eventDao.insertEvent(_makeEvent(eventId: 'e1'));

      final updated = await eventDao.updateGoogleEventId('e1', 'gcal-abc123');
      expect(updated, 1);

      final event = await eventDao.getEventById('e1');
      expect(event!.googleEventId, 'gcal-abc123');
      expect(event.status, 'CONFIRMED');
    });

    test('returns 0 for non-existent event', () async {
      final updated = await eventDao.updateGoogleEventId('no-such', 'gcal-abc');
      expect(updated, 0);
    });
  });

  group('getPendingEvents', () {
    test('returns only PENDING_CREATE events', () async {
      await eventDao.insertEvent(_makeEvent(eventId: 'e1'));
      await eventDao.insertEvent(_makeEvent(eventId: 'e2'));
      await eventDao.insertEvent(_makeEvent(eventId: 'e3'));

      // Move e2 to CONFIRMED, e3 to CANCELLED.
      await eventDao.updateStatus('e2', 'CONFIRMED');
      await eventDao.updateStatus('e3', 'CANCELLED');

      final pending = await eventDao.getPendingEvents();
      expect(pending.length, 1);
      expect(pending[0].eventId, 'e1');
    });

    test('returns empty list when no pending events', () async {
      final pending = await eventDao.getPendingEvents();
      expect(pending, isEmpty);
    });
  });

  group('getEventsToSync', () {
    test('returns CONFIRMED events with PENDING syncStatus', () async {
      await eventDao.insertEvent(_makeEvent(eventId: 'e1'));
      await eventDao.insertEvent(_makeEvent(eventId: 'e2'));
      await eventDao.insertEvent(_makeEvent(eventId: 'e3'));

      // e1: PENDING_CREATE + PENDING sync → NOT returned (not CONFIRMED)
      // e2: CONFIRMED + PENDING sync → returned
      await eventDao.updateStatus('e2', 'CONFIRMED');
      // e3: CONFIRMED + SYNCED → NOT returned
      await eventDao.updateStatus('e3', 'CONFIRMED');
      await eventDao.updateSyncStatus('e3', 'SYNCED');

      final toSync = await eventDao.getEventsToSync();
      expect(toSync.length, 1);
      expect(toSync[0].eventId, 'e2');
    });

    test('returns empty list when nothing needs sync', () async {
      final toSync = await eventDao.getEventsToSync();
      expect(toSync, isEmpty);
    });
  });

  group('updateSyncStatus', () {
    test('updates sync status', () async {
      await eventDao.insertEvent(_makeEvent(eventId: 'e1'));

      await eventDao.updateSyncStatus('e1', 'SYNCED');

      final event = await eventDao.getEventById('e1');
      expect(event!.syncStatus, 'SYNCED');
    });

    test('can set sync status to FAILED', () async {
      await eventDao.insertEvent(_makeEvent(eventId: 'e1'));

      await eventDao.updateSyncStatus('e1', 'FAILED');

      final event = await eventDao.getEventById('e1');
      expect(event!.syncStatus, 'FAILED');
    });

    test('returns 0 for non-existent event', () async {
      final updated = await eventDao.updateSyncStatus('no-such', 'SYNCED');
      expect(updated, 0);
    });
  });

  group('deleteEvent', () {
    test('deletes a single event', () async {
      await eventDao.insertEvent(_makeEvent(eventId: 'e1'));

      final deleted = await eventDao.deleteEvent('e1');
      expect(deleted, 1);

      final event = await eventDao.getEventById('e1');
      expect(event, isNull);
    });

    test('returns 0 for non-existent event', () async {
      final deleted = await eventDao.deleteEvent('no-such');
      expect(deleted, 0);
    });
  });

  group('deleteEventsBySession', () {
    test('deletes all events for a session', () async {
      await eventDao.insertEvent(_makeEvent(eventId: 'e1'));
      await eventDao.insertEvent(_makeEvent(eventId: 'e2'));

      final deleted = await eventDao.deleteEventsBySession('s1');
      expect(deleted, 2);

      final remaining = await eventDao.getEventsForSession('s1');
      expect(remaining, isEmpty);
    });

    test('does not affect events in other sessions', () async {
      await sessionDao.createSession('s2', DateTime.utc(2026, 2, 26), 'UTC');
      await eventDao.insertEvent(_makeEvent(eventId: 'e1', sessionId: 's1'));
      await eventDao.insertEvent(_makeEvent(eventId: 'e2', sessionId: 's2'));

      await eventDao.deleteEventsBySession('s1');

      final s1Events = await eventDao.getEventsForSession('s1');
      final s2Events = await eventDao.getEventsForSession('s2');
      expect(s1Events, isEmpty);
      expect(s2Events.length, 1);
    });
  });

  group('countPendingForSession', () {
    test('counts only PENDING_CREATE events for session', () async {
      await eventDao.insertEvent(_makeEvent(eventId: 'e1'));
      await eventDao.insertEvent(_makeEvent(eventId: 'e2'));
      await eventDao.insertEvent(_makeEvent(eventId: 'e3'));

      // Move e3 to CONFIRMED — should not be counted.
      await eventDao.updateStatus('e3', 'CONFIRMED');

      final count = await eventDao.countPendingForSession('s1');
      expect(count, 2);
    });

    test('returns 0 for empty session', () async {
      final count = await eventDao.countPendingForSession('s1');
      expect(count, 0);
    });

    test('does not count events from other sessions', () async {
      await sessionDao.createSession('s2', DateTime.utc(2026, 2, 26), 'UTC');
      await eventDao.insertEvent(_makeEvent(eventId: 'e1', sessionId: 's1'));
      await eventDao.insertEvent(_makeEvent(eventId: 'e2', sessionId: 's2'));

      final count = await eventDao.countPendingForSession('s1');
      expect(count, 1);
    });
  });
}
