import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:drift/native.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';
import 'package:agentic_journal/database/daos/message_dao.dart';
import 'package:agentic_journal/models/search_models.dart';
import 'package:agentic_journal/repositories/search_repository.dart';

void main() {
  late AppDatabase database;
  late SessionDao sessionDao;
  late MessageDao messageDao;
  late SearchRepository searchRepo;

  setUp(() {
    database = AppDatabase.forTesting(NativeDatabase.memory());
    sessionDao = SessionDao(database);
    messageDao = MessageDao(database);
    searchRepo = SearchRepository(
      sessionDao: sessionDao,
      messageDao: messageDao,
    );
  });

  tearDown(() async {
    await database.close();
  });

  /// Helper: create a session with messages and metadata.
  Future<void> createSessionWith({
    required String id,
    required DateTime startTime,
    String? summary,
    List<String>? moodTags,
    List<String> messages = const [],
  }) async {
    await sessionDao.createSession(id, startTime, 'UTC');
    await sessionDao.endSession(
      id,
      startTime.add(const Duration(minutes: 30)),
      summary: summary,
      moodTags: moodTags != null ? jsonEncode(moodTags) : null,
    );
    for (var i = 0; i < messages.length; i++) {
      await messageDao.insertMessage(
        '$id-m$i',
        id,
        'USER',
        messages[i],
        startTime.add(Duration(minutes: i)),
      );
    }
  }

  group('SearchRepository.searchEntries', () {
    test('empty query returns empty results', () async {
      final results = await searchRepo.searchEntries('');
      expect(results.isEmpty, isTrue);
    });

    test('whitespace-only query returns empty results', () async {
      final results = await searchRepo.searchEntries('   ');
      expect(results.isEmpty, isTrue);
    });

    test('finds session by summary match', () async {
      await createSessionWith(
        id: 's1',
        startTime: DateTime.utc(2026, 2, 19),
        summary: 'Great day at work',
      );

      final results = await searchRepo.searchEntries('work');
      expect(results.count, 1);
      expect(results.items[0].sessionId, 's1');
      expect(results.items[0].matchSource, MatchSource.summary);
    });

    test('finds session by message match', () async {
      await createSessionWith(
        id: 's1',
        startTime: DateTime.utc(2026, 2, 19),
        summary: 'A normal day',
        messages: ['I feel anxious about the deadline'],
      );

      final results = await searchRepo.searchEntries('anxious');
      expect(results.count, 1);
      expect(results.items[0].matchSource, MatchSource.message);
    });

    test(
      'dedup: session matching both summary and message appears once as summary',
      () async {
        await createSessionWith(
          id: 's1',
          startTime: DateTime.utc(2026, 2, 19),
          summary: 'Work stress today',
          messages: ['Work was really stressful today'],
        );

        final results = await searchRepo.searchEntries('Work');
        expect(results.count, 1);
        expect(results.items[0].matchSource, MatchSource.summary);
      },
    );

    test('summary match ranks above message-only match', () async {
      // s1 matches in summary, s2 matches only in messages.
      await createSessionWith(
        id: 's1',
        startTime: DateTime.utc(2026, 2, 18),
        summary: 'Talked about exercise today',
      );
      await createSessionWith(
        id: 's2',
        startTime: DateTime.utc(2026, 2, 19),
        summary: 'A normal day',
        messages: ['Did some exercise in the morning'],
      );

      final results = await searchRepo.searchEntries('exercise');
      expect(results.count, 2);
      // Summary match first regardless of date.
      expect(results.items[0].matchSource, MatchSource.summary);
      expect(results.items[0].sessionId, 's1');
      expect(results.items[1].matchSource, MatchSource.message);
    });

    test('filters are applied to search', () async {
      await createSessionWith(
        id: 's1',
        startTime: DateTime.utc(2026, 2, 10),
        summary: 'Work day in early Feb',
      );
      await createSessionWith(
        id: 's2',
        startTime: DateTime.utc(2026, 2, 20),
        summary: 'Work day in late Feb',
      );

      final results = await searchRepo.searchEntries(
        'Work',
        filters: SearchFilters(dateStart: DateTime.utc(2026, 2, 15)),
      );
      expect(results.count, 1);
      expect(results.items[0].sessionId, 's2');
    });
  });

  group('SearchRepository.getSessionContext', () {
    test('formats session context as maps', () async {
      await createSessionWith(
        id: 's1',
        startTime: DateTime.utc(2026, 2, 19),
        summary: 'A good day',
        messages: ['I felt great today', 'Work was productive'],
      );

      final context = await searchRepo.getSessionContext(['s1']);
      expect(context.length, 1);
      expect(context[0]['session_id'], 's1');
      expect(context[0]['session_date'], isNotNull);
      expect(context[0]['summary'], 'A good day');
      expect(context[0]['snippets'], isA<List>());
      expect((context[0]['snippets'] as List).length, 2);
    });

    test('enforces 10-session cap', () async {
      // Create 15 sessions.
      for (var i = 0; i < 15; i++) {
        await createSessionWith(
          id: 's$i',
          startTime: DateTime.utc(2026, 2, 1 + i),
          summary: 'Session $i',
          messages: ['Message in session $i'],
        );
      }

      final ids = List.generate(15, (i) => 's$i');
      final context = await searchRepo.getSessionContext(ids);
      expect(context.length, 10);
    });

    test('truncates summary to max length', () async {
      final longSummary = 'A' * 1000;
      await createSessionWith(
        id: 's1',
        startTime: DateTime.utc(2026, 2, 19),
        summary: longSummary,
      );

      final context = await searchRepo.getSessionContext(['s1']);
      expect((context[0]['summary'] as String).length, lessThanOrEqualTo(500));
    });

    test('limits snippets per session', () async {
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 19), 'UTC');
      await sessionDao.endSession(
        's1',
        DateTime.utc(2026, 2, 19, 1),
        summary: 'Session with many messages',
      );
      // Insert 10 user messages.
      for (var i = 0; i < 10; i++) {
        await messageDao.insertMessage(
          's1-m$i',
          's1',
          'USER',
          'User message number $i with some content',
          DateTime.utc(2026, 2, 19, 0, i),
        );
      }

      final context = await searchRepo.getSessionContext(['s1']);
      expect((context[0]['snippets'] as List).length, lessThanOrEqualTo(5));
    });

    test('skips missing sessions', () async {
      final context = await searchRepo.getSessionContext(['nonexistent-id']);
      expect(context, isEmpty);
    });

    test('only includes USER messages in snippets', () async {
      await sessionDao.createSession('s1', DateTime.utc(2026, 2, 19), 'UTC');
      await sessionDao.endSession(
        's1',
        DateTime.utc(2026, 2, 19, 1),
        summary: 'Session',
      );
      await messageDao.insertMessage(
        'm1',
        's1',
        'USER',
        'My journal thought',
        DateTime.utc(2026, 2, 19, 0, 1),
      );
      await messageDao.insertMessage(
        'm2',
        's1',
        'ASSISTANT',
        'How did that make you feel?',
        DateTime.utc(2026, 2, 19, 0, 2),
      );

      final context = await searchRepo.getSessionContext(['s1']);
      final snippets = context[0]['snippets'] as List;
      // Only USER message should be included.
      expect(snippets.length, 1);
      expect(snippets[0], 'My journal thought');
    });
  });
}
