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
