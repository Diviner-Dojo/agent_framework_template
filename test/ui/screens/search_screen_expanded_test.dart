// ===========================================================================
// file: test/ui/screens/search_screen_expanded_test.dart
// purpose: Expanded widget tests for search screen — covers multi-select
//          sheet interactions, clear-all filters button, offline banner,
//          and clear search button.
// ===========================================================================

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:drift/native.dart';

import 'package:agentic_journal/database/app_database.dart';
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

  Widget buildSearchScreen({
    bool isOnline = true,
    List<String> moodTags = const [],
    List<String> people = const [],
    List<String> topicTags = const [],
    List<Override> extraOverrides = const [],
  }) {
    final connectivity = ConnectivityService();
    // ConnectivityService defaults to offline in tests.

    return ProviderScope(
      overrides: [
        databaseProvider.overrideWithValue(database),
        connectivityServiceProvider.overrideWithValue(connectivity),
        availableMoodTagsProvider.overrideWith((ref) => Future.value(moodTags)),
        availablePeopleProvider.overrideWith((ref) => Future.value(people)),
        availableTopicTagsProvider.overrideWith(
          (ref) => Future.value(topicTags),
        ),
        ...extraOverrides,
      ],
      child: const MaterialApp(home: SearchScreen()),
    );
  }

  group('Search screen — offline banner', () {
    testWidgets('shows offline banner when not online', (tester) async {
      await tester.pumpWidget(buildSearchScreen());
      await tester.pumpAndSettle();

      // ConnectivityService defaults to offline — banner should show.
      expect(find.byIcon(Icons.cloud_off), findsOneWidget);
      expect(find.textContaining('Searching local data'), findsOneWidget);
    });
  });

  group('Search screen — clear search', () {
    testWidgets('clear button appears after typing and debounce', (
      tester,
    ) async {
      await tester.pumpWidget(buildSearchScreen());
      await tester.pumpAndSettle();

      // No clear button initially.
      expect(find.byIcon(Icons.clear), findsNothing);

      // Type in search bar and wait for debounce + rebuild.
      await tester.enterText(find.byType(TextField), 'hello');
      await tester.pump(const Duration(milliseconds: 350));
      await tester.pumpAndSettle();

      // After search results update triggers rebuild, clear button appears.
      expect(find.byIcon(Icons.clear), findsOneWidget);
    });

    testWidgets('clear button resets search text', (tester) async {
      await tester.pumpWidget(buildSearchScreen());
      await tester.pumpAndSettle();

      // Type and wait for debounce.
      await tester.enterText(find.byType(TextField), 'test');
      await tester.pump(const Duration(milliseconds: 350));
      await tester.pumpAndSettle();

      // Tap clear button.
      await tester.tap(find.byIcon(Icons.clear));
      await tester.pumpAndSettle();

      // Should return to pre-search state.
      expect(find.text('Search your journal'), findsOneWidget);
    });
  });

  group('Search screen — filter chip interactions', () {
    testWidgets('Mood chip opens multi-select bottom sheet', (tester) async {
      await tester.pumpWidget(
        buildSearchScreen(moodTags: ['Happy', 'Sad', 'Anxious']),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Mood'));
      await tester.pumpAndSettle();

      expect(find.text('Mood'), findsWidgets); // Title + chip
      expect(find.text('Apply'), findsOneWidget);
      expect(find.text('Happy'), findsOneWidget);
      expect(find.text('Sad'), findsOneWidget);
      expect(find.text('Anxious'), findsOneWidget);
    });

    testWidgets('People chip opens multi-select bottom sheet', (tester) async {
      await tester.pumpWidget(buildSearchScreen(people: ['Alice', 'Bob']));
      await tester.pumpAndSettle();

      await tester.tap(find.text('People'));
      await tester.pumpAndSettle();

      expect(find.text('Apply'), findsOneWidget);
      expect(find.text('Alice'), findsOneWidget);
      expect(find.text('Bob'), findsOneWidget);
    });

    testWidgets('Topics chip opens multi-select bottom sheet', (tester) async {
      await tester.pumpWidget(buildSearchScreen(topicTags: ['Work', 'Health']));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Topics'));
      await tester.pumpAndSettle();

      expect(find.text('Apply'), findsOneWidget);
      expect(find.text('Work'), findsOneWidget);
      expect(find.text('Health'), findsOneWidget);
    });

    testWidgets('multi-select shows empty message when no items', (
      tester,
    ) async {
      await tester.pumpWidget(buildSearchScreen(moodTags: []));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Mood'));
      await tester.pumpAndSettle();

      expect(find.text('No mood found in your journal yet'), findsOneWidget);
    });

    testWidgets('clear-all icon appears when filters are active', (
      tester,
    ) async {
      await tester.pumpWidget(buildSearchScreen());
      await tester.pumpAndSettle();

      // No clear-all icon initially.
      expect(find.byIcon(Icons.clear_all), findsNothing);

      // Activate a filter.
      final container = ProviderScope.containerOf(
        tester.element(find.byType(SearchScreen)),
      );
      container.read(searchFiltersProvider.notifier).state = SearchFilters(
        dateStart: DateTime.utc(2026, 1, 1),
      );
      await tester.pumpAndSettle();

      // Clear-all icon should appear.
      expect(find.byIcon(Icons.clear_all), findsWidgets);
    });

    testWidgets('date filter chip shows "Date range" when active', (
      tester,
    ) async {
      await tester.pumpWidget(buildSearchScreen());
      await tester.pumpAndSettle();

      // Initially shows "Date".
      expect(find.text('Date'), findsOneWidget);

      // Activate a date filter.
      final container = ProviderScope.containerOf(
        tester.element(find.byType(SearchScreen)),
      );
      container.read(searchFiltersProvider.notifier).state = SearchFilters(
        dateStart: DateTime.utc(2026, 1, 1),
      );
      await tester.pumpAndSettle();

      // Should now show "Date range".
      expect(find.text('Date range'), findsOneWidget);
    });

    testWidgets('clear date filter button appears in date sheet', (
      tester,
    ) async {
      await tester.pumpWidget(buildSearchScreen());
      await tester.pumpAndSettle();

      // Set a date filter.
      final container = ProviderScope.containerOf(
        tester.element(find.byType(SearchScreen)),
      );
      container.read(searchFiltersProvider.notifier).state = SearchFilters(
        dateStart: DateTime.utc(2026, 1, 1),
      );
      await tester.pumpAndSettle();

      // Open date picker.
      await tester.tap(find.text('Date range'));
      await tester.pumpAndSettle();

      // Should have "Clear date filter" button.
      expect(find.text('Clear date filter'), findsOneWidget);
    });
  });

  group('Search screen — error state', () {
    testWidgets('shows error message on search failure', (tester) async {
      await tester.pumpWidget(
        buildSearchScreen(
          extraOverrides: [
            searchResultsProvider.overrideWith(
              (ref) => Future.error('network error'),
            ),
            searchQueryProvider.overrideWith((ref) => 'test'),
          ],
        ),
      );
      await tester.pumpAndSettle();

      expect(
        find.text('Something went wrong. Try searching again.'),
        findsOneWidget,
      );
    });
  });
}
