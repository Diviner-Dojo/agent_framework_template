import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/services/google_calendar_service.dart';

void main() {
  group('GoogleCalendarService', () {
    group('createEvent', () {
      test('returns result on success', () async {
        final service = GoogleCalendarService(
          createEvent:
              ({
                required String title,
                required DateTime startTime,
                DateTime? endTime,
                String? description,
              }) async => const CalendarCreateResult(
                googleEventId: 'gcal-123',
                htmlLink: 'https://calendar.google.com/event/gcal-123',
              ),
          createReminder:
              ({
                required String title,
                required DateTime dateTime,
                String? description,
              }) async => throw UnimplementedError(),
        );

        final result = await service.createEvent(
          title: 'Team standup',
          startTime: DateTime.utc(2026, 3, 1, 14, 0),
          endTime: DateTime.utc(2026, 3, 1, 14, 30),
        );

        expect(result.googleEventId, 'gcal-123');
        expect(result.htmlLink, contains('gcal-123'));
      });

      test('passes all parameters to callable', () async {
        String? capturedTitle;
        DateTime? capturedStart;
        DateTime? capturedEnd;
        String? capturedDescription;

        final service = GoogleCalendarService(
          createEvent:
              ({
                required String title,
                required DateTime startTime,
                DateTime? endTime,
                String? description,
              }) async {
                capturedTitle = title;
                capturedStart = startTime;
                capturedEnd = endTime;
                capturedDescription = description;
                return const CalendarCreateResult(
                  googleEventId: 'gcal-abc',
                  htmlLink: null,
                );
              },
          createReminder:
              ({
                required String title,
                required DateTime dateTime,
                String? description,
              }) async => throw UnimplementedError(),
        );

        await service.createEvent(
          title: 'Doctor appointment',
          startTime: DateTime.utc(2026, 3, 1, 9, 0),
          endTime: DateTime.utc(2026, 3, 1, 10, 0),
          description: 'Annual checkup',
        );

        expect(capturedTitle, 'Doctor appointment');
        expect(capturedStart, DateTime.utc(2026, 3, 1, 9, 0));
        expect(capturedEnd, DateTime.utc(2026, 3, 1, 10, 0));
        expect(capturedDescription, 'Annual checkup');
      });

      test('propagates CalendarServiceException', () async {
        final service = GoogleCalendarService(
          createEvent:
              ({
                required String title,
                required DateTime startTime,
                DateTime? endTime,
                String? description,
              }) async => throw const CalendarServiceException(
                'API error 403: forbidden',
              ),
          createReminder:
              ({
                required String title,
                required DateTime dateTime,
                String? description,
              }) async => throw UnimplementedError(),
        );

        expect(
          () => service.createEvent(
            title: 'Test',
            startTime: DateTime.utc(2026, 3, 1),
          ),
          throwsA(isA<CalendarServiceException>()),
        );
      });

      test('works without endTime', () async {
        DateTime? capturedEnd;
        final service = GoogleCalendarService(
          createEvent:
              ({
                required String title,
                required DateTime startTime,
                DateTime? endTime,
                String? description,
              }) async {
                capturedEnd = endTime;
                return const CalendarCreateResult(
                  googleEventId: 'gcal-no-end',
                  htmlLink: null,
                );
              },
          createReminder:
              ({
                required String title,
                required DateTime dateTime,
                String? description,
              }) async => throw UnimplementedError(),
        );

        await service.createEvent(
          title: 'Quick chat',
          startTime: DateTime.utc(2026, 3, 1, 14, 0),
        );

        expect(capturedEnd, isNull);
      });
    });

    group('createReminder', () {
      test('returns result on success', () async {
        final service = GoogleCalendarService(
          createEvent:
              ({
                required String title,
                required DateTime startTime,
                DateTime? endTime,
                String? description,
              }) async => throw UnimplementedError(),
          createReminder:
              ({
                required String title,
                required DateTime dateTime,
                String? description,
              }) async => const CalendarCreateResult(
                googleEventId: 'gcal-reminder-1',
                htmlLink: null,
              ),
        );

        final result = await service.createReminder(
          title: 'Call Mom',
          dateTime: DateTime.utc(2026, 3, 1, 17, 0),
        );

        expect(result.googleEventId, 'gcal-reminder-1');
      });

      test('passes description through', () async {
        String? capturedDescription;
        final service = GoogleCalendarService(
          createEvent:
              ({
                required String title,
                required DateTime startTime,
                DateTime? endTime,
                String? description,
              }) async => throw UnimplementedError(),
          createReminder:
              ({
                required String title,
                required DateTime dateTime,
                String? description,
              }) async {
                capturedDescription = description;
                return const CalendarCreateResult(
                  googleEventId: 'gcal-r2',
                  htmlLink: null,
                );
              },
        );

        await service.createReminder(
          title: 'Pick up groceries',
          dateTime: DateTime.utc(2026, 3, 2, 18, 0),
          description: 'Milk, eggs, bread',
        );

        expect(capturedDescription, 'Milk, eggs, bread');
      });

      test('propagates CalendarServiceException', () async {
        final service = GoogleCalendarService(
          createEvent:
              ({
                required String title,
                required DateTime startTime,
                DateTime? endTime,
                String? description,
              }) async => throw UnimplementedError(),
          createReminder:
              ({
                required String title,
                required DateTime dateTime,
                String? description,
              }) async => throw const CalendarServiceException('API error 401'),
        );

        expect(
          () => service.createReminder(
            title: 'Test',
            dateTime: DateTime.utc(2026, 3, 1),
          ),
          throwsA(isA<CalendarServiceException>()),
        );
      });
    });
  });

  group('updateEvent', () {
    test('delegates to updateEvent callable', () async {
      String? capturedId;
      String? capturedTitle;
      DateTime? capturedStart;
      DateTime? capturedEnd;

      final service = GoogleCalendarService(
        createEvent:
            ({
              required String title,
              required DateTime startTime,
              DateTime? endTime,
              String? description,
            }) async => throw UnimplementedError(),
        createReminder:
            ({
              required String title,
              required DateTime dateTime,
              String? description,
            }) async => throw UnimplementedError(),
        updateEvent:
            ({
              required String googleEventId,
              String? title,
              DateTime? startTime,
              DateTime? endTime,
            }) async {
              capturedId = googleEventId;
              capturedTitle = title;
              capturedStart = startTime;
              capturedEnd = endTime;
            },
      );

      await service.updateEvent(
        googleEventId: 'evt-123',
        title: 'Updated standup',
        startTime: DateTime.utc(2026, 3, 3, 15, 0),
        endTime: DateTime.utc(2026, 3, 3, 15, 30),
      );

      expect(capturedId, 'evt-123');
      expect(capturedTitle, 'Updated standup');
      expect(capturedStart, DateTime.utc(2026, 3, 3, 15, 0));
      expect(capturedEnd, DateTime.utc(2026, 3, 3, 15, 30));
    });

    test('throws when updateEvent callable is null', () {
      final service = GoogleCalendarService(
        createEvent:
            ({
              required String title,
              required DateTime startTime,
              DateTime? endTime,
              String? description,
            }) async => throw UnimplementedError(),
        createReminder:
            ({
              required String title,
              required DateTime dateTime,
              String? description,
            }) async => throw UnimplementedError(),
      );

      expect(
        () => service.updateEvent(googleEventId: 'evt-1'),
        throwsA(isA<CalendarServiceException>()),
      );
    });

    test('propagates CalendarServiceException', () async {
      final service = GoogleCalendarService(
        createEvent:
            ({
              required String title,
              required DateTime startTime,
              DateTime? endTime,
              String? description,
            }) async => throw UnimplementedError(),
        createReminder:
            ({
              required String title,
              required DateTime dateTime,
              String? description,
            }) async => throw UnimplementedError(),
        updateEvent:
            ({
              required String googleEventId,
              String? title,
              DateTime? startTime,
              DateTime? endTime,
            }) async => throw const CalendarServiceException('Update failed'),
      );

      expect(
        () => service.updateEvent(googleEventId: 'evt-1'),
        throwsA(isA<CalendarServiceException>()),
      );
    });
  });

  group('listEvents', () {
    test('delegates to listEvents callable', () async {
      final service = GoogleCalendarService(
        createEvent:
            ({
              required String title,
              required DateTime startTime,
              DateTime? endTime,
              String? description,
            }) async => throw UnimplementedError(),
        createReminder:
            ({
              required String title,
              required DateTime dateTime,
              String? description,
            }) async => throw UnimplementedError(),
        listEvents:
            ({required DateTime timeMin, required DateTime timeMax}) async {
              return [
                CalendarEventSummary(
                  title: 'Meeting',
                  startTime: DateTime.utc(2026, 3, 3, 14, 0),
                  endTime: DateTime.utc(2026, 3, 3, 15, 0),
                ),
              ];
            },
      );

      final result = await service.listEvents(
        timeMin: DateTime.utc(2026, 3, 3),
        timeMax: DateTime.utc(2026, 3, 4),
      );

      expect(result, hasLength(1));
      expect(result.first.title, 'Meeting');
    });

    test('returns empty list when no events', () async {
      final service = GoogleCalendarService(
        createEvent:
            ({
              required String title,
              required DateTime startTime,
              DateTime? endTime,
              String? description,
            }) async => throw UnimplementedError(),
        createReminder:
            ({
              required String title,
              required DateTime dateTime,
              String? description,
            }) async => throw UnimplementedError(),
        listEvents:
            ({required DateTime timeMin, required DateTime timeMax}) async {
              return [];
            },
      );

      final result = await service.listEvents(
        timeMin: DateTime.utc(2026, 3, 3),
        timeMax: DateTime.utc(2026, 3, 4),
      );

      expect(result, isEmpty);
    });

    test('throws when listEvents callable is null', () {
      final service = GoogleCalendarService(
        createEvent:
            ({
              required String title,
              required DateTime startTime,
              DateTime? endTime,
              String? description,
            }) async => throw UnimplementedError(),
        createReminder:
            ({
              required String title,
              required DateTime dateTime,
              String? description,
            }) async => throw UnimplementedError(),
      );

      expect(
        () => service.listEvents(
          timeMin: DateTime.utc(2026, 3, 3),
          timeMax: DateTime.utc(2026, 3, 4),
        ),
        throwsA(isA<CalendarServiceException>()),
      );
    });
  });

  group('CalendarEventSummary', () {
    test('stores all fields', () {
      final summary = CalendarEventSummary(
        title: 'Team sync',
        startTime: DateTime.utc(2026, 3, 3, 14, 0),
        endTime: DateTime.utc(2026, 3, 3, 15, 0),
        isAllDay: false,
        location: 'Room 101',
      );
      expect(summary.title, 'Team sync');
      expect(summary.isAllDay, isFalse);
      expect(summary.location, 'Room 101');
    });

    test('defaults isAllDay to false', () {
      final summary = CalendarEventSummary(
        title: 'Quick call',
        startTime: DateTime.utc(2026, 3, 3, 10, 0),
      );
      expect(summary.isAllDay, isFalse);
      expect(summary.endTime, isNull);
      expect(summary.location, isNull);
    });
  });

  group('CalendarCreateResult', () {
    test('stores event ID and link', () {
      const result = CalendarCreateResult(
        googleEventId: 'abc-123',
        htmlLink: 'https://calendar.google.com/abc-123',
      );
      expect(result.googleEventId, 'abc-123');
      expect(result.htmlLink, 'https://calendar.google.com/abc-123');
    });

    test('htmlLink can be null', () {
      const result = CalendarCreateResult(
        googleEventId: 'abc-123',
        htmlLink: null,
      );
      expect(result.htmlLink, isNull);
    });
  });

  group('CalendarServiceException', () {
    test('toString includes message', () {
      const e = CalendarServiceException('test error');
      expect(e.toString(), contains('test error'));
    });
  });
}
