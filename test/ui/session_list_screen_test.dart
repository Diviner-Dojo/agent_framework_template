import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/providers/photo_providers.dart';
import 'package:agentic_journal/providers/search_providers.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/ui/screens/session_list_screen.dart';

void main() {
  group('SessionListScreen', () {
    testWidgets('shows empty state placeholder text', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            // Override with an empty stream.
            paginatedSessionsProvider.overrideWith(
              (ref) => Stream.value(<JournalSession>[]),
            ),
            photoCountProvider.overrideWith((ref) => Future.value(0)),
          ],
          child: const MaterialApp(home: SessionListScreen()),
        ),
      );

      // Wait for the stream to emit.
      await tester.pumpAndSettle();

      expect(find.text('No journal sessions yet'), findsOneWidget);
    });

    testWidgets('has a floating action button', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            paginatedSessionsProvider.overrideWith(
              (ref) => Stream.value(<JournalSession>[]),
            ),
          ],
          child: const MaterialApp(home: SessionListScreen()),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.byType(FloatingActionButton), findsOneWidget);
    });

    testWidgets('FAB shows add icon by default', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            paginatedSessionsProvider.overrideWith(
              (ref) => Stream.value(<JournalSession>[]),
            ),
          ],
          child: const MaterialApp(home: SessionListScreen()),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.add), findsOneWidget);
    });

    testWidgets('gallery icon hidden when no photos', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            paginatedSessionsProvider.overrideWith(
              (ref) => Stream.value(<JournalSession>[]),
            ),
            photoCountProvider.overrideWith((ref) => Future.value(0)),
          ],
          child: const MaterialApp(home: SessionListScreen()),
        ),
      );

      await tester.pumpAndSettle();

      // Gallery icon should NOT appear when photo count is 0.
      expect(find.byIcon(Icons.photo_library_outlined), findsNothing);
    });

    testWidgets('gallery icon visible when photos exist', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            paginatedSessionsProvider.overrideWith(
              (ref) => Stream.value(<JournalSession>[]),
            ),
            photoCountProvider.overrideWith((ref) => Future.value(5)),
          ],
          child: MaterialApp(
            home: const SessionListScreen(),
            routes: {'/gallery': (context) => const Scaffold()},
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Gallery icon should appear when photo count > 0.
      expect(find.byIcon(Icons.photo_library_outlined), findsOneWidget);
    });

    testWidgets('tapping gallery icon navigates to /gallery', (tester) async {
      var navigated = false;
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            paginatedSessionsProvider.overrideWith(
              (ref) => Stream.value(<JournalSession>[]),
            ),
            photoCountProvider.overrideWith((ref) => Future.value(3)),
          ],
          child: MaterialApp(
            home: const SessionListScreen(),
            routes: {
              '/gallery': (context) {
                navigated = true;
                return const Scaffold(body: Text('Gallery'));
              },
            },
          ),
        ),
      );

      await tester.pumpAndSettle();

      await tester.tap(find.byIcon(Icons.photo_library_outlined));
      await tester.pumpAndSettle();

      expect(navigated, true);
    });

    testWidgets('shows error state when session stream errors', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            paginatedSessionsProvider.overrideWith(
              (ref) => Stream<List<JournalSession>>.error('DB error'),
            ),
            photoCountProvider.overrideWith((ref) => Future.value(0)),
          ],
          child: const MaterialApp(home: SessionListScreen()),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.textContaining('Error loading sessions'), findsOneWidget);
    });

    testWidgets('search icon hidden when fewer than 5 sessions', (
      tester,
    ) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            paginatedSessionsProvider.overrideWith(
              (ref) => Stream.value(<JournalSession>[]),
            ),
            photoCountProvider.overrideWith((ref) => Future.value(0)),
            sessionCountProvider.overrideWith((ref) => Future.value(3)),
          ],
          child: const MaterialApp(home: SessionListScreen()),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.search), findsNothing);
    });

    testWidgets('search icon visible at 5+ sessions', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            paginatedSessionsProvider.overrideWith(
              (ref) => Stream.value(<JournalSession>[]),
            ),
            photoCountProvider.overrideWith((ref) => Future.value(0)),
            sessionCountProvider.overrideWith((ref) => Future.value(10)),
          ],
          child: MaterialApp(
            home: const SessionListScreen(),
            routes: {'/search': (context) => const Scaffold()},
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.search), findsOneWidget);
    });

    testWidgets('shows loading indicator when stream has no data yet', (
      tester,
    ) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            paginatedSessionsProvider.overrideWith(
              (ref) => const Stream<List<JournalSession>>.empty(),
            ),
            photoCountProvider.overrideWith((ref) => Future.value(0)),
          ],
          child: const MaterialApp(home: SessionListScreen()),
        ),
      );

      // Don't pump and settle — stay in loading state.
      await tester.pump();

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('renders session cards when sessions exist', (tester) async {
      final now = DateTime.utc(2026, 2, 19, 10, 0);
      final sessions = [
        JournalSession(
          sessionId: 's1',
          startTime: now,
          timezone: 'UTC',
          syncStatus: 'PENDING',
          isResumed: false,
          resumeCount: 0,
          createdAt: now,
          updatedAt: now,
        ),
        JournalSession(
          sessionId: 's2',
          startTime: now.subtract(const Duration(days: 1)),
          timezone: 'UTC',
          syncStatus: 'PENDING',
          isResumed: false,
          resumeCount: 0,
          createdAt: now,
          updatedAt: now,
          summary: 'Had a good day',
        ),
      ];

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            paginatedSessionsProvider.overrideWith(
              (ref) => Stream.value(sessions),
            ),
            photoCountProvider.overrideWith((ref) => Future.value(0)),
          ],
          child: const MaterialApp(home: SessionListScreen()),
        ),
      );

      await tester.pumpAndSettle();

      // Should not show empty state.
      expect(find.text('No journal sessions yet'), findsNothing);

      // Should show session data. The summary text should appear.
      expect(find.text('Had a good day'), findsOneWidget);
    });

    testWidgets('tapping session card navigates to detail', (tester) async {
      final now = DateTime.utc(2026, 2, 19, 10, 0);
      final sessions = [
        JournalSession(
          sessionId: 's1',
          startTime: now,
          timezone: 'UTC',
          syncStatus: 'PENDING',
          isResumed: false,
          resumeCount: 0,
          createdAt: now,
          updatedAt: now,
          summary: 'Tap me',
        ),
      ];

      var navigatedSessionId = '';
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            paginatedSessionsProvider.overrideWith(
              (ref) => Stream.value(sessions),
            ),
            photoCountProvider.overrideWith((ref) => Future.value(0)),
          ],
          child: MaterialApp(
            home: const SessionListScreen(),
            onGenerateRoute: (settings) {
              if (settings.name == '/session/detail') {
                navigatedSessionId = settings.arguments as String;
                return MaterialPageRoute(
                  builder: (_) => const Scaffold(body: Text('Detail')),
                );
              }
              return null;
            },
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Tap the session card.
      await tester.tap(find.text('Tap me'));
      await tester.pumpAndSettle();

      expect(navigatedSessionId, 's1');
    });

    testWidgets('shows Load older entries when page is full', (tester) async {
      final now = DateTime.utc(2026, 2, 19, 10, 0);
      final sessions = [
        JournalSession(
          sessionId: 's1',
          startTime: now,
          timezone: 'UTC',
          syncStatus: 'PENDING',
          isResumed: false,
          resumeCount: 0,
          createdAt: now,
          updatedAt: now,
        ),
        JournalSession(
          sessionId: 's2',
          startTime: now.subtract(const Duration(days: 1)),
          timezone: 'UTC',
          syncStatus: 'PENDING',
          isResumed: false,
          resumeCount: 0,
          createdAt: now,
          updatedAt: now,
        ),
      ];

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            paginatedSessionsProvider.overrideWith(
              (ref) => Stream.value(sessions),
            ),
            photoCountProvider.overrideWith((ref) => Future.value(0)),
            // Set page size to 2 so 2 sessions triggers "Load older".
            sessionPageSizeProvider.overrideWith((ref) => 2),
          ],
          child: const MaterialApp(home: SessionListScreen()),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('Load older entries'), findsOneWidget);
    });

    testWidgets('tapping search icon navigates to /search', (tester) async {
      var navigated = false;
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            paginatedSessionsProvider.overrideWith(
              (ref) => Stream.value(<JournalSession>[]),
            ),
            photoCountProvider.overrideWith((ref) => Future.value(0)),
            sessionCountProvider.overrideWith((ref) => Future.value(10)),
          ],
          child: MaterialApp(
            home: const SessionListScreen(),
            routes: {
              '/search': (context) {
                navigated = true;
                return const Scaffold(body: Text('Search'));
              },
            },
          ),
        ),
      );

      await tester.pumpAndSettle();

      await tester.tap(find.byIcon(Icons.search));
      await tester.pumpAndSettle();

      expect(navigated, true);
    });

    testWidgets('gallery icon hidden on provider error', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            paginatedSessionsProvider.overrideWith(
              (ref) => Stream.value(<JournalSession>[]),
            ),
            photoCountProvider.overrideWith((ref) => Future<int>.error('fail')),
          ],
          child: const MaterialApp(home: SessionListScreen()),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.photo_library_outlined), findsNothing);
    });

    testWidgets('search icon hidden on provider error', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            paginatedSessionsProvider.overrideWith(
              (ref) => Stream.value(<JournalSession>[]),
            ),
            photoCountProvider.overrideWith((ref) => Future.value(0)),
            sessionCountProvider.overrideWith(
              (ref) => Future<int>.error('fail'),
            ),
          ],
          child: const MaterialApp(home: SessionListScreen()),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.search), findsNothing);
    });
  });
}
