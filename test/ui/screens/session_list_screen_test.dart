// ===========================================================================
// file: test/ui/screens/session_list_screen_test.dart
// purpose: Widget tests for the session list (home) screen.
//
// Coverage targets:
//   - Empty state rendering
//   - FAB button presence
//   - AppBar actions: settings icon, progressive disclosure icons
//   - Session list with month grouping and session cards
//   - Phase 3C: Gift card (resurfacing) behaviour
//   - Phase 3D: Weekly digest card behaviour
// ===========================================================================

import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';
import 'package:agentic_journal/providers/calendar_providers.dart';
import 'package:agentic_journal/providers/photo_providers.dart';
import 'package:agentic_journal/providers/questionnaire_providers.dart';
import 'package:agentic_journal/providers/reminder_providers.dart';
import 'package:agentic_journal/providers/resurfacing_providers.dart';
import 'package:agentic_journal/providers/search_providers.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/providers/task_providers.dart';
import 'package:agentic_journal/providers/weekly_digest_providers.dart';
import 'package:agentic_journal/services/google_auth_service.dart';
import 'package:agentic_journal/services/resurfacing_service.dart';
import 'package:agentic_journal/services/weekly_digest_service.dart';
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
        dailyReminderVisibleProvider.overrideWith((ref) => false),
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

    group('gift card (Phase 3C)', () {
      late AppDatabase database;
      late SessionDao sessionDao;
      late SharedPreferences prefs;
      late ResurfacingService resurfacingService;

      setUp(() async {
        SharedPreferences.setMockInitialValues({});
        prefs = await SharedPreferences.getInstance();
        database = AppDatabase.forTesting(NativeDatabase.memory());
        sessionDao = SessionDao(database);
        resurfacingService = ResurfacingService(sessionDao, prefs);
      });

      tearDown(() async {
        await database.close();
      });

      /// A session 7 days ago that qualifies for resurfacing.
      JournalSession giftSession() => _makeSession(
        id: 'gift-1',
        startTime: DateTime.now().toUtc().subtract(const Duration(days: 7)),
        endTime: DateTime.now().toUtc().subtract(const Duration(days: 7)),
        summary: 'Had a wonderful morning walk.',
      );

      /// Build the screen with the gift card overrides applied.
      ///
      /// [sessionFn] is called each time [resurfacedSessionProvider] evaluates
      /// (including after invalidation). Pass a stateful closure to test the
      /// card-disappears-after-skip flow.
      Widget buildGiftScreen({required JournalSession? Function() sessionFn}) {
        final baseSession = _makeSession(
          id: 's1',
          startTime: DateTime.utc(2026, 2, 15),
          endTime: DateTime.utc(2026, 2, 15),
          summary: 'A session',
        );
        return ProviderScope(
          overrides: [
            paginatedSessionsProvider.overrideWith(
              (ref) => Stream.value([baseSession]),
            ),
            sessionCountProvider.overrideWith((ref) => Future.value(1)),
            taskCountProvider.overrideWith((ref) => Future.value(0)),
            photoCountProvider.overrideWith((ref) => Future.value(0)),
            pendingCalendarEventsCountProvider.overrideWith(
              (ref) => Future.value(0),
            ),
            checkInCountProvider.overrideWith((ref) => Stream.value(0)),
            // Suppress the Check-In CTA banner so only the gift card is visible.
            quickCheckInBannerDismissedProvider.overrideWith((ref) => true),
            resurfacingServiceProvider.overrideWithValue(resurfacingService),
            resurfacedSessionProvider.overrideWith((ref) async => sessionFn()),
            // Suppress the weekly digest card so it doesn't interfere.
            weeklyDigestProvider.overrideWith((ref) async => null),
            googleAuthServiceProvider.overrideWithValue(_fakeAuthService),
            isGoogleConnectedProvider.overrideWith(
              (ref) => GoogleConnectionNotifier(_fakeAuthService),
            ),
            dailyReminderVisibleProvider.overrideWith((ref) => false),
          ],
          child: MaterialApp(
            home: const SessionListScreen(),
            routes: {
              '/session': (context) => const Scaffold(body: Text('Session')),
              '/session/detail': (context) =>
                  const Scaffold(body: Text('Detail')),
              '/settings': (context) => const Scaffold(body: Text('Settings')),
              '/search': (context) => const Scaffold(body: Text('Search')),
              '/tasks': (context) => const Scaffold(body: Text('Tasks')),
              '/gallery': (context) => const Scaffold(body: Text('Gallery')),
            },
          ),
        );
      }

      testWidgets(
        'renders gift card with header and summary when session qualifies',
        (tester) async {
          final session = giftSession();
          await tester.pumpWidget(buildGiftScreen(sessionFn: () => session));
          await tester.pumpAndSettle();

          // Header label should appear.
          expect(find.textContaining('A moment from'), findsOneWidget);
          // Summary text should appear.
          expect(find.text('Had a wonderful morning walk.'), findsOneWidget);
          // Sparkle icon present.
          expect(find.byIcon(Icons.auto_awesome_outlined), findsOneWidget);
          // Reflect button present.
          expect(find.text('Reflect on this →'), findsOneWidget);
        },
      );

      testWidgets(
        'gift card absent when resurfacedSessionProvider returns null',
        (tester) async {
          await tester.pumpWidget(buildGiftScreen(sessionFn: () => null));
          await tester.pumpAndSettle();

          expect(find.textContaining('A moment from'), findsNothing);
          expect(find.text('Reflect on this →'), findsNothing);
        },
      );

      testWidgets('Reflect button navigates to session detail', (tester) async {
        final session = giftSession();
        await tester.pumpWidget(buildGiftScreen(sessionFn: () => session));
        await tester.pumpAndSettle();

        await tester.tap(find.text('Reflect on this →'));
        await tester.pumpAndSettle();

        expect(find.text('Detail'), findsOneWidget);
      });

      testWidgets('Skip button removes gift card after provider invalidation', (
        tester,
      ) async {
        // First evaluation returns the session (card shows); subsequent
        // evaluations return null (card hides after skip + invalidation).
        var calls = 0;
        final session = giftSession();

        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              paginatedSessionsProvider.overrideWith(
                (ref) => Stream.value([
                  _makeSession(
                    id: 's1',
                    startTime: DateTime.utc(2026, 2, 15),
                    endTime: DateTime.utc(2026, 2, 15),
                    summary: 'A session',
                  ),
                ]),
              ),
              sessionCountProvider.overrideWith((ref) => Future.value(1)),
              taskCountProvider.overrideWith((ref) => Future.value(0)),
              photoCountProvider.overrideWith((ref) => Future.value(0)),
              pendingCalendarEventsCountProvider.overrideWith(
                (ref) => Future.value(0),
              ),
              checkInCountProvider.overrideWith((ref) => Stream.value(0)),
              quickCheckInBannerDismissedProvider.overrideWith((ref) => true),
              resurfacingServiceProvider.overrideWithValue(resurfacingService),
              resurfacedSessionProvider.overrideWith((ref) async {
                calls++;
                // Return session only on first evaluation; null after skip
                // invalidates the provider.
                return calls <= 1 ? session : null;
              }),
              // Suppress the weekly digest card so it doesn't interfere.
              weeklyDigestProvider.overrideWith((ref) async => null),
              googleAuthServiceProvider.overrideWithValue(_fakeAuthService),
              isGoogleConnectedProvider.overrideWith(
                (ref) => GoogleConnectionNotifier(_fakeAuthService),
              ),
              dailyReminderVisibleProvider.overrideWith((ref) => false),
            ],
            child: MaterialApp(
              home: const SessionListScreen(),
              routes: {
                '/session': (context) => const Scaffold(body: Text('Session')),
                '/session/detail': (context) =>
                    const Scaffold(body: Text('Detail')),
                '/settings': (context) =>
                    const Scaffold(body: Text('Settings')),
                '/search': (context) => const Scaffold(body: Text('Search')),
                '/tasks': (context) => const Scaffold(body: Text('Tasks')),
                '/gallery': (context) => const Scaffold(body: Text('Gallery')),
              },
            ),
          ),
        );
        await tester.pumpAndSettle();

        // Gift card should be visible before skip.
        expect(find.textContaining('A moment from'), findsOneWidget);

        // Tap the skip button.
        await tester.tap(find.byTooltip('Never resurface this memory'));
        await tester.pumpAndSettle();

        // Gift card should be gone after skip + provider invalidation.
        expect(find.textContaining('A moment from'), findsNothing);
      });
    });

    group('weekly digest card (Phase 3D)', () {
      late AppDatabase digestDatabase;
      late SessionDao digestSessionDao;
      late SharedPreferences digestPrefs;
      late WeeklyDigestService weeklyDigestService;

      setUp(() async {
        SharedPreferences.setMockInitialValues({});
        digestPrefs = await SharedPreferences.getInstance();
        digestDatabase = AppDatabase.forTesting(NativeDatabase.memory());
        digestSessionDao = SessionDao(digestDatabase);
        weeklyDigestService = WeeklyDigestService(
          digestSessionDao,
          digestPrefs,
        );
      });

      tearDown(() async {
        await digestDatabase.close();
      });

      final baseDigestSession = _makeSession(
        id: 'd1',
        startTime: DateTime.utc(2026, 2, 15),
        endTime: DateTime.utc(2026, 2, 15),
        summary: 'A session',
      );

      Widget buildDigestScreen({required WeeklyDigest? Function() digestFn}) {
        return ProviderScope(
          overrides: [
            paginatedSessionsProvider.overrideWith(
              (ref) => Stream.value([baseDigestSession]),
            ),
            sessionCountProvider.overrideWith((ref) => Future.value(1)),
            taskCountProvider.overrideWith((ref) => Future.value(0)),
            photoCountProvider.overrideWith((ref) => Future.value(0)),
            pendingCalendarEventsCountProvider.overrideWith(
              (ref) => Future.value(0),
            ),
            checkInCountProvider.overrideWith((ref) => Stream.value(0)),
            quickCheckInBannerDismissedProvider.overrideWith((ref) => true),
            // Suppress the gift card so only the digest card is visible.
            resurfacedSessionProvider.overrideWith((ref) async => null),
            weeklyDigestServiceProvider.overrideWithValue(weeklyDigestService),
            weeklyDigestProvider.overrideWith((ref) async => digestFn()),
            googleAuthServiceProvider.overrideWithValue(_fakeAuthService),
            isGoogleConnectedProvider.overrideWith(
              (ref) => GoogleConnectionNotifier(_fakeAuthService),
            ),
            dailyReminderVisibleProvider.overrideWith((ref) => false),
          ],
          child: MaterialApp(
            home: const SessionListScreen(),
            routes: {
              '/session': (context) => const Scaffold(body: Text('Session')),
              '/session/detail': (context) =>
                  const Scaffold(body: Text('Detail')),
              '/settings': (context) => const Scaffold(body: Text('Settings')),
              '/search': (context) => const Scaffold(body: Text('Search')),
              '/tasks': (context) => const Scaffold(body: Text('Tasks')),
              '/gallery': (context) => const Scaffold(body: Text('Gallery')),
            },
          ),
        );
      }

      testWidgets(
        'renders digest card with headline when digest is available',
        (tester) async {
          final digest = WeeklyDigest(
            sessionCount: 3,
            highlightSession: _makeSession(
              id: 'h1',
              startTime: DateTime.now().toUtc().subtract(
                const Duration(days: 2),
              ),
              endTime: DateTime.now().toUtc().subtract(const Duration(days: 2)),
              summary: 'A highlight moment.',
            ),
          );
          await tester.pumpWidget(buildDigestScreen(digestFn: () => digest));
          await tester.pumpAndSettle();

          expect(
            find.textContaining('This week you captured 3 moments'),
            findsOneWidget,
          );
          expect(find.text('A highlight moment.'), findsOneWidget);
          expect(find.byIcon(Icons.star_outline), findsOneWidget);
        },
      );

      testWidgets('digest card absent when weeklyDigestProvider returns null', (
        tester,
      ) async {
        await tester.pumpWidget(buildDigestScreen(digestFn: () => null));
        await tester.pumpAndSettle();

        expect(find.textContaining('This week you captured'), findsNothing);
      });

      testWidgets('digest card shows singular "moment" for count of 1', (
        tester,
      ) async {
        final digest = WeeklyDigest(sessionCount: 1);
        await tester.pumpWidget(buildDigestScreen(digestFn: () => digest));
        await tester.pumpAndSettle();

        expect(
          find.textContaining('This week you captured 1 moment — nice.'),
          findsOneWidget,
        );
      });

      testWidgets(
        'dismiss button removes digest card after provider invalidation',
        (tester) async {
          var calls = 0;
          final digest = WeeklyDigest(sessionCount: 2);

          await tester.pumpWidget(
            ProviderScope(
              overrides: [
                paginatedSessionsProvider.overrideWith(
                  (ref) => Stream.value([baseDigestSession]),
                ),
                sessionCountProvider.overrideWith((ref) => Future.value(1)),
                taskCountProvider.overrideWith((ref) => Future.value(0)),
                photoCountProvider.overrideWith((ref) => Future.value(0)),
                pendingCalendarEventsCountProvider.overrideWith(
                  (ref) => Future.value(0),
                ),
                checkInCountProvider.overrideWith((ref) => Stream.value(0)),
                quickCheckInBannerDismissedProvider.overrideWith((ref) => true),
                resurfacedSessionProvider.overrideWith((ref) async => null),
                weeklyDigestServiceProvider.overrideWithValue(
                  weeklyDigestService,
                ),
                weeklyDigestProvider.overrideWith((ref) async {
                  calls++;
                  return calls <= 1 ? digest : null;
                }),
                googleAuthServiceProvider.overrideWithValue(_fakeAuthService),
                isGoogleConnectedProvider.overrideWith(
                  (ref) => GoogleConnectionNotifier(_fakeAuthService),
                ),
                dailyReminderVisibleProvider.overrideWith((ref) => false),
              ],
              child: MaterialApp(
                home: const SessionListScreen(),
                routes: {
                  '/session': (context) =>
                      const Scaffold(body: Text('Session')),
                  '/session/detail': (context) =>
                      const Scaffold(body: Text('Detail')),
                  '/settings': (context) =>
                      const Scaffold(body: Text('Settings')),
                  '/search': (context) => const Scaffold(body: Text('Search')),
                  '/tasks': (context) => const Scaffold(body: Text('Tasks')),
                  '/gallery': (context) =>
                      const Scaffold(body: Text('Gallery')),
                },
              ),
            ),
          );
          await tester.pumpAndSettle();

          // Digest card should be visible before dismiss.
          expect(
            find.textContaining('This week you captured 2 moments'),
            findsOneWidget,
          );

          // Tap the dismiss button.
          await tester.tap(find.byTooltip('Dismiss until next week'));
          await tester.pumpAndSettle();

          // Digest card should be gone after dismiss + provider invalidation.
          expect(find.textContaining('This week you captured'), findsNothing);
        },
      );
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
