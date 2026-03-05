// ===========================================================================
// file: test/database/search_filter_browse_regression_test.dart
// purpose: Regression tests for search filter-only browse bug.
//
// Bug: Tapping Mood/People/Topics filter chips and pressing Apply returned
// no results when no keyword was typed. Three compounding root causes:
//   1. session_dao.searchSessions always required a keyword LIKE clause
//   2. search_repository.searchEntries returned early when query was empty
//   3. search_providers.searchResultsProvider returned early when query was empty
//
// See: memory/bugs/regression-ledger.md
//      'Search filter-only browse returns no results'
// ===========================================================================

@Tags(['regression'])
library;

import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:drift/native.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';
import 'package:agentic_journal/database/daos/message_dao.dart';
import 'package:agentic_journal/models/search_models.dart';
import 'package:agentic_journal/providers/database_provider.dart';
import 'package:agentic_journal/providers/search_providers.dart';
import 'package:agentic_journal/repositories/search_repository.dart';

void main() {
  late AppDatabase database;
  late SessionDao sessionDao;
  late MessageDao messageDao;

  setUp(() {
    database = AppDatabase.forTesting(NativeDatabase.memory());
    sessionDao = SessionDao(database);
    messageDao = MessageDao(database);
  });

  tearDown(() async {
    await database.close();
  });

  Future<void> createSession(
    String id,
    DateTime startTime, {
    String? summary,
    List<String>? moodTags,
    List<String>? people,
    List<String>? topicTags,
  }) async {
    await sessionDao.createSession(id, startTime, 'UTC');
    await sessionDao.endSession(
      id,
      startTime.add(const Duration(minutes: 30)),
      summary: summary,
      moodTags: moodTags != null ? jsonEncode(moodTags) : null,
      people: people != null ? jsonEncode(people) : null,
      topicTags: topicTags != null ? jsonEncode(topicTags) : null,
    );
  }

  // ---------------------------------------------------------------------------
  // Layer 1: DAO — searchSessions keyword clause conditional
  // ---------------------------------------------------------------------------

  group('SessionDao.searchSessions — filter-only browse (regression)', () {
    test('empty query with mood filter returns matching sessions', () async {
      await createSession(
        's1',
        DateTime.utc(2026, 2, 19),
        summary: 'Happy day',
        moodTags: ['happy'],
      );
      await createSession(
        's2',
        DateTime.utc(2026, 2, 18),
        summary: 'Sad day',
        moodTags: ['sad'],
      );

      final results = await sessionDao.searchSessions('', moodTags: ['happy']);
      expect(results.length, 1);
      expect(results[0].sessionId, 's1');
    });

    test('empty query with people filter returns matching sessions', () async {
      await createSession(
        's1',
        DateTime.utc(2026, 2, 19),
        summary: 'Meeting',
        people: ['Alice'],
      );
      await createSession(
        's2',
        DateTime.utc(2026, 2, 18),
        summary: 'Solo work',
        people: ['Bob'],
      );

      final results = await sessionDao.searchSessions('', people: ['Alice']);
      expect(results.length, 1);
      expect(results[0].sessionId, 's1');
    });

    test(
      'empty query with topicTags filter returns matching sessions',
      () async {
        await createSession(
          's1',
          DateTime.utc(2026, 2, 19),
          summary: 'Work tasks',
          topicTags: ['work'],
        );
        await createSession(
          's2',
          DateTime.utc(2026, 2, 18),
          summary: 'Health log',
          topicTags: ['health'],
        );

        final results = await sessionDao.searchSessions(
          '',
          topicTags: ['work'],
        );
        expect(results.length, 1);
        expect(results[0].sessionId, 's1');
      },
    );

    test('empty query with date filter returns sessions in range', () async {
      await createSession('s1', DateTime.utc(2026, 2, 10), summary: 'Early');
      await createSession('s2', DateTime.utc(2026, 2, 20), summary: 'Late');

      final results = await sessionDao.searchSessions(
        '',
        dateStart: DateTime.utc(2026, 2, 15),
      );
      expect(results.length, 1);
      expect(results[0].sessionId, 's2');
    });

    test(
      'empty query with combined mood+topicTags filters applies AND logic',
      () async {
        await createSession(
          's1',
          DateTime.utc(2026, 2, 19),
          summary: 'Focus session',
          moodTags: ['focused'],
          topicTags: ['work'],
        );
        await createSession(
          's2',
          DateTime.utc(2026, 2, 18),
          summary: 'Anxious work',
          moodTags: ['anxious'],
          topicTags: ['work'],
        );
        await createSession(
          's3',
          DateTime.utc(2026, 2, 17),
          summary: 'Focus play',
          moodTags: ['focused'],
          topicTags: ['hobby'],
        );

        // Only s1 has both focused AND work.
        final results = await sessionDao.searchSessions(
          '',
          moodTags: ['focused'],
          topicTags: ['work'],
        );
        expect(results.length, 1);
        expect(results[0].sessionId, 's1');
      },
    );
  });

  // ---------------------------------------------------------------------------
  // Layer 2: Repository — searchEntries early return + message skip
  // ---------------------------------------------------------------------------

  group('SearchRepository.searchEntries — filter-only browse (regression)', () {
    late SearchRepository searchRepo;

    setUp(() {
      searchRepo = SearchRepository(
        sessionDao: sessionDao,
        messageDao: messageDao,
      );
    });

    test(
      'empty query with active mood filter returns results as summary matches',
      () async {
        await createSession(
          's1',
          DateTime.utc(2026, 2, 19),
          summary: 'A happy day',
          moodTags: ['happy'],
        );
        await createSession(
          's2',
          DateTime.utc(2026, 2, 18),
          summary: 'A tough day',
          moodTags: ['anxious'],
        );

        final results = await searchRepo.searchEntries(
          '',
          filters: SearchFilters(moodTags: ['happy']),
        );
        expect(results.count, 1);
        expect(results.items[0].sessionId, 's1');
        expect(results.items[0].matchSource, MatchSource.summary);
        // Filter-only browse returns no snippets (no keyword to highlight).
        expect(results.items[0].matchingSnippets, isEmpty);
      },
    );

    test(
      'empty query with no filters still returns empty results (unchanged behaviour)',
      () async {
        await createSession('s1', DateTime.utc(2026, 2, 19), summary: 'A');
        final results = await searchRepo.searchEntries('');
        expect(results.isEmpty, isTrue);
      },
    );
  });

  // ---------------------------------------------------------------------------
  // Layer 3: Provider — searchResultsProvider early return
  // ---------------------------------------------------------------------------

  group('searchResultsProvider — filter-only browse (regression)', () {
    late ProviderContainer container;

    setUp(() {
      container = ProviderContainer(
        overrides: [databaseProvider.overrideWithValue(database)],
      );
    });

    tearDown(() => container.dispose());

    test(
      'active mood filter with empty query returns matching sessions',
      () async {
        await createSession(
          's1',
          DateTime.utc(2026, 2, 19),
          summary: 'Good day',
          moodTags: ['happy'],
        );
        await createSession(
          's2',
          DateTime.utc(2026, 2, 18),
          summary: 'Rough day',
          moodTags: ['anxious'],
        );

        container.read(searchQueryProvider.notifier).state = '';
        container.read(searchFiltersProvider.notifier).state = SearchFilters(
          moodTags: ['happy'],
        );
        container.invalidate(searchResultsProvider);

        final results = await container.read(searchResultsProvider.future);
        expect(results.count, 1);
        expect(results.items[0].sessionId, 's1');
      },
    );

    test(
      'empty query with no filters returns empty results (unchanged behaviour)',
      () async {
        await createSession('s1', DateTime.utc(2026, 2, 19), summary: 'A');

        container.read(searchQueryProvider.notifier).state = '';
        container.read(searchFiltersProvider.notifier).state =
            SearchFilters.empty;
        container.invalidate(searchResultsProvider);

        final results = await container.read(searchResultsProvider.future);
        expect(results.isEmpty, isTrue);
      },
    );
  });
}
