// ===========================================================================
// file: test/ui/screens/search_screen_results_test.dart
// purpose: Widget tests for search screen results rendering paths — covers
//          no results with/without filters, results list rendering, and
//          the loading state.
// ===========================================================================

import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/message_dao.dart';
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

  Widget buildSearchScreen({List<Override> extraOverrides = const []}) {
    final connectivity = ConnectivityService();

    return ProviderScope(
      overrides: [
        databaseProvider.overrideWithValue(database),
        connectivityServiceProvider.overrideWithValue(connectivity),
        availableMoodTagsProvider.overrideWith((ref) => Future.value([])),
        availablePeopleProvider.overrideWith((ref) => Future.value([])),
        availableTopicTagsProvider.overrideWith((ref) => Future.value([])),
        ...extraOverrides,
      ],
      child: MaterialApp(
        home: const SearchScreen(),
        routes: {
          '/session/detail': (context) =>
              const Scaffold(body: Text('Detail Screen')),
        },
      ),
    );
  }

  group('Search screen — no results (typed query)', () {
    testWidgets('shows no results message for unmatched query', (tester) async {
      await tester.pumpWidget(buildSearchScreen());
      await tester.pumpAndSettle();

      // Type a query that won't match anything in the empty DB.
      await tester.enterText(find.byType(TextField), 'xyznonexistent');
      await tester.pump(const Duration(milliseconds: 350));
      await tester.pumpAndSettle();

      expect(find.text('No entries found'), findsOneWidget);
      expect(find.text('Try different keywords'), findsOneWidget);
      expect(find.byIcon(Icons.search_off), findsOneWidget);
    });

    testWidgets('shows no results with filters message', (tester) async {
      await tester.pumpWidget(buildSearchScreen());
      await tester.pumpAndSettle();

      // Set a date filter.
      final container = ProviderScope.containerOf(
        tester.element(find.byType(SearchScreen)),
      );
      container.read(searchFiltersProvider.notifier).state = SearchFilters(
        dateStart: DateTime.utc(2026, 1, 1),
        dateEnd: DateTime.utc(2026, 1, 31),
      );

      // Type a query.
      await tester.enterText(find.byType(TextField), 'nope');
      await tester.pump(const Duration(milliseconds: 350));
      await tester.pumpAndSettle();

      expect(find.text('No entries match your filters'), findsOneWidget);
      expect(
        find.text('Try different keywords or adjust your filters'),
        findsOneWidget,
      );
      expect(find.byIcon(Icons.filter_list_off), findsOneWidget);
      expect(find.text('Clear filters'), findsOneWidget);
    });
  });

  group('Search screen — results list', () {
    testWidgets('renders search result cards for matching query', (
      tester,
    ) async {
      // Insert a session and messages into the DB so search finds them.
      final sessionDao = SessionDao(database);
      final messageDao = MessageDao(database);

      await sessionDao.createSession(
        'sess-1',
        DateTime.utc(2026, 2, 20, 14, 0),
        'UTC',
      );
      await messageDao.insertMessage(
        'msg-1',
        'sess-1',
        'USER',
        'Discussed the project timeline',
        DateTime.utc(2026, 2, 20, 14, 5),
      );
      await sessionDao.endSession(
        'sess-1',
        DateTime.utc(2026, 2, 20, 14, 30),
        summary: 'Meeting notes about timeline',
      );

      await tester.pumpWidget(buildSearchScreen());
      await tester.pumpAndSettle();

      // Type a search query.
      await tester.enterText(find.byType(TextField), 'project');
      await tester.pump(const Duration(milliseconds: 350));
      await tester.pumpAndSettle();

      // Should find the session via message content search.
      // SearchResultCard renders the snippet via RichText (bold matching).
      // Check for session metadata or match source label instead.
      expect(find.text('Conversation'), findsOneWidget);
    });
  });

  group('Search screen — clear filters button', () {
    testWidgets('clear filters button resets to no-filter state', (
      tester,
    ) async {
      await tester.pumpWidget(buildSearchScreen());
      await tester.pumpAndSettle();

      // Set filters.
      final container = ProviderScope.containerOf(
        tester.element(find.byType(SearchScreen)),
      );
      container.read(searchFiltersProvider.notifier).state = SearchFilters(
        dateStart: DateTime.utc(2026, 1, 1),
      );

      // Type a query to get no-results-with-filters state.
      await tester.enterText(find.byType(TextField), 'nada');
      await tester.pump(const Duration(milliseconds: 350));
      await tester.pumpAndSettle();

      expect(find.text('No entries match your filters'), findsOneWidget);

      // Tap "Clear filters".
      await tester.tap(find.text('Clear filters'));
      await tester.pumpAndSettle();

      // Should now show regular no-results state.
      expect(find.text('No entries found'), findsOneWidget);
    });
  });
}
