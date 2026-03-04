// ===========================================================================
// file: test/ui/quick_capture_palette_test.dart
// purpose: Widget tests for QuickCapturePalette (Phase 3A Quick Capture Mode).
//
// Tests cover:
//   - All four mode tiles render with correct labels (Photo absent until
//     camera dispatch is implemented — see Bug 2 in BUILD_STATUS.md)
//   - No tile is highlighted when lastMode is null
//   - Tile matching lastMode is highlighted (primaryContainer background)
//   - Tapping each tile pops with the correct mode key
//   - Unknown lastMode value does not highlight any tile
//   - ADHD copy is present ("What's on your mind?", "A few words is enough.")
//
// See: lib/ui/widgets/quick_capture_palette.dart, SPEC-20260302 Phase 3A
// ===========================================================================

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/ui/widgets/quick_capture_palette.dart';

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

/// Pump a MaterialApp that shows [showQuickCapturePalette] via a button tap.
Future<String?> _openPalette(WidgetTester tester, {String? lastMode}) async {
  String? result;

  await tester.pumpWidget(
    MaterialApp(
      home: Builder(
        builder: (context) => Scaffold(
          body: ElevatedButton(
            onPressed: () async {
              result = await showQuickCapturePalette(
                context,
                lastMode: lastMode,
              );
            },
            child: const Text('Open'),
          ),
        ),
      ),
    ),
  );

  await tester.tap(find.text('Open'));
  await tester.pumpAndSettle();

  return result;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void main() {
  group('QuickCapturePalette', () {
    testWidgets('renders ADHD header copy', (tester) async {
      await _openPalette(tester);

      expect(find.text("What's on your mind?"), findsOneWidget);
      expect(find.text('A few words is enough.'), findsOneWidget);
    });

    testWidgets('renders all four mode labels', (tester) async {
      await _openPalette(tester);

      expect(find.text('Write'), findsOneWidget);
      expect(find.text('Voice'), findsOneWidget);
      expect(find.text('Mood Tap'), findsOneWidget);
      expect(find.text('Check-In'), findsOneWidget);
      // Photo tile is intentionally absent until camera-open dispatch is
      // implemented (see Bug 2 in BUILD_STATUS.md).
      expect(find.text('Photo'), findsNothing);
    });

    testWidgets('no tile is highlighted when lastMode is null', (tester) async {
      await _openPalette(tester, lastMode: null);

      // No primaryContainer-colored Material should appear (all tiles use
      // surfaceContainerHighest when none is highlighted).
      // We verify by checking that the Semantics labels do not include
      // ', last used' for any tile.
      final semanticsLabels = tester
          .widgetList<Semantics>(find.byType(Semantics))
          .where((s) => s.properties.label?.contains(', last used') == true)
          .toList();
      expect(semanticsLabels, isEmpty);
    });

    testWidgets('tile matching lastMode has ", last used" semantics label', (
      tester,
    ) async {
      await _openPalette(tester, lastMode: 'voice');

      final lastUsedSemantics = tester
          .widgetList<Semantics>(find.byType(Semantics))
          .where((s) => s.properties.label?.contains(', last used') == true)
          .toList();

      expect(lastUsedSemantics, hasLength(1));
      expect(lastUsedSemantics.first.properties.label, contains('Voice'));
    });

    testWidgets('tapping Write returns "text"', (tester) async {
      String? result;

      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (context) => Scaffold(
              body: ElevatedButton(
                onPressed: () async {
                  result = await showQuickCapturePalette(context);
                },
                child: const Text('Open'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Open'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Write'));
      await tester.pumpAndSettle();

      expect(result, equals('text'));
    });

    testWidgets('tapping Voice returns "voice"', (tester) async {
      String? result;

      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (context) => Scaffold(
              body: ElevatedButton(
                onPressed: () async {
                  result = await showQuickCapturePalette(context);
                },
                child: const Text('Open'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Open'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Voice'));
      await tester.pumpAndSettle();

      expect(result, equals('voice'));
    });

    testWidgets('tapping Mood Tap returns "__quick_mood_tap__"', (
      tester,
    ) async {
      String? result;

      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (context) => Scaffold(
              body: ElevatedButton(
                onPressed: () async {
                  result = await showQuickCapturePalette(context);
                },
                child: const Text('Open'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Open'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Mood Tap'));
      await tester.pumpAndSettle();

      expect(result, equals('__quick_mood_tap__'));
    });

    testWidgets('tapping Check-In returns "pulse_check_in"', (tester) async {
      String? result;

      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (context) => Scaffold(
              body: ElevatedButton(
                onPressed: () async {
                  result = await showQuickCapturePalette(context);
                },
                child: const Text('Open'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Open'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Check-In'));
      await tester.pumpAndSettle();

      expect(result, equals('pulse_check_in'));
    });

    testWidgets('unknown lastMode value does not highlight any tile', (
      tester,
    ) async {
      await _openPalette(tester, lastMode: 'unknown_mode_key');

      final lastUsedSemantics = tester
          .widgetList<Semantics>(find.byType(Semantics))
          .where((s) => s.properties.label?.contains(', last used') == true)
          .toList();

      expect(lastUsedSemantics, isEmpty);
    });

    testWidgets('dismissing sheet without selection returns null', (
      tester,
    ) async {
      String? result = 'sentinel';

      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (context) => Scaffold(
              body: ElevatedButton(
                onPressed: () async {
                  result = await showQuickCapturePalette(context);
                },
                child: const Text('Open'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Open'));
      await tester.pumpAndSettle();

      // Tap the barrier to dismiss the sheet.
      await tester.tapAt(const Offset(200, 100));
      await tester.pumpAndSettle();

      expect(result, isNull);
    });
  });
}
