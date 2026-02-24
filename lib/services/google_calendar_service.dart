// ===========================================================================
// file: lib/services/google_calendar_service.dart
// purpose: Google Calendar API client for creating events and reminders.
//
// Pattern: Injectable callable (matches GoogleAuthService, LocationService).
//   Production code uses the real googleapis CalendarApi. Tests inject fakes
//   without touching platform channels.
//
// Scope: Create-only (events.insert). No read, update, or delete operations
//   in Phase 11. Events always go to the user's primary calendar.
//
// See: ADR-0020 §2 (Scope Minimization), §4 (Event Extraction Routing)
// ===========================================================================

import 'package:flutter/foundation.dart';
import 'package:googleapis/calendar/v3.dart' as gcal;
import 'package:googleapis_auth/googleapis_auth.dart' as googleapis_auth;

/// Result of a successful Google Calendar event creation.
class CalendarCreateResult {
  /// The Google Calendar event ID (e.g., "abc123xyz").
  final String googleEventId;

  /// The HTML link to the event in Google Calendar.
  final String? htmlLink;

  /// Create a [CalendarCreateResult].
  const CalendarCreateResult({
    required this.googleEventId,
    required this.htmlLink,
  });
}

/// Typed error for calendar API failures.
class CalendarServiceException implements Exception {
  final String message;
  const CalendarServiceException(this.message);

  @override
  String toString() => 'CalendarServiceException: $message';
}

/// Callback type for creating a Google Calendar event.
typedef CreateEventFn =
    Future<CalendarCreateResult> Function({
      required String title,
      required DateTime startTime,
      DateTime? endTime,
      String? description,
    });

/// Callback type for creating a reminder (timed event with notification).
typedef CreateReminderFn =
    Future<CalendarCreateResult> Function({
      required String title,
      required DateTime dateTime,
      String? description,
    });

/// Google Calendar API service for creating events and reminders.
///
/// Accepts an authenticated [googleapis_auth.AuthClient] from
/// [GoogleAuthService.getAuthClient()]. All operations target the user's
/// primary calendar.
///
/// Usage:
///   final authClient = await googleAuthService.getAuthClient();
///   final service = GoogleCalendarService(authClient: authClient!);
///   final result = await service.createEvent(
///     title: 'Team standup',
///     startTime: DateTime.utc(2026, 3, 1, 14, 0),
///     endTime: DateTime.utc(2026, 3, 1, 14, 30),
///   );
class GoogleCalendarService {
  final CreateEventFn _createEvent;
  final CreateReminderFn _createReminder;

  /// Create a GoogleCalendarService with injectable callables.
  ///
  /// For production, use [GoogleCalendarService.withClient] which builds
  /// the real implementation from an authenticated HTTP client.
  /// For tests, inject fake callables directly.
  GoogleCalendarService({
    required CreateEventFn createEvent,
    required CreateReminderFn createReminder,
  }) : _createEvent = createEvent,
       _createReminder = createReminder;

  /// Create a GoogleCalendarService backed by a real Google Calendar API client.
  ///
  /// [authClient] must be an authenticated HTTP client from
  /// [GoogleAuthService.getAuthClient()].
  /// [timezone] is the IANA timezone string (e.g., 'America/New_York') used
  /// for event start/end times. If null, falls back to the device's local
  /// timezone name via [DateTime.now().timeZoneName].
  factory GoogleCalendarService.withClient(
    googleapis_auth.AuthClient authClient, {
    String? timezone,
  }) {
    final calendarApi = gcal.CalendarApi(authClient);
    final tz = timezone ?? DateTime.now().timeZoneName;

    return GoogleCalendarService(
      createEvent:
          ({
            required String title,
            required DateTime startTime,
            DateTime? endTime,
            String? description,
          }) => _createEventImpl(
            calendarApi,
            title,
            startTime,
            endTime,
            description,
            tz,
          ),
      createReminder:
          ({
            required String title,
            required DateTime dateTime,
            String? description,
          }) => _createReminderImpl(
            calendarApi,
            title,
            dateTime,
            description,
            tz,
          ),
    );
  }

