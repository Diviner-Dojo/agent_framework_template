import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/ui/widgets/end_session_button.dart';

void main() {
  group('EndSessionButton', () {
    testWidgets('tap shows confirmation dialog', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            appBar: AppBar(actions: [EndSessionButton(onEndSession: () {})]),
          ),
        ),
      );

      // Tap the button.
      await tester.tap(find.byType(IconButton));
      await tester.pumpAndSettle();

      // Dialog should appear.
      expect(find.text('End session?'), findsOneWidget);
      expect(find.text('Cancel'), findsOneWidget);
      expect(find.text('End'), findsOneWidget);
    });

    testWidgets('Cancel dismisses dialog without calling callback', (
      tester,
    ) async {
      bool callbackCalled = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            appBar: AppBar(
              actions: [
                EndSessionButton(onEndSession: () => callbackCalled = true),
              ],
            ),
          ),
        ),
      );

      // Open dialog.
      await tester.tap(find.byType(IconButton));
      await tester.pumpAndSettle();

      // Tap Cancel.
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      // Dialog should be dismissed, callback NOT called.
      expect(find.text('End session?'), findsNothing);
      expect(callbackCalled, isFalse);
    });

    testWidgets('End button calls the callback', (tester) async {
      bool callbackCalled = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            appBar: AppBar(
              actions: [
                EndSessionButton(onEndSession: () => callbackCalled = true),
              ],
            ),
          ),
        ),
      );

      // Open dialog.
      await tester.tap(find.byType(IconButton));
      await tester.pumpAndSettle();

      // Tap End.
      await tester.tap(find.text('End'));
      await tester.pumpAndSettle();

      // Callback should have been called.
      expect(callbackCalled, isTrue);
    });
  });
}
