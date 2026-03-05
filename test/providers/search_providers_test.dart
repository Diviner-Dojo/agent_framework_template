import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:drift/native.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/providers/database_provider.dart';
import 'package:agentic_journal/models/search_models.dart';
import 'package:agentic_journal/providers/search_providers.dart';
import 'package:agentic_journal/repositories/search_repository.dart';
import 'package:agentic_journal/services/intent_classifier.dart';

void main() {
  late AppDatabase database;
  late ProviderContainer container;

  setUp(() {
    database = AppDatabase.forTesting(NativeDatabase.memory());
    container = ProviderContainer(
      overrides: [databaseProvider.overrideWithValue(database)],
    );
  });

  tearDown(() async {
    container.dispose();
    await database.close();
  });

  group('searchResultsProvider', () {
    test('returns empty results for empty query', () async {
      // searchQueryProvider defaults to '' so results should be empty.
      final results = await container.read(searchResultsProvider.future);
      expect(results.isEmpty, isTrue);
    });
  });

  group('sessionCountProvider', () {
    test('returns 0 when no sessions exist', () async {
      final count = await container.read(sessionCountProvider.future);
      expect(count, 0);
    });

    test('returns correct count after creating sessions', () async {
      final sessionDao = container.read(sessionDaoProvider);
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 19), 'UTC');
      await sessionDao.createSession('s2', DateTime.utc(2026, 2, 18), 'UTC');

      // Force re-read (provider may be cached).
      container.invalidate(sessionCountProvider);
      final count = await container.read(sessionCountProvider.future);
      expect(count, 2);
    });
  });

  group('intentClassifierProvider', () {
    test('returns an IntentClassifier instance', () {
      final classifier = container.read(intentClassifierProvider);
      expect(classifier, isA<IntentClassifier>());
    });

    test('classifier can be overridden for testing', () {
      final mockClassifier = IntentClassifier();
      final overriddenContainer = ProviderContainer(
        overrides: [intentClassifierProvider.overrideWithValue(mockClassifier)],
      );

      final classifier = overriddenContainer.read(intentClassifierProvider);
      expect(identical(classifier, mockClassifier), isTrue);

      overriddenContainer.dispose();
    });
  });

  group('searchQueryProvider', () {
    test('defaults to empty string', () {
      final query = container.read(searchQueryProvider);
      expect(query, '');
    });

    test('can be updated', () {
      container.read(searchQueryProvider.notifier).state = 'test query';
      expect(container.read(searchQueryProvider), 'test query');
    });
  });

  group('searchFiltersProvider', () {
    test('defaults to empty filters', () {
      final filters = container.read(searchFiltersProvider);
      expect(filters.hasActiveFilters, isFalse);
    });

    test('tracks active filters', () {
      container.read(searchFiltersProvider.notifier).state = SearchFilters(
        dateStart: DateTime.utc(2026, 2, 1),
      );
      final filters = container.read(searchFiltersProvider);
      expect(filters.hasActiveFilters, isTrue);
    });
  });

  group('searchResultsProvider — filter-only browse (regression)', () {
    // Regression: searchResultsProvider returned empty when query was empty
    // even when filters were active — the early-return guard did not check
    // filters.hasActiveFilters. Fix: early return only when both are false.
    test('active filter with empty query returns matching sessions', () async {
      final sessionDao = container.read(sessionDaoProvider);
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 19), 'UTC');
      await sessionDao.endSession(
        's1',
        DateTime.utc(2026, 2, 19, 0, 30),
        summary: 'Good day',
        moodTags: '["happy"]',
      );
      await sessionDao.createSession('s2', DateTime.utc(2026, 2, 18), 'UTC');
      await sessionDao.endSession(
        's2',
        DateTime.utc(2026, 2, 18, 0, 30),
        summary: 'Rough day',
        moodTags: '["anxious"]',
      );

      // Empty query but active mood filter.
      container.read(searchQueryProvider.notifier).state = '';
      container.read(searchFiltersProvider.notifier).state = SearchFilters(
        moodTags: ['happy'],
      );
      container.invalidate(searchResultsProvider);
      final results = await container.read(searchResultsProvider.future);
      expect(results.count, 1);
      expect(results.items[0].sessionId, 's1');
    });

    test('empty query with no filters returns empty results', () async {
      final sessionDao = container.read(sessionDaoProvider);
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 19), 'UTC');
      await sessionDao.endSession('s1', DateTime.utc(2026, 2, 19, 0, 30));

      container.read(searchQueryProvider.notifier).state = '';
      container.read(searchFiltersProvider.notifier).state =
          SearchFilters.empty;
      container.invalidate(searchResultsProvider);
      final results = await container.read(searchResultsProvider.future);
      expect(results.isEmpty, isTrue);
    });
  });

  group('searchResultsProvider with data', () {
    test('returns matching results when query matches summary', () async {
      final sessionDao = container.read(sessionDaoProvider);
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 19), 'UTC');
      await sessionDao.endSession(
        's1',
        DateTime.utc(2026, 2, 19, 0, 30),
        summary: 'Work stress and deadlines',
      );

      container.read(searchQueryProvider.notifier).state = 'stress';
      container.invalidate(searchResultsProvider);
      final results = await container.read(searchResultsProvider.future);
      expect(results.count, 1);
      expect(results.items[0].sessionId, 's1');
    });

    test('applies filters to search results', () async {
      final sessionDao = container.read(sessionDaoProvider);
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 10), 'UTC');
      await sessionDao.endSession(
        's1',
        DateTime.utc(2026, 2, 10, 0, 30),
        summary: 'Work in early Feb',
      );
      await sessionDao.createSession('s2', DateTime.utc(2026, 2, 20), 'UTC');
      await sessionDao.endSession(
        's2',
        DateTime.utc(2026, 2, 20, 0, 30),
        summary: 'Work in late Feb',
      );

      container.read(searchQueryProvider.notifier).state = 'Work';
      container.read(searchFiltersProvider.notifier).state = SearchFilters(
        dateStart: DateTime.utc(2026, 2, 15),
      );
      container.invalidate(searchResultsProvider);
      final results = await container.read(searchResultsProvider.future);
      expect(results.count, 1);
      expect(results.items[0].sessionId, 's2');
    });
  });

  group('availableMoodTagsProvider', () {
    test('returns empty list when no mood tags', () async {
      final tags = await container.read(availableMoodTagsProvider.future);
      expect(tags, isEmpty);
    });

    test('returns mood tags from sessions', () async {
      final sessionDao = container.read(sessionDaoProvider);
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 19), 'UTC');
      await sessionDao.endSession(
        's1',
        DateTime.utc(2026, 2, 19, 0, 30),
        moodTags: '["happy","grateful"]',
      );

      container.invalidate(availableMoodTagsProvider);
      final tags = await container.read(availableMoodTagsProvider.future);
      expect(tags, containsAll(['happy', 'grateful']));
    });
  });

  group('availablePeopleProvider', () {
    test('returns people from sessions', () async {
      final sessionDao = container.read(sessionDaoProvider);
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 19), 'UTC');
      await sessionDao.endSession(
        's1',
        DateTime.utc(2026, 2, 19, 0, 30),
        people: '["Mike","Sarah"]',
      );

      container.invalidate(availablePeopleProvider);
      final people = await container.read(availablePeopleProvider.future);
      expect(people, containsAll(['Mike', 'Sarah']));
    });
  });

  group('availableTopicTagsProvider', () {
    test('returns topic tags from sessions', () async {
      final sessionDao = container.read(sessionDaoProvider);
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 19), 'UTC');
      await sessionDao.endSession(
        's1',
        DateTime.utc(2026, 2, 19, 0, 30),
        topicTags: '["work","health"]',
      );

      container.invalidate(availableTopicTagsProvider);
      final topics = await container.read(availableTopicTagsProvider.future);
      expect(topics, containsAll(['work', 'health']));
    });
  });

  group('searchRepositoryProvider', () {
    test('provides a SearchRepository', () {
      final repo = container.read(searchRepositoryProvider);
      expect(repo, isA<SearchRepository>());
    });
  });
}
