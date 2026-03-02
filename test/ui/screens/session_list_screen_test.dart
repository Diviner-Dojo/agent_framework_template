// ===========================================================================
// file: test/ui/screens/session_list_screen_test.dart
// purpose: Widget tests for the session list (home) screen.
//
// Coverage targets:
//   - Empty state rendering
//   - FAB button presence
//   - AppBar actions: settings icon, progressive disclosure icons
//   - Session list with month grouping and session cards
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
  }) {
    return ProviderScope(
      overrides: [
        paginatedSessionsProvider.overrideWith((ref) => Stream.value(sessions)),
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

  group('SessionListScreen', () {
    group('app bar', () {
      testWidgets('shows Agentic Journal title', (tester) async {
        await tester.pumpWidget(buildScreen());
        await tester.pumpAndSettle();
        expect(find.text('Agentic Journal'), findsOneWidget);
      });

      testWidgets('shows settings icon', (tester) async {
        await tester.pumpWidget(buildScreen());
        await tester.pumpAndSettle();
        expect(find.byIcon(Icons.settings), findsOneWidget);
      });

      testWidgets('settings icon navigates to settings', (tester) async {
        await tester.pumpWidget(buildScreen());
        await tester.pumpAndSettle();

        await tester.tap(find.byIcon(Icons.settings));
        await tester.pumpAndSettle();

        expect(find.text('Settings'), findsOneWidget);
      });
    });

    group('progressive disclosure icons', () {
      testWidgets('search icon hidden when < 5 sessions', (tester) async {
        await tester.pumpWidget(buildScreen(sessionCount: 3));
        await tester.pumpAndSettle();
        expect(find.byIcon(Icons.search), findsNothing);
      });

      testWidgets('search icon shown when >= 5 sessions', (tester) async {
        await tester.pumpWidget(buildScreen(sessionCount: 5));
        await tester.pumpAndSettle();
        expect(find.byIcon(Icons.search), findsOneWidget);
      });

      testWidgets('tasks icon hidden when 0 tasks', (tester) async {
        await tester.pumpWidget(buildScreen(taskCount: 0));
        await tester.pumpAndSettle();
        expect(find.byIcon(Icons.task_alt_outlined), findsNothing);
      });

      testWidgets('tasks icon shown when >= 1 task', (tester) async {
        await tester.pumpWidget(buildScreen(taskCount: 2));
        await tester.pumpAndSettle();
        expect(find.byIcon(Icons.task_alt_outlined), findsOneWidget);
      });

      testWidgets('gallery icon hidden when 0 photos', (tester) async {
        await tester.pumpWidget(buildScreen(photoCount: 0));
        await tester.pumpAndSettle();
        expect(find.byIcon(Icons.photo_library_outlined), findsNothing);
      });

      testWidgets('gallery icon shown when >= 1 photo', (tester) async {
        await tester.pumpWidget(buildScreen(photoCount: 3));
        await tester.pumpAndSettle();
        expect(find.byIcon(Icons.photo_library_outlined), findsOneWidget);
      });
    });

    group('empty state', () {
      testWidgets('shows empty state when no sessions', (tester) async {
        await tester.pumpWidget(buildScreen());
        await tester.pumpAndSettle();

        expect(find.text('No journal sessions yet'), findsOneWidget);
        expect(find.text('Tap + to start your first entry.'), findsOneWidget);
        expect(find.byIcon(Icons.book_outlined), findsOneWidget);
      });
    });

    group('FAB', () {
      testWidgets('shows add FAB', (tester) async {
        await tester.pumpWidget(buildScreen());
        await tester.pumpAndSettle();
        expect(find.byType(FloatingActionButton), findsOneWidget);
        expect(find.byIcon(Icons.add), findsOneWidget);
      });
    });

    group('session list', () {
      testWidgets('shows sessions grouped by month', (tester) async {
        await tester.pumpWidget(
          buildScreen(
            sessions: [
              _makeSession(
                id: 's1',
                startTime: DateTime.utc(2026, 2, 15, 10, 0),
                endTime: DateTime.utc(2026, 2, 15, 10, 30),
                summary: 'A great day',
              ),
              _makeSession(
                id: 's2',
                startTime: DateTime.utc(2026, 1, 10, 9, 0),
                endTime: DateTime.utc(2026, 1, 10, 9, 30),
                summary: 'A quiet evening',
              ),
            ],
          ),
        );
        await tester.pumpAndSettle();

        // Should show month-year headers.
        expect(find.text('February 2026'), findsOneWidget);
        expect(find.text('January 2026'), findsOneWidget);
      });

      testWidgets('shows session summary in card', (tester) async {
        await tester.pumpWidget(
          buildScreen(
            sessions: [
              _makeSession(
                id: 's1',
                startTime: DateTime.utc(2026, 2, 20, 14, 0),
                endTime: DateTime.utc(2026, 2, 20, 14, 30),
                summary: 'Had a great meeting today',
              ),
            ],
          ),
        );
        await tester.pumpAndSettle();

        expect(find.text('Had a great meeting today'), findsOneWidget);
      });

      testWidgets('shows load older entries when page is full', (tester) async {
        // Create 50+ sessions to fill the page.
        final sessions = List.generate(
          50,
          (i) => _makeSession(
            id: 's-$i',
            startTime: DateTime.utc(2026, 2, 28).subtract(Duration(days: i)),
            endTime: DateTime.utc(
              2026,
              2,
              28,
            ).subtract(Duration(days: i, hours: -1)),
            summary: 'Session $i',
          ),
        );

        await tester.pumpWidget(buildScreen(sessions: sessions));
        await tester.pumpAndSettle();

        // Scroll to bottom.
        await tester.scrollUntilVisible(
          find.text('Load older entries'),
          200,
          scrollable: find.byType(Scrollable).first,
        );
        await tester.pumpAndSettle();

        expect(find.text('Load older entries'), findsOneWidget);
      });
    });
  });
}
