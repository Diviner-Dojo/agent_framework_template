import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/models/search_models.dart';
import 'package:agentic_journal/ui/widgets/search_result_card.dart';

void main() {
  /// Create a JournalSession for testing.
  JournalSession makeSession({
    String id = 's1',
    DateTime? startTime,
    DateTime? endTime,
    String? summary,
    String? moodTags,
    String? people,
    String? topicTags,
  }) {
    return JournalSession(
      sessionId: id,
      startTime: startTime ?? DateTime.utc(2026, 2, 19, 10, 0),
      endTime: endTime ?? DateTime.utc(2026, 2, 19, 10, 30),
      timezone: 'UTC',
      summary: summary,
      moodTags: moodTags,
      people: people,
      topicTags: topicTags,
      syncStatus: 'PENDING',
      isResumed: false,
      resumeCount: 0,
      createdAt: DateTime.utc(2026, 2, 19, 10, 0),
      updatedAt: DateTime.utc(2026, 2, 19, 10, 0),
    );
  }

  Widget buildCard(SearchResultItem item, String query) {
    return MaterialApp(
      home: Scaffold(
        body: SearchResultCard(item: item, query: query),
      ),
    );
  }

  group('SearchResultCard', () {
    testWidgets('displays date and match source label', (tester) async {
      final item = SearchResultItem(
        sessionId: 's1',
        session: makeSession(summary: 'A great day'),
        matchingSnippets: ['I had a great day at work'],
        matchSource: MatchSource.summary,
      );

      await tester.pumpWidget(buildCard(item, 'great'));

      expect(find.text('Summary'), findsOneWidget);
    });

    testWidgets('displays Conversation for message match', (tester) async {
      final item = SearchResultItem(
        sessionId: 's1',
        session: makeSession(summary: 'A normal day'),
        matchingSnippets: ['I felt great today'],
        matchSource: MatchSource.message,
      );

      await tester.pumpWidget(buildCard(item, 'great'));

      expect(find.text('Conversation'), findsOneWidget);
    });

    testWidgets('bolds search keyword in snippet', (tester) async {
      final item = SearchResultItem(
        sessionId: 's1',
        session: makeSession(),
        matchingSnippets: ['I felt anxious about work'],
        matchSource: MatchSource.message,
      );

      await tester.pumpWidget(buildCard(item, 'anxious'));

      // RichText should contain the snippet text.
      expect(find.byType(RichText), findsWidgets);
    });

    testWidgets('shows summary when no snippets available', (tester) async {
      final item = SearchResultItem(
        sessionId: 's1',
        session: makeSession(summary: 'A productive day at work'),
        matchingSnippets: [],
        matchSource: MatchSource.summary,
      );

      await tester.pumpWidget(buildCard(item, 'work'));

      expect(find.text('A productive day at work'), findsOneWidget);
    });

    testWidgets('displays mood chips when moodTags present', (tester) async {
      final item = SearchResultItem(
        sessionId: 's1',
        session: makeSession(moodTags: '["happy","grateful"]'),
        matchingSnippets: ['A great day'],
        matchSource: MatchSource.summary,
      );

      await tester.pumpWidget(buildCard(item, 'great'));

      expect(find.text('happy'), findsOneWidget);
      expect(find.text('grateful'), findsOneWidget);
    });

    testWidgets('displays people chips when people present', (tester) async {
      final item = SearchResultItem(
        sessionId: 's1',
        session: makeSession(people: '["Mike","Sarah"]'),
        matchingSnippets: ['Meeting notes'],
        matchSource: MatchSource.summary,
      );

      await tester.pumpWidget(buildCard(item, 'Meeting'));

      expect(find.text('Mike'), findsOneWidget);
      expect(find.text('Sarah'), findsOneWidget);
    });

    testWidgets('handles null metadata gracefully', (tester) async {
      final item = SearchResultItem(
        sessionId: 's1',
        session: makeSession(),
        matchingSnippets: ['Some text'],
        matchSource: MatchSource.summary,
      );

      await tester.pumpWidget(buildCard(item, 'text'));

      // Should render without error.
      expect(find.byType(SearchResultCard), findsOneWidget);
    });

    testWidgets('onTap callback fires when tapped', (tester) async {
      var tapped = false;
      final item = SearchResultItem(
        sessionId: 's1',
        session: makeSession(summary: 'Tap me'),
        matchingSnippets: ['Tap me'],
        matchSource: MatchSource.summary,
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SearchResultCard(
              item: item,
              query: 'Tap',
              onTap: () => tapped = true,
            ),
          ),
        ),
      );

      await tester.tap(find.byType(SearchResultCard));
      expect(tapped, isTrue);
    });
  });
}
