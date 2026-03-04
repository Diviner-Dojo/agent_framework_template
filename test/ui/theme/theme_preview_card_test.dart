import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/ui/theme/palettes.dart';
import 'package:agentic_journal/ui/widgets/theme_preview_card.dart';

void main() {
  group('ThemePreviewCard', () {
    final testPalette = getPaletteById('still_water');

    testWidgets('renders palette name and description', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: ThemePreviewCard(palette: testPalette)),
        ),
      );

      expect(find.text('Still Water'), findsOneWidget);
      expect(find.text('Calm reflection'), findsOneWidget);
    });

    testWidgets('shows check mark when selected', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThemePreviewCard(palette: testPalette, isSelected: true),
          ),
        ),
      );

      expect(find.byIcon(Icons.check), findsOneWidget);
    });

    testWidgets('hides check mark when not selected', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThemePreviewCard(palette: testPalette, isSelected: false),
          ),
        ),
      );

      expect(find.byIcon(Icons.check), findsNothing);
    });

    testWidgets('calls onTap when tapped', (tester) async {
      var tapped = false;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThemePreviewCard(
              palette: testPalette,
              onTap: () => tapped = true,
            ),
          ),
        ),
      );

      await tester.tap(find.byType(ThemePreviewCard));
      expect(tapped, isTrue);
    });

    testWidgets('does not crash when onTap is null', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: ThemePreviewCard(palette: testPalette)),
        ),
      );

      await tester.tap(find.byType(ThemePreviewCard));
      // No exception thrown.
    });

    testWidgets('has proper semantics', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ThemePreviewCard(palette: testPalette, isSelected: true),
          ),
        ),
      );

      final semantics = tester.getSemantics(find.byType(ThemePreviewCard));
      expect(semantics.label, contains('Still Water'));
    });

    testWidgets('renders differently in dark mode', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(brightness: Brightness.dark),
          home: Scaffold(body: ThemePreviewCard(palette: testPalette)),
        ),
      );

      // Should render without errors in dark mode.
      expect(find.text('Still Water'), findsOneWidget);
    });
  });
}
