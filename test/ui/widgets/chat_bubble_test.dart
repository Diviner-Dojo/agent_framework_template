// ===========================================================================
// file: test/ui/widgets/chat_bubble_test.dart
// purpose: Widget tests for the ChatBubble widget — covers recall mode,
//          offline recall, citation chips, photo/video thumbnail branches,
//          and user vs. assistant alignment.
// ===========================================================================

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/ui/widgets/chat_bubble.dart';

void main() {
  Widget wrap(Widget child) {
    return MaterialApp(
      home: Scaffold(body: SingleChildScrollView(child: child)),
    );
  }

  group('ChatBubble — basic rendering', () {
    testWidgets('user message is right-aligned', (tester) async {
      await tester.pumpWidget(
        wrap(
          ChatBubble(
            content: 'Hello',
            role: 'USER',
            timestamp: DateTime.utc(2026, 2, 24, 10, 0),
          ),
        ),
      );
      await tester.pumpAndSettle();

      final row = tester.widget<Row>(find.byType(Row).first);
      expect(row.mainAxisAlignment, MainAxisAlignment.end);
    });

    testWidgets('assistant message is left-aligned', (tester) async {
      await tester.pumpWidget(
        wrap(
          ChatBubble(
            content: 'Hi there!',
            role: 'ASSISTANT',
            timestamp: DateTime.utc(2026, 2, 24, 10, 0),
          ),
        ),
      );
      await tester.pumpAndSettle();

      final row = tester.widget<Row>(find.byType(Row).first);
      expect(row.mainAxisAlignment, MainAxisAlignment.start);
    });

    testWidgets('shows message content and timestamp', (tester) async {
      await tester.pumpWidget(
        wrap(
          ChatBubble(
            content: 'Test message',
            role: 'USER',
            timestamp: DateTime.utc(2026, 2, 24, 10, 30),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Test message'), findsOneWidget);
    });
  });

  group('ChatBubble — recall mode', () {
    testWidgets('shows recall header with history icon', (tester) async {
      await tester.pumpWidget(
        wrap(
          ChatBubble(
            content: 'You mentioned this last week.',
            role: 'ASSISTANT',
            timestamp: DateTime.utc(2026, 2, 24, 10, 0),
            isRecall: true,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('From your journal'), findsOneWidget);
      expect(find.byIcon(Icons.history), findsOneWidget);
    });

    testWidgets('shows citation chips when provided', (tester) async {
      await tester.pumpWidget(
        wrap(
          ChatBubble(
            content: 'Based on your entries...',
            role: 'ASSISTANT',
            timestamp: DateTime.utc(2026, 2, 24, 10, 0),
            isRecall: true,
            citations: const [
              RecallCitation(sessionId: 's1', label: 'Feb 19 — Morning'),
              RecallCitation(sessionId: 's2', label: 'Feb 20 — Evening'),
            ],
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Feb 19 — Morning'), findsOneWidget);
      expect(find.text('Feb 20 — Evening'), findsOneWidget);
      expect(find.text('Based on your entries'), findsOneWidget);
    });

    testWidgets('citation chip calls onCitationTap', (tester) async {
      String? tappedId;
      await tester.pumpWidget(
        wrap(
          ChatBubble(
            content: 'Recall answer',
            role: 'ASSISTANT',
            timestamp: DateTime.utc(2026, 2, 24, 10, 0),
            isRecall: true,
            citations: const [
              RecallCitation(sessionId: 's1', label: 'Session 1'),
            ],
            onCitationTap: (id) => tappedId = id,
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Session 1'));
      expect(tappedId, 's1');
    });

    testWidgets('shows recall footer disclaimer', (tester) async {
      await tester.pumpWidget(
        wrap(
          ChatBubble(
            content: 'Memory answer',
            role: 'ASSISTANT',
            timestamp: DateTime.utc(2026, 2, 24, 10, 0),
            isRecall: true,
            citations: const [
              RecallCitation(sessionId: 's1', label: 'Entry 1'),
            ],
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Based on your entries'), findsOneWidget);
    });
  });

  group('ChatBubble — offline recall', () {
    testWidgets('shows offline recall header with cloud-off icon', (
      tester,
    ) async {
      await tester.pumpWidget(
        wrap(
          ChatBubble(
            content: 'Offline recall content',
            role: 'ASSISTANT',
            timestamp: DateTime.utc(2026, 2, 24, 10, 0),
            isRecall: true,
            isOfflineRecall: true,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('From your journal (offline)'), findsOneWidget);
      expect(find.byIcon(Icons.cloud_off), findsOneWidget);
    });

    testWidgets('shows offline recall footer', (tester) async {
      await tester.pumpWidget(
        wrap(
          ChatBubble(
            content: 'Offline recall',
            role: 'ASSISTANT',
            timestamp: DateTime.utc(2026, 2, 24, 10, 0),
            isRecall: true,
            isOfflineRecall: true,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.textContaining('Full recall synthesis'), findsOneWidget);
    });
  });

  group('ChatBubble — photo thumbnail', () {
    testWidgets('renders photo Semantics when photoPath is set', (
      tester,
    ) async {
      await tester.pumpWidget(
        wrap(
          ChatBubble(
            content: 'Photo message',
            role: 'USER',
            timestamp: DateTime.utc(2026, 2, 24, 10, 0),
            photoPath: '/fake/nonexistent.jpg',
            photoCaption: 'A beautiful sunset',
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Photo caption should be rendered.
      expect(find.text('A beautiful sunset'), findsOneWidget);
      // Semantics label for accessibility.
      expect(
        find.bySemanticsLabel(RegExp('Photo: A beautiful sunset')),
        findsOneWidget,
      );
    });

    testWidgets('photo without caption has generic semantics', (tester) async {
      await tester.pumpWidget(
        wrap(
          ChatBubble(
            content: 'Another photo',
            role: 'USER',
            timestamp: DateTime.utc(2026, 2, 24, 10, 0),
            photoPath: '/fake/none.jpg',
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(
        find.bySemanticsLabel(RegExp('Photo. Tap to view full screen.')),
        findsOneWidget,
      );
    });
  });

  group('ChatBubble — video thumbnail', () {
    testWidgets('renders video Semantics when videoThumbnailPath is set', (
      tester,
    ) async {
      await tester.pumpWidget(
        wrap(
          ChatBubble(
            content: 'Video message',
            role: 'USER',
            timestamp: DateTime.utc(2026, 2, 24, 10, 0),
            videoThumbnailPath: '/fake/thumb.jpg',
            videoDuration: 45,
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Semantics label for accessibility.
      expect(
        find.bySemanticsLabel(RegExp('Video, 45s. Tap to play.')),
        findsOneWidget,
      );
      // Play icon overlay.
      expect(find.byIcon(Icons.play_arrow), findsOneWidget);
    });

    testWidgets('shows duration badge for non-zero duration', (tester) async {
      await tester.pumpWidget(
        wrap(
          ChatBubble(
            content: 'Video clip',
            role: 'USER',
            timestamp: DateTime.utc(2026, 2, 24, 10, 0),
            videoThumbnailPath: '/fake/thumb.jpg',
            videoDuration: 125,
          ),
        ),
      );
      await tester.pumpAndSettle();

      // 125 seconds = 02:05
      expect(find.text('02:05'), findsOneWidget);
    });

    testWidgets('no duration badge when videoDuration is 0', (tester) async {
      await tester.pumpWidget(
        wrap(
          ChatBubble(
            content: 'Zero duration video',
            role: 'USER',
            timestamp: DateTime.utc(2026, 2, 24, 10, 0),
            videoThumbnailPath: '/fake/thumb.jpg',
            videoDuration: 0,
          ),
        ),
      );
      await tester.pumpAndSettle();

      // 0 seconds should not show duration badge.
      expect(find.text('00:00'), findsNothing);
    });

    testWidgets('calls onVideoTap when video is tapped', (tester) async {
      bool tapped = false;
      await tester.pumpWidget(
        wrap(
          ChatBubble(
            content: 'Tappable video',
            role: 'USER',
            timestamp: DateTime.utc(2026, 2, 24, 10, 0),
            videoThumbnailPath: '/fake/thumb.jpg',
            videoDuration: 10,
            onVideoTap: () => tapped = true,
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Tap the play button area (GestureDetector wraps the whole video area).
      await tester.tap(find.byIcon(Icons.play_arrow));
      expect(tapped, isTrue);
    });
  });

  group('ChatBubble — recall border', () {
    testWidgets('recall mode adds left border accent', (tester) async {
      await tester.pumpWidget(
        wrap(
          ChatBubble(
            content: 'Recall bubble',
            role: 'ASSISTANT',
            timestamp: DateTime.utc(2026, 2, 24, 10, 0),
            isRecall: true,
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Find the decorated container and verify it has a border.
      final container = tester
          .widgetList<Container>(find.byType(Container))
          .where((c) => c.decoration is BoxDecoration)
          .where((c) {
            final dec = c.decoration as BoxDecoration;
            return dec.border != null;
          });
      expect(container, isNotEmpty);
    });
  });
}
