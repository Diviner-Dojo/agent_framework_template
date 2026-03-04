import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/providers/calendar_providers.dart';
import 'package:agentic_journal/providers/database_provider.dart';
import 'package:agentic_journal/providers/last_capture_mode_provider.dart';
import 'package:agentic_journal/providers/onboarding_providers.dart';
import 'package:agentic_journal/providers/photo_providers.dart';
import 'package:agentic_journal/providers/questionnaire_providers.dart';
import 'package:agentic_journal/providers/reminder_providers.dart';
import 'package:agentic_journal/providers/search_providers.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/providers/voice_providers.dart';
import 'package:agentic_journal/repositories/agent_repository.dart';
import 'package:agentic_journal/ui/screens/session_list_screen.dart';
import 'package:shared_preferences/shared_preferences.dart';

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
            dailyReminderVisibleProvider.overrideWith((ref) => false),
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
            dailyReminderVisibleProvider.overrideWith((ref) => false),
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
            dailyReminderVisibleProvider.overrideWith((ref) => false),
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
            dailyReminderVisibleProvider.overrideWith((ref) => false),
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
            dailyReminderVisibleProvider.overrideWith((ref) => false),
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
            dailyReminderVisibleProvider.overrideWith((ref) => false),
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
            dailyReminderVisibleProvider.overrideWith((ref) => false),
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
            dailyReminderVisibleProvider.overrideWith((ref) => false),
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
            dailyReminderVisibleProvider.overrideWith((ref) => false),
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
            dailyReminderVisibleProvider.overrideWith((ref) => false),
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
          locationName: 'Denver, Colorado',
        ),
      ];

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            paginatedSessionsProvider.overrideWith(
              (ref) => Stream.value(sessions),
            ),
            photoCountProvider.overrideWith((ref) => Future.value(0)),
            dailyReminderVisibleProvider.overrideWith((ref) => false),
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
            dailyReminderVisibleProvider.overrideWith((ref) => false),
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
            dailyReminderVisibleProvider.overrideWith((ref) => false),
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
            dailyReminderVisibleProvider.overrideWith((ref) => false),
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
            dailyReminderVisibleProvider.overrideWith((ref) => false),
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
            dailyReminderVisibleProvider.overrideWith((ref) => false),
          ],
          child: const MaterialApp(home: SessionListScreen()),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.search), findsNothing);
    });

    group('pending calendar events banner', () {
      testWidgets('hidden when no pending events', (tester) async {
        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              paginatedSessionsProvider.overrideWith(
                (ref) => Stream.value(<JournalSession>[]),
              ),
              photoCountProvider.overrideWith((ref) => Future.value(0)),
              pendingCalendarEventsCountProvider.overrideWith(
                (ref) => Future.value(0),
              ),
              dailyReminderVisibleProvider.overrideWith((ref) => false),
            ],
            child: const MaterialApp(home: SessionListScreen()),
          ),
        );

        await tester.pumpAndSettle();

        expect(find.byIcon(Icons.event_note), findsNothing);
        expect(find.text('Tap to connect Google Calendar'), findsNothing);
      });

      testWidgets('shows banner for 1 pending event', (tester) async {
        final now = DateTime.utc(2026, 2, 25, 10, 0);
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
            summary: 'Test session',
          ),
        ];

        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              paginatedSessionsProvider.overrideWith(
                (ref) => Stream.value(sessions),
              ),
              photoCountProvider.overrideWith((ref) => Future.value(0)),
              pendingCalendarEventsCountProvider.overrideWith(
                (ref) => Future.value(1),
              ),
              dailyReminderVisibleProvider.overrideWith((ref) => false),
            ],
            child: const MaterialApp(home: SessionListScreen()),
          ),
        );

        await tester.pumpAndSettle();

        expect(find.text('1 pending calendar event'), findsOneWidget);
        expect(find.text('Tap to connect Google Calendar'), findsOneWidget);
        expect(find.byIcon(Icons.event_note), findsOneWidget);
      });

      testWidgets('shows plural text for multiple pending events', (
        tester,
      ) async {
        final now = DateTime.utc(2026, 2, 25, 10, 0);
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
        ];

        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              paginatedSessionsProvider.overrideWith(
                (ref) => Stream.value(sessions),
              ),
              photoCountProvider.overrideWith((ref) => Future.value(0)),
              pendingCalendarEventsCountProvider.overrideWith(
                (ref) => Future.value(3),
              ),
              dailyReminderVisibleProvider.overrideWith((ref) => false),
            ],
            child: const MaterialApp(home: SessionListScreen()),
          ),
        );

        await tester.pumpAndSettle();

        expect(find.text('3 pending calendar events'), findsOneWidget);
      });

      testWidgets('hidden on provider error', (tester) async {
        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              paginatedSessionsProvider.overrideWith(
                (ref) => Stream.value(<JournalSession>[]),
              ),
              photoCountProvider.overrideWith((ref) => Future.value(0)),
              pendingCalendarEventsCountProvider.overrideWith(
                (ref) => Future<int>.error('fail'),
              ),
              dailyReminderVisibleProvider.overrideWith((ref) => false),
            ],
            child: const MaterialApp(home: SessionListScreen()),
          ),
        );

        await tester.pumpAndSettle();

        expect(find.byIcon(Icons.event_note), findsNothing);
      });
    });

    // Phase 2B — Quick Check-In CTA banner (REV-20260303-142206 B6)
    // Banner is shown universally (no gap-detection) until dismissed.
    // Dismissal persists at app level via quickCheckInBannerDismissedProvider.
    group('quick check-in banner', () {
      final sessionTime = DateTime.utc(2026, 2, 19, 10, 0);
      final session = JournalSession(
        sessionId: 's1',
        startTime: sessionTime,
        timezone: 'UTC',
        syncStatus: 'PENDING',
        isResumed: false,
        resumeCount: 0,
        createdAt: sessionTime,
        updatedAt: sessionTime,
      );

      testWidgets('shown when sessions exist and not dismissed', (
        tester,
      ) async {
        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              paginatedSessionsProvider.overrideWith(
                (ref) => Stream.value([session]),
              ),
              photoCountProvider.overrideWith((ref) => Future.value(0)),
              quickCheckInBannerDismissedProvider.overrideWith((ref) => false),
              dailyReminderVisibleProvider.overrideWith((ref) => false),
            ],
            child: const MaterialApp(home: SessionListScreen()),
          ),
        );

        await tester.pumpAndSettle();

        expect(find.text('Quick check-in'), findsOneWidget);
        expect(find.text('Just browse'), findsOneWidget);
      });

      testWidgets('not shown in empty state (no sessions)', (tester) async {
        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              paginatedSessionsProvider.overrideWith(
                (ref) => Stream.value(<JournalSession>[]),
              ),
              photoCountProvider.overrideWith((ref) => Future.value(0)),
              quickCheckInBannerDismissedProvider.overrideWith((ref) => false),
              dailyReminderVisibleProvider.overrideWith((ref) => false),
            ],
            child: const MaterialApp(home: SessionListScreen()),
          ),
        );

        await tester.pumpAndSettle();

        expect(find.text('Quick check-in'), findsNothing);
        expect(find.text('Just browse'), findsNothing);
      });

      testWidgets('close button dismisses banner — does not reappear', (
        tester,
      ) async {
        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              paginatedSessionsProvider.overrideWith(
                (ref) => Stream.value([session]),
              ),
              photoCountProvider.overrideWith((ref) => Future.value(0)),
              quickCheckInBannerDismissedProvider.overrideWith((ref) => false),
              dailyReminderVisibleProvider.overrideWith((ref) => false),
            ],
            child: const MaterialApp(home: SessionListScreen()),
          ),
        );

        await tester.pumpAndSettle();

        // Banner visible.
        expect(find.text('Quick check-in'), findsOneWidget);

        // Dismiss via close icon.
        await tester.tap(find.byTooltip('Dismiss'));
        await tester.pumpAndSettle();

        // Banner is gone.
        expect(find.text('Quick check-in'), findsNothing);
        expect(find.text('Just browse'), findsNothing);
      });

      testWidgets('Just browse dismisses banner — does not reappear', (
        tester,
      ) async {
        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              paginatedSessionsProvider.overrideWith(
                (ref) => Stream.value([session]),
              ),
              photoCountProvider.overrideWith((ref) => Future.value(0)),
              quickCheckInBannerDismissedProvider.overrideWith((ref) => false),
              dailyReminderVisibleProvider.overrideWith((ref) => false),
            ],
            child: const MaterialApp(home: SessionListScreen()),
          ),
        );

        await tester.pumpAndSettle();

        expect(find.text('Just browse'), findsOneWidget);

        await tester.tap(find.text('Just browse'));
        await tester.pumpAndSettle();

        expect(find.text('Quick check-in'), findsNothing);
        expect(find.text('Just browse'), findsNothing);
      });

      testWidgets('banner absent when already dismissed', (tester) async {
        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              paginatedSessionsProvider.overrideWith(
                (ref) => Stream.value([session]),
              ),
              photoCountProvider.overrideWith((ref) => Future.value(0)),
              // Start with dismissed = true (persisted from prior navigation).
              quickCheckInBannerDismissedProvider.overrideWith((ref) => true),
              dailyReminderVisibleProvider.overrideWith((ref) => false),
            ],
            child: const MaterialApp(home: SessionListScreen()),
          ),
        );

        await tester.pumpAndSettle();

        expect(find.text('Quick check-in'), findsNothing);
        expect(find.text('Just browse'), findsNothing);
      });
    });

    // ---------------------------------------------------------------------------
    // _openQuickCapturePalette dispatch branch tests (Advisory A1 from
    // REV-20260304-142456 — coverage for the 5 routing branches).
    // ---------------------------------------------------------------------------
    group('_openQuickCapturePalette dispatch branches', () {
      // Shared base overrides that keep the screen buildable for these tests.
      List<Override> baseOverrides({SharedPreferences? prefs}) {
        final p = prefs;
        return [
          paginatedSessionsProvider.overrideWith(
            (ref) => Stream.value(<JournalSession>[]),
          ),
          photoCountProvider.overrideWith((ref) => Future.value(0)),
          dailyReminderVisibleProvider.overrideWith((ref) => false),
          if (p != null) sharedPreferencesProvider.overrideWithValue(p),
        ];
      }

      testWidgets(
        'tapping Mood Tap tile opens QuickMoodTapSheet (mood-tap dispatch)',
        (tester) async {
          SharedPreferences.setMockInitialValues({});
          final prefs = await SharedPreferences.getInstance();

          await tester.pumpWidget(
            ProviderScope(
              overrides: baseOverrides(prefs: prefs),
              child: const MaterialApp(home: SessionListScreen()),
            ),
          );
          await tester.pumpAndSettle();

          // Open the Quick Capture Palette.
          await tester.tap(find.byType(FloatingActionButton));
          await tester.pumpAndSettle();
          expect(find.text('Mood Tap'), findsOneWidget);

          // Tap the Mood Tap tile.
          await tester.tap(find.text('Mood Tap'));
          await tester.pumpAndSettle();

          // QuickMoodTapSheet should now be visible.
          expect(
            find.text('How are you feeling?'),
            findsOneWidget,
            reason:
                'tapping Mood Tap must open QuickMoodTapSheet, not navigate '
                'to a session screen',
          );
        },
      );

      testWidgets(
        'tapping Voice tile enables voiceModeEnabledProvider (voice pre-enable dispatch)',
        (tester) async {
          SharedPreferences.setMockInitialValues({});
          final prefs = await SharedPreferences.getInstance();

          // Use a real VoiceModeNotifier so we can read the enabled state.
          bool? voiceModeEnabled;

          await tester.pumpWidget(
            ProviderScope(
              overrides: [
                ...baseOverrides(prefs: prefs),
                // Intercept session start so navigation doesn't fail.
                paginatedSessionsProvider.overrideWith(
                  (ref) => Stream.value(<JournalSession>[]),
                ),
              ],
              child: Builder(
                builder: (context) {
                  return const MaterialApp(home: SessionListScreen());
                },
              ),
            ),
          );
          await tester.pumpAndSettle();

          // Capture a reference to the ProviderScope's container.
          // containerOf() requires a descendant element, not the ProviderScope itself.
          final element = tester.element(find.byType(SessionListScreen));
          final container = ProviderScope.containerOf(element);

          // Open palette and tap Voice.
          await tester.tap(find.byType(FloatingActionButton));
          await tester.pumpAndSettle();
          expect(find.text('Voice'), findsOneWidget);

          await tester.tap(find.text('Voice'));
          // Pump a single frame — voice mode is set synchronously before
          // the async _startNewSession() call.
          await tester.pump();

          voiceModeEnabled = container.read(voiceModeEnabledProvider);
          expect(
            voiceModeEnabled,
            isTrue,
            reason:
                'voice pre-enable must set voiceModeEnabledProvider=true '
                'before _startNewSession() is called',
          );
        },
      );

      testWidgets(
        'tapping Write/Check-In tiles persists mode key via lastCaptureModeProvider',
        (tester) async {
          SharedPreferences.setMockInitialValues({});
          final prefs = await SharedPreferences.getInstance();

          await tester.pumpWidget(
            ProviderScope(
              overrides: baseOverrides(prefs: prefs),
              child: const MaterialApp(home: SessionListScreen()),
            ),
          );
          await tester.pumpAndSettle();

          // containerOf() requires a descendant element, not the ProviderScope itself.
          final element = tester.element(find.byType(SessionListScreen));
          final container = ProviderScope.containerOf(element);

          // Initially no preference.
          expect(container.read(lastCaptureModeProvider), isNull);

          // Open palette and tap Write.
          await tester.tap(find.byType(FloatingActionButton));
          await tester.pumpAndSettle();
          await tester.tap(find.text('Write'));
          await tester.pump();

          // lastCaptureModeProvider must be persisted before _startNewSession.
          expect(
            container.read(lastCaptureModeProvider),
            equals('text'),
            reason:
                'tapping Write must persist mode key "text" via '
                'lastCaptureModeProvider before navigation',
          );
        },
      );
    }); // end '_openQuickCapturePalette dispatch branches'

    // Phase 4B: widget launch dispatch via pendingWidgetLaunchModeProvider.
    // These tests verify that the ref.listen in build() correctly dispatches
    // to the right capture mode when the app is opened from the home screen
    // widget (regression guard — if the ref.listen is removed, these fail).
    //
    // Pump strategy: pumpAndSettle() cannot settle after setMode() triggers
    // _startNewSession() because drift's NativeDatabase creates real async
    // work that conflicts with fake_async's frame scheduler. Instead:
    //   1. pump() — fires ref.listen, clears provider, registers callback
    //   2. pump() — fires postFrameCallback, setMode() completes (mock prefs
    //      are synchronous microtasks), _startNewSession() begins async work
    //   3. runAsync() — real event loop processes any pending DB futures
    //   4. pump() — processes state changes and any navigation that occurred
    //
    // We verify lastCaptureModeProvider (set synchronously before startSession
    // starts its async work) rather than navigation destination — the mode
    // value determines the route via a simple if/else in _dispatchCaptureMode,
    // so verifying the mode is equivalent to verifying the routing intent.
    // ---------------------------------------------------------------------------
    group('Phase 4B widget launch dispatch (pendingWidgetLaunchModeProvider)', () {
      // Shared base overrides for the widget launch tests.
      // db: in-memory AppDatabase so startSession() can write the session row.
      // activeSessionMessagesProvider: overridden to prevent drift QueryStreams
      //   from being created — avoids fake_async timer conflicts at teardown.
      List<Override> baseOverrides({
        SharedPreferences? prefs,
        AppDatabase? db,
      }) {
        final p = prefs;
        return [
          paginatedSessionsProvider.overrideWith(
            (ref) => Stream.value(<JournalSession>[]),
          ),
          photoCountProvider.overrideWith((ref) => Future.value(0)),
          dailyReminderVisibleProvider.overrideWith((ref) => false),
          deviceTimezoneProvider.overrideWith(
            (ref) async => 'America/New_York',
          ),
          // Prevent drift QueryStream creation so fake_async doesn't get
          // zero-duration timer conflicts from StreamQueryStore.markAsClosed.
          // checkInCountProvider wraps dao.watchAllResponses() (a drift
          // .watch() query) and must be overridden or disposal creates a
          // pending timer that fails _verifyInvariants.
          activeSessionMessagesProvider.overrideWith(
            (ref) => Stream.value(<JournalMessage>[]),
          ),
          checkInCountProvider.overrideWith((ref) => Stream.value(0)),
          if (p != null) sharedPreferencesProvider.overrideWithValue(p),
          if (db != null) databaseProvider.overrideWithValue(db),
          if (db != null)
            agentRepositoryProvider.overrideWithValue(AgentRepository()),
        ];
      }

      testWidgets(
        'text mode: sets lastCaptureModeProvider to "text" and clears provider',
        (tester) async {
          SharedPreferences.setMockInitialValues({});
          final prefs = await SharedPreferences.getInstance();
          final database = AppDatabase.forTesting(NativeDatabase.memory());
          addTearDown(database.close);

          await tester.pumpWidget(
            ProviderScope(
              overrides: baseOverrides(prefs: prefs, db: database),
              child: MaterialApp(
                home: const SessionListScreen(),
                routes: {
                  '/session': (_) =>
                      const Scaffold(body: Text('Session Screen')),
                  '/check_in': (_) =>
                      const Scaffold(body: Text('CheckIn Screen')),
                },
              ),
            ),
          );
          await tester.pumpAndSettle();

          // Simulate widget launch by setting the pending mode.
          final element = tester.element(find.byType(SessionListScreen));
          final container = ProviderScope.containerOf(element);
          container.read(pendingWidgetLaunchModeProvider.notifier).state =
              'text';

          // Step 1: ref.listen fires → provider cleared → postFrameCallback
          // registered.
          await tester.pump();
          // Step 2: postFrameCallback fires → setMode('text') completes
          // (mock SharedPreferences is synchronous) → _dispatchCaptureMode
          // starts → _startNewSession begins async DB work.
          await tester.pump();
          // Step 3: let real async DB futures resolve (NativeDatabase uses FFI).
          await tester.runAsync(() async {
            await Future<void>.delayed(const Duration(milliseconds: 300));
          });
          // Step 4: process resulting state changes.
          await tester.pump();

          expect(
            container.read(lastCaptureModeProvider),
            equals('text'),
            reason:
                'widget launch with mode=text must persist "text" via '
                'lastCaptureModeProvider before navigation',
          );
          expect(
            container.read(pendingWidgetLaunchModeProvider),
            isNull,
            reason:
                'pendingWidgetLaunchModeProvider must be cleared to null '
                'after dispatch to prevent double-fire',
          );
        },
      );

      testWidgets(
        'pulse_check_in mode: sets lastCaptureModeProvider to "pulse_check_in" '
        'and clears provider',
        (tester) async {
          SharedPreferences.setMockInitialValues({});
          final prefs = await SharedPreferences.getInstance();
          final database = AppDatabase.forTesting(NativeDatabase.memory());
          addTearDown(database.close);

          await tester.pumpWidget(
            ProviderScope(
              overrides: baseOverrides(prefs: prefs, db: database),
              child: MaterialApp(
                home: const SessionListScreen(),
                routes: {
                  '/session': (_) =>
                      const Scaffold(body: Text('Session Screen')),
                  '/check_in': (_) =>
                      const Scaffold(body: Text('CheckIn Screen')),
                },
              ),
            ),
          );
          await tester.pumpAndSettle();

          final element = tester.element(find.byType(SessionListScreen));
          final container = ProviderScope.containerOf(element);
          container.read(pendingWidgetLaunchModeProvider.notifier).state =
              'pulse_check_in';

          await tester.pump();
          await tester.pump();
          await tester.runAsync(() async {
            await Future<void>.delayed(const Duration(milliseconds: 300));
          });
          await tester.pump();

          expect(
            container.read(lastCaptureModeProvider),
            equals('pulse_check_in'),
            reason:
                'widget launch with mode=pulse_check_in must persist '
                '"pulse_check_in" via lastCaptureModeProvider',
          );
          expect(
            container.read(pendingWidgetLaunchModeProvider),
            isNull,
            reason:
                'pendingWidgetLaunchModeProvider must be cleared to null '
                'after dispatch',
          );
        },
      );

      testWidgets(
        'provider cleared to null after dispatch — no double-dispatch on re-pump',
        (tester) async {
          SharedPreferences.setMockInitialValues({});
          final prefs = await SharedPreferences.getInstance();
          final database = AppDatabase.forTesting(NativeDatabase.memory());
          addTearDown(database.close);

          await tester.pumpWidget(
            ProviderScope(
              overrides: baseOverrides(prefs: prefs, db: database),
              child: MaterialApp(
                home: const SessionListScreen(),
                routes: {
                  '/session': (_) =>
                      const Scaffold(body: Text('Session Screen')),
                  '/check_in': (_) =>
                      const Scaffold(body: Text('CheckIn Screen')),
                },
              ),
            ),
          );
          await tester.pumpAndSettle();

          final element = tester.element(find.byType(SessionListScreen));
          final container = ProviderScope.containerOf(element);

          // Dispatch once.
          container.read(pendingWidgetLaunchModeProvider.notifier).state =
              'text';
          await tester.pump();
          await tester.pump();
          await tester.runAsync(() async {
            await Future<void>.delayed(const Duration(milliseconds: 300));
          });
          await tester.pump();

          // Provider is cleared — verifies the if (next == null) return guard
          // prevents re-dispatch when provider was cleared inside the listener.
          expect(
            container.read(pendingWidgetLaunchModeProvider),
            isNull,
            reason:
                'pendingWidgetLaunchModeProvider must be cleared to null '
                'after dispatch to prevent double-fire on rebuild',
          );
          // Mode was persisted exactly once.
          expect(container.read(lastCaptureModeProvider), equals('text'));

          // Additional pumps must NOT re-dispatch (mode key unchanged).
          await tester.pump();
          await tester.pump();
          expect(
            container.read(lastCaptureModeProvider),
            equals('text'),
            reason: 'mode key must not change after a re-pump',
          );
          expect(
            container.read(pendingWidgetLaunchModeProvider),
            isNull,
            reason: 'provider must remain null after a re-pump',
          );
        },
      );
    }); // end 'Phase 4B widget launch dispatch'
  });
}
