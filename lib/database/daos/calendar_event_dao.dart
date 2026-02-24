// ===========================================================================
// file: lib/database/daos/calendar_event_dao.dart
// purpose: Data Access Object for CalendarEvents table (Phase 11 — ADR-0020).
//
// Pattern: Constructor-injected DAO (same as SessionDao, MessageDao,
//   PhotoDao). Receives the AppDatabase instance via constructor for
//   testability — tests pass an in-memory database.
//
// Lifecycle states (status column):
//   PENDING_CREATE → CONFIRMED (on successful Google API insert)
//   PENDING_CREATE → FAILED (on API error)
//   PENDING_CREATE → CANCELLED (user dismissed)
//
// Sync states (syncStatus column) — independent from lifecycle:
//   PENDING → SYNCED (on successful Supabase upsert)
//   PENDING → FAILED (on sync error)
//
// See: ADR-0020 §5 (Event Lifecycle State vs Sync State)
// ===========================================================================

import 'package:drift/drift.dart';

import '../app_database.dart';

/// Typed constants for the event lifecycle status column.
///
/// Using these instead of raw strings prevents typos from silently
/// corrupting state (security-specialist checkpoint, Task 6).
abstract final class EventStatus {
  static const pendingCreate = 'PENDING_CREATE';
  static const confirmed = 'CONFIRMED';
  static const failed = 'FAILED';
  static const cancelled = 'CANCELLED';
}

/// Typed constants for the cloud sync status column.
///
/// Independent from [EventStatus] — see ADR-0020 §5.
abstract final class EventSyncStatus {
  static const pending = 'PENDING';
  static const synced = 'SYNCED';
  static const failed = 'FAILED';
}

/// Data Access Object for calendar events.
///
/// Provides CRUD operations for the CalendarEvents table. All methods
/// are type-safe via drift's generated code.
class CalendarEventDao {
  final AppDatabase _db;

  /// Create a CalendarEventDao with the given database.
  CalendarEventDao(this._db);

  /// Insert a new calendar event.
  Future<void> insertEvent(CalendarEventsCompanion event) {
    return _db.into(_db.calendarEvents).insert(event);
  }

  /// Get a single event by ID.
  Future<CalendarEvent?> getEventById(String eventId) {
    return (_db.select(
      _db.calendarEvents,
    )..where((e) => e.eventId.equals(eventId))).getSingleOrNull();
  }

  /// Get all events for a session, ordered by creation time.
  Future<List<CalendarEvent>> getEventsForSession(String sessionId) {
    return (_db.select(_db.calendarEvents)
          ..where((e) => e.sessionId.equals(sessionId))
          ..orderBy([(e) => OrderingTerm.asc(e.createdAt)]))
        .get();
  }

  /// Watch all events for a session (reactive stream).
  Stream<List<CalendarEvent>> watchEventsForSession(String sessionId) {
    return (_db.select(_db.calendarEvents)
          ..where((e) => e.sessionId.equals(sessionId))
          ..orderBy([(e) => OrderingTerm.asc(e.createdAt)]))
        .watch();
  }

  /// Update the lifecycle status of an event.
  Future<int> updateStatus(String eventId, String status) {
    return (_db.update(
      _db.calendarEvents,
    )..where((e) => e.eventId.equals(eventId))).write(
      CalendarEventsCompanion(
        status: Value(status),
        updatedAt: Value(DateTime.now().toUtc()),
      ),
    );
  }

  /// Set the Google Calendar event ID after successful creation.
  Future<int> updateGoogleEventId(String eventId, String googleEventId) {
    return (_db.update(
      _db.calendarEvents,
    )..where((e) => e.eventId.equals(eventId))).write(
      CalendarEventsCompanion(
        googleEventId: Value(googleEventId),
        status: const Value(EventStatus.confirmed),
        updatedAt: Value(DateTime.now().toUtc()),
      ),
    );
  }

  /// Get all events with PENDING_CREATE status (awaiting user action).
  Future<List<CalendarEvent>> getPendingEvents() {
    return (_db.select(_db.calendarEvents)
          ..where((e) => e.status.equals(EventStatus.pendingCreate))
          ..orderBy([(e) => OrderingTerm.asc(e.createdAt)]))
        .get();
  }

  /// Get events that need cloud sync (CONFIRMED but not yet synced).
  Future<List<CalendarEvent>> getEventsToSync() {
    return (_db.select(_db.calendarEvents)..where(
          (e) =>
              e.status.equals(EventStatus.confirmed) &
              e.syncStatus.equals(EventSyncStatus.pending),
        ))
        .get();
  }

  /// Update cloud sync status.
  Future<int> updateSyncStatus(String eventId, String syncStatus) {
    return (_db.update(
      _db.calendarEvents,
    )..where((e) => e.eventId.equals(eventId))).write(
      CalendarEventsCompanion(
        syncStatus: Value(syncStatus),
        updatedAt: Value(DateTime.now().toUtc()),
      ),
    );
  }

  /// Delete a single event.
  Future<int> deleteEvent(String eventId) {
    return (_db.delete(
      _db.calendarEvents,
    )..where((e) => e.eventId.equals(eventId))).go();
  }

  /// Delete all events for a session (cascade delete support).
  Future<int> deleteEventsBySession(String sessionId) {
    return (_db.delete(
      _db.calendarEvents,
    )..where((e) => e.sessionId.equals(sessionId))).go();
  }

  /// Count pending events for a session (for queue cap check — ADR-0020 §7).
  Future<int> countPendingForSession(String sessionId) async {
    final count = _db.calendarEvents.eventId.count();
    final query = _db.selectOnly(_db.calendarEvents)
      ..addColumns([count])
      ..where(
        _db.calendarEvents.sessionId.equals(sessionId) &
            _db.calendarEvents.status.equals(EventStatus.pendingCreate),
      );
    final result = await query.getSingle();
    return result.read(count) ?? 0;
  }
}
