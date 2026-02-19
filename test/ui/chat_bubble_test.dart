import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/ui/widgets/chat_bubble.dart';

void main() {
  group('ChatBubble', () {
    testWidgets('user messages are right-aligned', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ChatBubble(
              content: 'Hello from user',
              role: 'USER',
              timestamp: DateTime.utc(2026, 2, 19, 10, 0),
            ),
          ),
        ),
      );

      // Find the Row that controls alignment.
      final rowFinder = find.byType(Row);
      final row = tester.widget<Row>(rowFinder.first);
      expect(row.mainAxisAlignment, MainAxisAlignment.end);
    });

    testWidgets('assistant messages are left-aligned', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ChatBubble(
              content: 'Hello from assistant',
              role: 'ASSISTANT',
              timestamp: DateTime.utc(2026, 2, 19, 10, 0),
            ),
          ),
        ),
      );

      final rowFinder = find.byType(Row);
      final row = tester.widget<Row>(rowFinder.first);
      expect(row.mainAxisAlignment, MainAxisAlignment.start);
    });

    testWidgets('displays message content', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ChatBubble(
              content: 'Test message content',
              role: 'USER',
              timestamp: DateTime.utc(2026, 2, 19, 10, 0),
            ),
          ),
        ),
      );

      expect(find.text('Test message content'), findsOneWidget);
    });
  });
}
