import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/models/search_models.dart';

void main() {
  JournalSession makeSession({String id = 's1'}) {
    return JournalSession(
      sessionId: id,
      startTime: DateTime.utc(2026, 2, 19, 10, 0),
      timezone: 'UTC',
      syncStatus: 'PENDING',
      createdAt: DateTime.utc(2026, 2, 19),
      updatedAt: DateTime.utc(2026, 2, 19),
    );
  }

  group('SearchFilters', () {
    test('empty has no active filters', () {
      expect(SearchFilters.empty.hasActiveFilters, isFalse);
    });

    test('dateStart activates filters', () {
      final f = SearchFilters(dateStart: DateTime.utc(2026, 2, 1));
      expect(f.hasActiveFilters, isTrue);
    });

    test('dateEnd activates filters', () {
      final f = SearchFilters(dateEnd: DateTime.utc(2026, 2, 28));
      expect(f.hasActiveFilters, isTrue);
    });

    test('moodTags activates filters when non-empty', () {
      final f = SearchFilters(moodTags: ['happy']);
      expect(f.hasActiveFilters, isTrue);
    });

    test('empty moodTags list does not activate filters', () {
      final f = SearchFilters(moodTags: []);
      expect(f.hasActiveFilters, isFalse);
    });

    test('people activates filters', () {
      final f = SearchFilters(people: ['Mike']);
      expect(f.hasActiveFilters, isTrue);
    });

    test('topicTags activates filters', () {
      final f = SearchFilters(topicTags: ['work']);
      expect(f.hasActiveFilters, isTrue);
    });
  });

  group('SearchResults', () {
    test('empty by default', () {
      const results = SearchResults();
      expect(results.isEmpty, isTrue);
      expect(results.count, 0);
    });

    test('count returns item count', () {
      final results = SearchResults(
        query: 'test',
        items: [
          SearchResultItem(
            sessionId: 's1',
            session: makeSession(),
            matchSource: MatchSource.summary,
          ),
          SearchResultItem(
            sessionId: 's2',
            session: makeSession(id: 's2'),
            matchSource: MatchSource.message,
          ),
        ],
      );
      expect(results.count, 2);
      expect(results.isEmpty, isFalse);
    });
  });

  group('SearchResultItem', () {
    test('default snippets is empty list', () {
      final item = SearchResultItem(
        sessionId: 's1',
        session: makeSession(),
        matchSource: MatchSource.summary,
      );
      expect(item.matchingSnippets, isEmpty);
    });

    test('stores snippets', () {
      final item = SearchResultItem(
        sessionId: 's1',
        session: makeSession(),
        matchingSnippets: ['snippet 1', 'snippet 2'],
        matchSource: MatchSource.message,
      );
      expect(item.matchingSnippets, hasLength(2));
    });
  });

  group('RecallResponse', () {
    test('default cited sessions is empty', () {
      const response = RecallResponse(answer: 'Test answer');
      expect(response.citedSessionIds, isEmpty);
    });

    test('stores cited session IDs', () {
      const response = RecallResponse(
        answer: 'You talked about work.',
        citedSessionIds: ['s1', 's2'],
      );
      expect(response.answer, 'You talked about work.');
      expect(response.citedSessionIds, hasLength(2));
    });
  });
}
