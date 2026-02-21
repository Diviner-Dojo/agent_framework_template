import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/ui/widgets/chat_bubble.dart';

void main() {
  Widget buildBubble({
    String content = 'Test message',
    String role = 'ASSISTANT',
    bool isRecall = false,
    List<RecallCitation> citations = const [],
    bool isOfflineRecall = false,
    void Function(String)? onCitationTap,
  }) {
    return MaterialApp(
      home: Scaffold(
        body: ChatBubble(
          content: content,
          role: role,
          timestamp: DateTime.utc(2026, 2, 19, 10, 0),
          isRecall: isRecall,
          citations: citations,
          onCitationTap: onCitationTap,
          isOfflineRecall: isOfflineRecall,
        ),
      ),
    );
  }

  group('ChatBubble recall mode', () {
    testWidgets('standard assistant bubble has no recall header', (
      tester,
    ) async {
      await tester.pumpWidget(buildBubble());

      expect(find.text('From your journal'), findsNothing);
      expect(find.text('Test message'), findsOneWidget);
    });

    testWidgets('recall mode shows "From your journal" header', (tester) async {
      await tester.pumpWidget(
        buildBubble(
          isRecall: true,
          content: 'You mentioned work stress on Feb 19.',
          citations: [
            RecallCitation(sessionId: 's1', label: 'Feb 19 — Work stress'),
          ],
        ),
      );

      expect(find.text('From your journal'), findsOneWidget);
      expect(find.text('You mentioned work stress on Feb 19.'), findsOneWidget);
    });

    testWidgets('recall mode shows citation chips', (tester) async {
      await tester.pumpWidget(
        buildBubble(
          isRecall: true,
          content: 'Answer here.',
          citations: [
            RecallCitation(sessionId: 's1', label: 'Feb 19 — Morning'),
            RecallCitation(sessionId: 's2', label: 'Feb 18 — Evening'),
          ],
        ),
      );

      expect(find.text('Feb 19 — Morning'), findsOneWidget);
      expect(find.text('Feb 18 — Evening'), findsOneWidget);
    });

    testWidgets('citation chip tap fires callback', (tester) async {
      String? tappedId;
      await tester.pumpWidget(
        buildBubble(
          isRecall: true,
          content: 'Answer.',
          citations: [RecallCitation(sessionId: 's1', label: 'Feb 19')],
          onCitationTap: (id) => tappedId = id,
        ),
      );

      await tester.tap(find.text('Feb 19'));
      expect(tappedId, 's1');
    });

    testWidgets('recall mode shows "Based on your entries" disclaimer', (
      tester,
    ) async {
      await tester.pumpWidget(
        buildBubble(
          isRecall: true,
          content: 'Answer here.',
          citations: [RecallCitation(sessionId: 's1', label: 'Feb 19')],
        ),
      );

      expect(find.text('Based on your entries'), findsOneWidget);
    });

    testWidgets('offline recall shows cloud_off icon and offline message', (
      tester,
    ) async {
      await tester.pumpWidget(
        buildBubble(
          isRecall: true,
          isOfflineRecall: true,
          content: 'Here are matching entries.',
        ),
      );

      expect(find.byIcon(Icons.cloud_off), findsOneWidget);
      expect(find.text('From your journal'), findsNothing);
    });

    testWidgets('offline recall shows offline disclaimer', (tester) async {
      await tester.pumpWidget(
        buildBubble(
          isRecall: true,
          isOfflineRecall: true,
          content: 'Matching entries found.',
        ),
      );

      expect(find.textContaining('Full recall synthesis'), findsOneWidget);
    });

    testWidgets('user bubble is unaffected by recall params', (tester) async {
      await tester.pumpWidget(
        buildBubble(role: 'USER', content: 'What did I do yesterday?'),
      );

      expect(find.text('What did I do yesterday?'), findsOneWidget);
      expect(find.text('From your journal'), findsNothing);
    });

    testWidgets('recall without citations hides disclaimer', (tester) async {
      await tester.pumpWidget(
        buildBubble(
          isRecall: true,
          content: 'I found some entries.',
          citations: [],
        ),
      );

      expect(find.text('Based on your entries'), findsNothing);
    });
  });
}
