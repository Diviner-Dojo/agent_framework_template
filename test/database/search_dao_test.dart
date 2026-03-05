import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:drift/native.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';
import 'package:agentic_journal/database/daos/message_dao.dart';

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

  /// Helper: create a session with optional metadata.
  Future<void> createSessionWithMetadata(
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

  group('SessionDao.searchSessions', () {
    test('finds session by summary keyword', () async {
      await createSessionWithMetadata(
        's1',
        DateTime.utc(2026, 2, 19),
        summary: 'Great day at work with the team',
      );
      await createSessionWithMetadata(
        's2',
        DateTime.utc(2026, 2, 18),
        summary: 'Feeling tired and stressed',
      );

      final results = await sessionDao.searchSessions('work');
      expect(results.length, 1);
      expect(results[0].sessionId, 's1');
    });

    test('case-insensitive search', () async {
      await createSessionWithMetadata(
        's1',
        DateTime.utc(2026, 2, 19),
        summary: 'Talked about ANXIETY today',
      );

      final results = await sessionDao.searchSessions('anxiety');
      expect(results.length, 1);
    });

    test(
      'LIKE wildcard escaping: search for "100%" returns correct results',
      () async {
        await createSessionWithMetadata(
          's1',
          DateTime.utc(2026, 2, 19),
          summary: 'Gave 100% effort today',
        );
        await createSessionWithMetadata(
          's2',
          DateTime.utc(2026, 2, 18),
          summary: 'A regular day with nothing special',
        );

        final results = await sessionDao.searchSessions('100%');
        expect(results.length, 1);
        expect(results[0].sessionId, 's1');
      },
    );

    test('LIKE wildcard escaping: underscore in search', () async {
      await createSessionWithMetadata(
        's1',
        DateTime.utc(2026, 2, 19),
        summary: 'Used my_variable in code today',
      );
      await createSessionWithMetadata(
        's2',
        DateTime.utc(2026, 2, 18),
        summary: 'A normal summary with my thoughts',
      );

      final results = await sessionDao.searchSessions('my_');
      expect(results.length, 1);
      expect(results[0].sessionId, 's1');
    });

    test('searches moodTags column', () async {
      await createSessionWithMetadata(
        's1',
        DateTime.utc(2026, 2, 19),
        summary: 'A day',
        moodTags: ['happy', 'grateful'],
      );

      final results = await sessionDao.searchSessions('grateful');
      expect(results.length, 1);
    });

    test('searches people column', () async {
      await createSessionWithMetadata(
        's1',
        DateTime.utc(2026, 2, 19),
        summary: 'Meeting notes',
        people: ['Mike', 'Sarah'],
      );

      final results = await sessionDao.searchSessions('Sarah');
      expect(results.length, 1);
    });

    test('date range filter', () async {
      await createSessionWithMetadata(
        's1',
        DateTime.utc(2026, 2, 10),
        summary: 'Work day in early Feb',
      );
      await createSessionWithMetadata(
        's2',
        DateTime.utc(2026, 2, 20),
        summary: 'Work day in late Feb',
      );

      final results = await sessionDao.searchSessions(
        'Work',
        dateStart: DateTime.utc(2026, 2, 15),
        dateEnd: DateTime.utc(2026, 2, 25),
      );
      expect(results.length, 1);
      expect(results[0].sessionId, 's2');
    });

    test('mood tag filter', () async {
      await createSessionWithMetadata(
        's1',
        DateTime.utc(2026, 2, 19),
        summary: 'Good day',
        moodTags: ['happy'],
      );
      await createSessionWithMetadata(
        's2',
        DateTime.utc(2026, 2, 18),
        summary: 'Good day too',
        moodTags: ['sad'],
      );

      final results = await sessionDao.searchSessions(
        'day',
        moodTags: ['happy'],
      );
      expect(results.length, 1);
      expect(results[0].sessionId, 's1');
    });

    test('combined filters: date + mood + people', () async {
      await createSessionWithMetadata(
        's1',
        DateTime.utc(2026, 2, 19),
        summary: 'Meeting with team',
        moodTags: ['focused'],
        people: ['Mike'],
      );
      await createSessionWithMetadata(
        's2',
        DateTime.utc(2026, 2, 18),
        summary: 'Meeting with clients',
        moodTags: ['anxious'],
        people: ['Mike'],
      );

      final results = await sessionDao.searchSessions(
        'Meeting',
        dateStart: DateTime.utc(2026, 2, 19),
        moodTags: ['focused'],
        people: ['Mike'],
      );
      expect(results.length, 1);
      expect(results[0].sessionId, 's1');
    });

    test('empty results for no matches', () async {
      await createSessionWithMetadata(
        's1',
        DateTime.utc(2026, 2, 19),
        summary: 'A normal day',
      );

      final results = await sessionDao.searchSessions('nonexistent');
      expect(results, isEmpty);
    });

    test(
      'session with null metadata fields handles filter gracefully',
      () async {
        await createSessionWithMetadata(
          's1',
          DateTime.utc(2026, 2, 19),
          summary: 'Day without metadata',
        );

        // Mood filter should exclude sessions with null moodTags.
        final results = await sessionDao.searchSessions(
          'Day',
          moodTags: ['happy'],
        );
        expect(results, isEmpty);
      },
    );

    // Regression: filter-only browse (empty query + active filter) was
    // returning empty results because the keyword LIKE clause was always
    // required. Fix: keyword constraint is only added when query is non-empty.
    test(
      'filter-only browse: empty query with mood filter returns matching sessions (regression)',
      () async {
        await createSessionWithMetadata(
          's1',
          DateTime.utc(2026, 2, 19),
          summary: 'Happy day',
          moodTags: ['happy'],
        );
        await createSessionWithMetadata(
          's2',
          DateTime.utc(2026, 2, 18),
          summary: 'Sad day',
          moodTags: ['sad'],
        );

        // Empty query + mood filter — should return only 'happy' session.
        final results = await sessionDao.searchSessions(
          '',
          moodTags: ['happy'],
        );
        expect(results.length, 1);
        expect(results[0].sessionId, 's1');
      },
    );

    test(
      'filter-only browse: empty query with date filter returns all sessions in range (regression)',
      () async {
        await createSessionWithMetadata(
          's1',
          DateTime.utc(2026, 2, 10),
          summary: 'Early',
        );
        await createSessionWithMetadata(
          's2',
          DateTime.utc(2026, 2, 20),
          summary: 'Late',
        );

        final results = await sessionDao.searchSessions(
          '',
          dateStart: DateTime.utc(2026, 2, 15),
        );
        expect(results.length, 1);
        expect(results[0].sessionId, 's2');
      },
    );

    test(
      'filter-only browse: empty query with no filters returns all sessions (regression)',
      () async {
        await createSessionWithMetadata(
          's1',
          DateTime.utc(2026, 2, 19),
          summary: 'A',
        );
        await createSessionWithMetadata(
          's2',
          DateTime.utc(2026, 2, 18),
          summary: 'B',
        );

        // Both callers guard against this, but the DAO handles it gracefully.
        final results = await sessionDao.searchSessions('');
        expect(results.length, 2);
      },
    );
  });

  group('SessionDao.getDistinctMoodTags', () {
    test('returns distinct mood tags across sessions', () async {
      await createSessionWithMetadata(
        's1',
        DateTime.utc(2026, 2, 19),
        summary: 'Day 1',
        moodTags: ['happy', 'grateful'],
      );
      await createSessionWithMetadata(
        's2',
        DateTime.utc(2026, 2, 18),
        summary: 'Day 2',
        moodTags: ['happy', 'tired'],
      );

      final tags = await sessionDao.getDistinctMoodTags();
      expect(tags, containsAll(['happy', 'grateful', 'tired']));
      // No duplicates — 'happy' appears only once.
      expect(tags.where((t) => t == 'happy').length, 1);
    });

    test('returns empty list when no mood tags exist', () async {
      await createSessionWithMetadata(
        's1',
        DateTime.utc(2026, 2, 19),
        summary: 'No tags',
      );

      final tags = await sessionDao.getDistinctMoodTags();
      expect(tags, isEmpty);
    });
  });

  group('SessionDao.getDistinctPeople', () {
    test('returns distinct people across sessions', () async {
      await createSessionWithMetadata(
        's1',
        DateTime.utc(2026, 2, 19),
        summary: 'Day',
        people: ['Mike', 'Sarah'],
      );
      await createSessionWithMetadata(
        's2',
        DateTime.utc(2026, 2, 18),
        summary: 'Day',
        people: ['Mike', 'Tom'],
      );

      final people = await sessionDao.getDistinctPeople();
      expect(people, containsAll(['Mike', 'Sarah', 'Tom']));
      expect(people.where((p) => p == 'Mike').length, 1);
    });
  });

  group('SessionDao.getDistinctTopicTags', () {
    test('returns distinct topic tags across sessions', () async {
      await createSessionWithMetadata(
        's1',
        DateTime.utc(2026, 2, 19),
        summary: 'Day',
        topicTags: ['work', 'health'],
      );

      final topics = await sessionDao.getDistinctTopicTags();
      expect(topics, containsAll(['work', 'health']));
    });
  });

  group('SessionDao.countSessions', () {
    test('returns 0 when no sessions exist', () async {
      final count = await sessionDao.countSessions();
      expect(count, 0);
    });

    test('returns correct count', () async {
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 19), 'UTC');
      await sessionDao.createSession('s2', DateTime.utc(2026, 2, 18), 'UTC');

      final count = await sessionDao.countSessions();
      expect(count, 2);
    });
  });

  group('MessageDao.searchMessages', () {
    test('finds messages by content keyword', () async {
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 19), 'UTC');
      await messageDao.insertMessage(
        'm1',
        's1',
        'USER',
        'I feel anxious about work',
        DateTime.utc(2026, 2, 19),
      );
      await messageDao.insertMessage(
        'm2',
        's1',
        'USER',
        'The weather is nice today',
        DateTime.utc(2026, 2, 19),
      );

      final results = await messageDao.searchMessages('anxious');
      expect(results.length, 1);
      expect(results[0].messageId, 'm1');
    });

    test('case-insensitive content search', () async {
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 19), 'UTC');
      await messageDao.insertMessage(
        'm1',
        's1',
        'USER',
        'Feeling GREAT today',
        DateTime.utc(2026, 2, 19),
      );

      final results = await messageDao.searchMessages('great');
      expect(results.length, 1);
    });

    test('scoped to specific session', () async {
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 19), 'UTC');
      await sessionDao.createSession('s2', DateTime.utc(2026, 2, 18), 'UTC');
      await messageDao.insertMessage(
        'm1',
        's1',
        'USER',
        'Work was stressful',
        DateTime.utc(2026, 2, 19),
      );
      await messageDao.insertMessage(
        'm2',
        's2',
        'USER',
        'Work was fun',
        DateTime.utc(2026, 2, 18),
      );

      final results = await messageDao.searchMessages('Work', sessionId: 's1');
      expect(results.length, 1);
      expect(results[0].sessionId, 's1');
    });

    test('LIKE wildcard escaping in message search', () async {
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 19), 'UTC');
      await messageDao.insertMessage(
        'm1',
        's1',
        'USER',
        'Score was 95%',
        DateTime.utc(2026, 2, 19),
      );
      await messageDao.insertMessage(
        'm2',
        's1',
        'USER',
        'A random message',
        DateTime.utc(2026, 2, 19),
      );

      final results = await messageDao.searchMessages('95%');
      expect(results.length, 1);
    });
  });

  group('MessageDao.getMessageSnippets', () {
    test('returns snippets around keyword match', () async {
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 19), 'UTC');
      await messageDao.insertMessage(
        'm1',
        's1',
        'USER',
        'I was walking in the park and thinking about how work has been '
            'really stressful lately with all the deadlines and meetings',
        DateTime.utc(2026, 2, 19),
      );

      final snippets = await messageDao.getMessageSnippets('s1', 'stressful');
      expect(snippets, isNotEmpty);
      expect(snippets.first, contains('stressful'));
    });

    test('returns max 2 snippets per session', () async {
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 19), 'UTC');
      // Create 5 messages all mentioning the keyword.
      for (var i = 0; i < 5; i++) {
        await messageDao.insertMessage(
          'm$i',
          's1',
          'USER',
          'Message $i about feeling anxious and worried about the future',
          DateTime.utc(2026, 2, 19, 10, i),
        );
      }

      final snippets = await messageDao.getMessageSnippets('s1', 'anxious');
      expect(snippets.length, lessThanOrEqualTo(2));
    });

    test('returns empty list for no matches', () async {
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 19), 'UTC');
      await messageDao.insertMessage(
        'm1',
        's1',
        'USER',
        'A normal message',
        DateTime.utc(2026, 2, 19),
      );

      final snippets = await messageDao.getMessageSnippets('s1', 'nonexistent');
      expect(snippets, isEmpty);
    });
  });

  group('MessageDao.insertMessage with entitiesJson', () {
    test('stores entitiesJson when provided', () async {
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 19), 'UTC');
      final metadata = jsonEncode({
        'type': 'recall',
        'cited_sessions': ['s2'],
      });
      await messageDao.insertMessage(
        'm1',
        's1',
        'ASSISTANT',
        'Here is what I found',
        DateTime.utc(2026, 2, 19),
        entitiesJson: metadata,
      );

      final messages = await messageDao.getMessagesForSession('s1');
      expect(messages.length, 1);
      expect(messages[0].entitiesJson, metadata);
    });

    test('entitiesJson is null by default', () async {
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 19), 'UTC');
      await messageDao.insertMessage(
        'm1',
        's1',
        'USER',
        'Hello',
        DateTime.utc(2026, 2, 19),
      );

      final messages = await messageDao.getMessagesForSession('s1');
      expect(messages[0].entitiesJson, isNull);
    });
  });
}