  /// Create a calendar event with a start and optional end time.
  ///
  /// Returns the Google Calendar event ID on success.
  /// Throws [CalendarServiceException] on API error.
  Future<CalendarCreateResult> createEvent({
    required String title,
    required DateTime startTime,
    DateTime? endTime,
    String? description,
  }) {
    return _createEvent(
      title: title,
      startTime: startTime,
      endTime: endTime,
      description: description,
    );
  }

  /// Create a reminder as a timed event with a 10-minute notification.
  ///
  /// Unlike [createEvent], a reminder always uses a single point-in-time
  /// with a popup notification. If no specific time is given, the caller
  /// should pass a morning time (e.g., 9:00 AM) as the default.
  ///
  /// Returns the Google Calendar event ID on success.
  /// Throws [CalendarServiceException] on API error.
  Future<CalendarCreateResult> createReminder({
    required String title,
    required DateTime dateTime,
    String? description,
  }) {
    return _createReminder(
      title: title,
      dateTime: dateTime,
      description: description,
    );
  }

  /// Real implementation for creating a calendar event.
  static Future<CalendarCreateResult> _createEventImpl(
    gcal.CalendarApi api,
    String title,
    DateTime startTime,
    DateTime? endTime,
    String? description,
    String timezone,
  ) async {
    // Default end time: 1 hour after start if not provided.
    final effectiveEnd = endTime ?? startTime.add(const Duration(hours: 1));

    final event = gcal.Event(
      summary: title,
      description: description,
      start: gcal.EventDateTime(
        dateTime: startTime.toUtc(),
        timeZone: timezone,
      ),
      end: gcal.EventDateTime(
        dateTime: effectiveEnd.toUtc(),
        timeZone: timezone,
      ),
    );

    try {
      final created = await api.events.insert(event, 'primary');
      final eventId = created.id;
      if (eventId == null || eventId.isEmpty) {
        throw const CalendarServiceException(
          'Google Calendar returned an event without an ID',
        );
      }
      return CalendarCreateResult(
        googleEventId: eventId,
        htmlLink: created.htmlLink,
      );
    } on gcal.DetailedApiRequestError catch (e) {
      if (kDebugMode) {
        debugPrint('Google Calendar API detail: ${e.message}');
      }
      throw CalendarServiceException(
        'Google Calendar API error (HTTP ${e.status})',
      );
    } on Exception catch (e) {
      if (kDebugMode) {
        debugPrint('GoogleCalendarService.createEvent failed: $e');
      }
      throw const CalendarServiceException('Failed to create calendar event');
    }
  }

  /// Real implementation for creating a reminder.
  static Future<CalendarCreateResult> _createReminderImpl(
    gcal.CalendarApi api,
    String title,
    DateTime dateTime,
    String? description,
    String timezone,
  ) async {
    // Reminders are 30-minute events with a 10-minute popup notification.
    final event = gcal.Event(
      summary: title,
      description: description,
      start: gcal.EventDateTime(dateTime: dateTime.toUtc(), timeZone: timezone),
      end: gcal.EventDateTime(
        dateTime: dateTime.add(const Duration(minutes: 30)).toUtc(),
        timeZone: timezone,
      ),
      reminders: gcal.EventReminders(
        useDefault: false,
        overrides: [gcal.EventReminder(method: 'popup', minutes: 10)],
      ),
    );

    try {
      final created = await api.events.insert(event, 'primary');
      final eventId = created.id;
      if (eventId == null || eventId.isEmpty) {
        throw const CalendarServiceException(
          'Google Calendar returned a reminder without an ID',
        );
      }
      return CalendarCreateResult(
        googleEventId: eventId,
        htmlLink: created.htmlLink,
      );
    } on gcal.DetailedApiRequestError catch (e) {
      if (kDebugMode) {
        debugPrint('Google Calendar API detail: ${e.message}');
      }
      throw CalendarServiceException(
        'Google Calendar API error (HTTP ${e.status})',
      );
    } on Exception catch (e) {
      if (kDebugMode) {
        debugPrint('GoogleCalendarService.createReminder failed: $e');
      }
      throw const CalendarServiceException('Failed to create reminder');
    }
  }
}
