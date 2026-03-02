// ===========================================================================
// file: test/ui/screens/session_list_screen_expanded_test.dart
// purpose: Expanded widget tests for the session list screen — covers
//          pending events banner, error state, navigation callbacks,
//          and icon progressive disclosure edge cases.
// ===========================================================================

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/providers/calendar_providers.dart';
import 'package:agentic_journal/providers/photo_providers.dart';
import 'package:agentic_journal/providers/search_providers.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/providers/task_providers.dart';
import 'package:agentic_journal/services/google_auth_service.dart';
import 'package:agentic_journal/ui/screens/session_list_screen.dart';

/// No-op auth service for test overrides.
final _fakeAuthService = GoogleAuthService(
  signIn: () async => null,
  signOut: () async => null,
  disconnect: () async => null,
  isSignedIn: () async => false,
  getAuthClient: () async => null,
  signInSilently: () async => null,
);

JournalSession _makeSession({
  required String id,
  required DateTime startTime,
  DateTime? endTime,
  String? summary,
}) {
  return JournalSession(
    sessionId: id,
    startTime: startTime,
    endTime: endTime,
    timezone: 'UTC',
    summary: summary,
    syncStatus: 'PENDING',
    isResumed: false,
    resumeCount: 0,
    createdAt: startTime,
    updatedAt: startTime,
  );
}

void main() {
  Widget buildScreen({
    List<JournalSession> sessions = const [],
    int sessionCount = 0,
    int taskCount = 0,
    int photoCount = 0,
    int pendingEventCount = 0,
    bool errorLoading = false,
  }) {
    return ProviderScope(
      overrides: [
        paginatedSessionsProvider.overrideWith(
          (ref) => errorLoading
              ? Stream.error(Exception('DB failure'))
              : Stream.value(sessions),
        ),
        sessionCountProvider.overrideWith((ref) => Future.value(sessionCount)),
        taskCountProvider.overrideWith((ref) => Future.value(taskCount)),
        photoCountProvider.overrideWith((ref) => Future.value(photoCount)),
        pendingCalendarEventsCountProvider.overrideWith(
          (ref) => Future.value(pendingEventCount),
        ),
        googleAuthServiceProvider.overrideWithValue(_fakeAuthService),
        isGoogleConnectedProvider.overrideWith(
          (ref) => GoogleConnectionNotifier(_fakeAuthService),
        ),
      ],
      child: MaterialApp(
        home: const SessionListScreen(),
        routes: {
          '/session': (context) => const Scaffold(body: Text('Session')),
          '/session/detail': (context) => const Scaffold(body: Text('Detail')),
          '/settings': (context) => const Scaffold(body: Text('Settings')),
          '/search': (context) => const Scaffold(body: Text('Search')),
          '/tasks': (context) => const Scaffold(body: Text('Tasks')),
          '/gallery': (context) => const Scaffold(body: Text('Gallery')),
        },
      ),
    );
  }

  group('SessionListScreen — pending events banner', () {
    testWidgets('shows pending events banner when count > 0', (tester) async {
      final sessions = [
        _makeSession(
          id: 's1',
          startTime: DateTime.utc(2026, 2, 15, 10, 0),
          endTime: DateTime.utc(2026, 2, 15, 10, 30),
          summary: 'Test session',
        ),
      ];
      await tester.pumpWidget(
        buildScreen(sessions: sessions, pendingEventCount: 3),
      );
      await tester.pumpAndSettle();

      expect(find.text('3 pending calendar events'), findsOneWidget);
      expect(find.text('Tap to connect Google Calendar'), findsOneWidget);
    });

    testWidgets('shows singular text for 1 pending event', (tester) async {
      final sessions = [
        _makeSession(
          id: 's1',
          startTime: DateTime.utc(2026, 2, 15, 10, 0),
          endTime: DateTime.utc(2026, 2, 15, 10, 30),
          summary: 'Test',
        ),
      ];
      await tester.pumpWidget(
        buildScreen(sessions: sessions, pendingEventCount: 1),
      );
      await tester.pumpAndSettle();

      expect(find.text('1 pending calendar event'), findsOneWidget);
    });

    testWidgets('hides banner when pending count is 0', (tester) async {
      final sessions = [
        _makeSession(
          id: 's1',
          startTime: DateTime.utc(2026, 2, 15, 10, 0),
          endTime: DateTime.utc(2026, 2, 15, 10, 30),
        ),
      ];
      await tester.pumpWidget(
        buildScreen(sessions: sessions, pendingEventCount: 0),
      );
      await tester.pumpAndSettle();

      expect(find.textContaining('pending calendar'), findsNothing);
    });
  });

  group('SessionListScreen — error state', () {
    testWidgets('shows error message when sessions fail to load', (
      tester,
    ) async {
      await tester.pumpWidget(buildScreen(errorLoading: true));
      await tester.pumpAndSettle();

      expect(find.textContaining('Error loading sessions'), findsOneWidget);
    });
  });

  group('SessionListScreen — navigation', () {
    testWidgets('search icon navigates to search', (tester) async {
      await tester.pumpWidget(buildScreen(sessionCount: 10));
      await tester.pumpAndSettle();

      await tester.tap(find.byIcon(Icons.search));
      await tester.pumpAndSettle();

      expect(find.text('Search'), findsOneWidget);
    });

    testWidgets('tasks icon navigates to tasks', (tester) async {
      await tester.pumpWidget(buildScreen(taskCount: 5));
      await tester.pumpAndSettle();

      await tester.tap(find.byIcon(Icons.task_alt_outlined));
      await tester.pumpAndSettle();

      expect(find.text('Tasks'), findsOneWidget);
    });

    testWidgets('gallery icon navigates to gallery', (tester) async {
      await tester.pumpWidget(buildScreen(photoCount: 3));
      await tester.pumpAndSettle();

      await tester.tap(find.byIcon(Icons.photo_library_outlined));
      await tester.pumpAndSettle();

      expect(find.text('Gallery'), findsOneWidget);
    });

    testWidgets('session card tap navigates to detail', (tester) async {
      final sessions = [
        _makeSession(
          id: 's1',
          startTime: DateTime.utc(2026, 2, 15, 10, 0),
          endTime: DateTime.utc(2026, 2, 15, 10, 30),
          summary: 'Tappable session',
        ),
      ];
      await tester.pumpWidget(buildScreen(sessions: sessions));
      await tester.pumpAndSettle();

      // Tap the session card.
      await tester.tap(find.text('Tappable session'));
      await tester.pumpAndSettle();

      expect(find.text('Detail'), findsOneWidget);
    });
  });

  group('SessionListScreen — bottom padding', () {
    testWidgets('shows bottom padding when sessions do not fill page', (
      tester,
    ) async {
      final sessions = [
        _makeSession(
          id: 's1',
          startTime: DateTime.utc(2026, 2, 15, 10, 0),
          summary: 'Only session',
        ),
      ];
      await tester.pumpWidget(buildScreen(sessions: sessions));
      await tester.pumpAndSettle();

      // Should NOT show "Load older entries".
      expect(find.text('Load older entries'), findsNothing);
    });
  });
}
