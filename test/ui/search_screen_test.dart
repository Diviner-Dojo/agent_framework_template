import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:drift/native.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';
import 'package:agentic_journal/models/search_models.dart';
import 'package:agentic_journal/providers/database_provider.dart';
import 'package:agentic_journal/providers/search_providers.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/services/connectivity_service.dart';
import 'package:agentic_journal/ui/screens/search_screen.dart';

void main() {
  late AppDatabase database;

  setUp(() {
    database = AppDatabase.forTesting(NativeDatabase.memory());
  });

  tearDown(() async {
    await database.close();
  });

  Widget buildSearchScreen({List<Override> overrides = const []}) {
    return ProviderScope(
      overrides: [
        databaseProvider.overrideWithValue(database),
        connectivityServiceProvider.overrideWithValue(ConnectivityService()),
        ...overrides,
      ],
      child: const MaterialApp(home: SearchScreen()),
    );
  }

  group('SearchScreen', () {
    testWidgets('shows search bar', (tester) async {
      await tester.pumpWidget(buildSearchScreen());
      await tester.pumpAndSettle();

      expect(find.byType(TextField), findsOneWidget);
    });

    testWidgets('shows app bar title', (tester) async {
      await tester.pumpWidget(buildSearchScreen());
      await tester.pumpAndSettle();

      expect(find.text('Search Journal'), findsOneWidget);
    });

    testWidgets('shows pre-search empty state', (tester) async {
      await tester.pumpWidget(buildSearchScreen());
      await tester.pumpAndSettle();

      expect(find.text('Search your journal'), findsOneWidget);
      expect(
        find.text('Find entries by keyword, date, mood, or people'),
        findsOneWidget,
      );
    });

    testWidgets('filter chips are displayed', (tester) async {
      await tester.pumpWidget(buildSearchScreen());
      await tester.pumpAndSettle();

      expect(find.text('Date'), findsOneWidget);
      expect(find.text('Mood'), findsOneWidget);
      expect(find.text('People'), findsOneWidget);
      expect(find.text('Topics'), findsOneWidget);
    });

    testWidgets('typing in search bar updates query', (tester) async {
      await tester.pumpWidget(buildSearchScreen());
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField), 'work');
      // Wait for debounce (300ms + buffer).
      await tester.pump(const Duration(milliseconds: 350));
      await tester.pumpAndSettle();

      // After debounce, the provider should have the query.
      // The UI should show no results (empty database).
      expect(find.text('No entries found'), findsOneWidget);
    });

    testWidgets('shows results when entries match', (tester) async {
      // Create a session with matching content.
      final sessionDao = SessionDao(database);
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 19), 'UTC');
      await sessionDao.endSession(
        's1',
        DateTime.utc(2026, 2, 19, 0, 30),
        summary: 'Work was stressful today',
      );

      await tester.pumpWidget(buildSearchScreen());
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField), 'stressful');
      await tester.pump(const Duration(milliseconds: 350));
      await tester.pumpAndSettle();

      // Should find the session.
      expect(find.text('No entries found'), findsNothing);
      expect(find.text('Summary'), findsOneWidget);
    });

    testWidgets('shows no-match with filters message', (tester) async {
      await tester.pumpWidget(buildSearchScreen());
      await tester.pumpAndSettle();

      // Enter a query.
      await tester.enterText(find.byType(TextField), 'nonexistent');
      await tester.pump(const Duration(milliseconds: 350));
      await tester.pumpAndSettle();

      // Also set a filter to trigger the "with filters" branch.
      final container = ProviderScope.containerOf(
        tester.element(find.byType(SearchScreen)),
      );
      container.read(searchFiltersProvider.notifier).state = SearchFilters(
        dateStart: DateTime.utc(2026, 2, 1),
      );
      await tester.pumpAndSettle();

      // Should show the filters-specific no-results message.
      expect(find.text('No entries match your filters'), findsOneWidget);
      expect(find.text('Clear filters'), findsOneWidget);
    });

    testWidgets('clear filters button resets filters', (tester) async {
      await tester.pumpWidget(buildSearchScreen());
      await tester.pumpAndSettle();

      final container = ProviderScope.containerOf(
        tester.element(find.byType(SearchScreen)),
      );

      // Set a query and filter.
      await tester.enterText(find.byType(TextField), 'nonexistent');
      await tester.pump(const Duration(milliseconds: 350));
      container.read(searchFiltersProvider.notifier).state = SearchFilters(
        dateStart: DateTime.utc(2026, 2, 1),
      );
      await tester.pumpAndSettle();

      expect(find.text('No entries match your filters'), findsOneWidget);

      // Tap clear filters.
      await tester.tap(find.text('Clear filters'));
      await tester.pumpAndSettle();

      // Should go back to "No entries found" (without filter message).
      expect(find.text('No entries found'), findsOneWidget);
    });

    testWidgets('date filter chip opens bottom sheet', (tester) async {
      await tester.pumpWidget(buildSearchScreen());
      await tester.pumpAndSettle();

      // Tap the Date filter chip.
      await tester.tap(find.text('Date'));
      await tester.pumpAndSettle();

      // Bottom sheet should show date range options.
      expect(find.text('Date Range'), findsOneWidget);
      expect(find.text('Last 7 days'), findsOneWidget);
      expect(find.text('Last 30 days'), findsOneWidget);
      expect(find.text('This year'), findsOneWidget);
      expect(find.text('Custom range...'), findsOneWidget);
    });

    testWidgets('Last 7 days preset sets date filter', (tester) async {
      await tester.pumpWidget(buildSearchScreen());
      await tester.pumpAndSettle();

      // Tap Date chip to open bottom sheet.
      await tester.tap(find.text('Date'));
      await tester.pumpAndSettle();

      // Tap "Last 7 days" preset.
      await tester.tap(find.text('Last 7 days'));
      await tester.pumpAndSettle();

      // Filter should now be active.
      final container = ProviderScope.containerOf(
        tester.element(find.byType(SearchScreen)),
      );
      final filters = container.read(searchFiltersProvider);
      expect(filters.hasActiveFilters, isTrue);
      expect(filters.dateStart, isNotNull);
    });

    testWidgets('Last 30 days preset sets date filter', (tester) async {
      await tester.pumpWidget(buildSearchScreen());
      await tester.pumpAndSettle();

      await tester.tap(find.text('Date'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Last 30 days'));
      await tester.pumpAndSettle();

      final container = ProviderScope.containerOf(
        tester.element(find.byType(SearchScreen)),
      );
      final filters = container.read(searchFiltersProvider);
      expect(filters.hasActiveFilters, isTrue);
      expect(filters.dateStart, isNotNull);
    });

    testWidgets('This year preset sets date filter', (tester) async {
      await tester.pumpWidget(buildSearchScreen());
      await tester.pumpAndSettle();

      await tester.tap(find.text('Date'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('This year'));
      await tester.pumpAndSettle();

      final container = ProviderScope.containerOf(
        tester.element(find.byType(SearchScreen)),
      );
      final filters = container.read(searchFiltersProvider);
      expect(filters.hasActiveFilters, isTrue);
      expect(filters.dateStart, isNotNull);
    });
  });
}
