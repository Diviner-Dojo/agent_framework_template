// ===========================================================================
// file: test/ui/quick_mood_tap_sheet_test.dart
// purpose: Widget tests for QuickMoodTapSheet (Phase 3B).
//
// Covers:
//   - Initial mood-phase layout (emoji row visible, energy row absent)
//   - Mood tap → transitions to energy phase (energy buttons appear)
//   - Energy tap → triggers saveMoodTap with correct mood + energy
//   - Skip link → triggers saveMoodTap with energy=null
//   - Success state shown after save
//   - Re-selecting a different emoji in energy phase updates selection
//   - Mood emoji re-tappable in energy phase (re-selection without going back)
// ===========================================================================

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/providers/quick_mood_providers.dart';
import 'package:agentic_journal/ui/widgets/quick_mood_tap_sheet.dart';

// ---------------------------------------------------------------------------
// Fake notifier to capture saveMoodTap calls without touching the database.
// ---------------------------------------------------------------------------

class _FakeQuickMoodNotifier extends QuickMoodNotifier {
  final List<({int mood, int? energy})> calls = [];
  final bool _shouldSucceed;

  _FakeQuickMoodNotifier({bool shouldSucceed = true})
    : _shouldSucceed = shouldSucceed;

  @override
  Future<bool> saveMoodTap({required int mood, int? energy}) async {
    calls.add((mood: mood, energy: energy));
    state = _shouldSucceed
        ? QuickMoodSaveStatus.saved
        : QuickMoodSaveStatus.error;
    return _shouldSucceed;
  }

  @override
  void reset() => state = QuickMoodSaveStatus.idle;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/// Pumps the sheet inside a testWidgets context by pushing it as a route.
Future<_FakeQuickMoodNotifier> _pumpSheet(
  WidgetTester tester, {
  bool shouldSucceed = true,
}) async {
  final notifier = _FakeQuickMoodNotifier(shouldSucceed: shouldSucceed);

  await tester.pumpWidget(
    ProviderScope(
      overrides: [quickMoodProvider.overrideWith(() => notifier)],
      child: MaterialApp(
        home: Builder(
          builder: (ctx) => Scaffold(
            body: Center(
              child: ElevatedButton(
                onPressed: () => showQuickMoodTapSheet(ctx),
                child: const Text('Open'),
              ),
            ),
          ),
        ),
      ),
    ),
  );

  // Open the sheet.
  await tester.tap(find.text('Open'));
  await tester.pumpAndSettle();

  return notifier;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void main() {
  group('QuickMoodTapSheet', () {
    testWidgets('shows mood header and 5 emoji buttons on open', (
      tester,
    ) async {
      await _pumpSheet(tester);

      expect(find.text('How are you feeling?'), findsOneWidget);

      // All 5 mood emojis rendered.
      for (final emoji in kMoodEmojis) {
        expect(find.text(emoji), findsOneWidget);
      }

      // Energy row not yet visible.
      expect(find.text('Energy level?'), findsNothing);
      expect(find.text('Low'), findsNothing);
    });

    testWidgets('tapping a mood emoji shows energy row', (tester) async {
      await _pumpSheet(tester);

      // Tap the third emoji (mood=3, 😐).
      await tester.tap(find.text('😐'));
      await tester.pump();

      expect(find.text('Energy level?'), findsOneWidget);
      for (final label in kEnergyLabels) {
        expect(find.text(label), findsOneWidget);
      }
      expect(find.text('Skip'), findsOneWidget);
    });

    testWidgets('tapping energy button saves with correct mood and energy', (
      tester,
    ) async {
      final notifier = await _pumpSheet(tester);

      // Select mood 4 (🙂).
      await tester.tap(find.text('🙂'));
      await tester.pump();

      // Select "Medium" energy (energy=2).
      await tester.tap(find.text('Medium'));
      // Two pumps: first processes the saving state change, second processes
      // the saved state + creates the 700ms close timer.
      await tester.pump();
      await tester.pump();

      expect(notifier.calls, hasLength(1));
      expect(notifier.calls.first.mood, equals(4));
      expect(notifier.calls.first.energy, equals(2));

      // Advance fake clock past the 700ms auto-close timer so no
      // pending-timer assertion fires when the widget tree is torn down.
      await tester.pump(const Duration(milliseconds: 800));
    });

    testWidgets('tapping Skip saves with energy=null', (tester) async {
      final notifier = await _pumpSheet(tester);

      // Select mood 2 (😕).
      await tester.tap(find.text('😕'));
      await tester.pump();

      // Tap Skip.
      await tester.tap(find.text('Skip'));
      await tester.pump();
      await tester.pump();

      expect(notifier.calls, hasLength(1));
      expect(notifier.calls.first.mood, equals(2));
      expect(notifier.calls.first.energy, isNull);

      // Drain pending close timer.
      await tester.pump(const Duration(milliseconds: 800));
    });

    testWidgets('shows saved state after successful save', (tester) async {
      await _pumpSheet(tester);

      await tester.tap(find.text('😄'));
      await tester.pump();

      await tester.tap(find.text('High'));
      await tester.pump();
      await tester.pump();

      // Saved state visible before timer fires.
      expect(find.byIcon(Icons.check_circle_outline), findsOneWidget);
      expect(find.text("Saved. That's enough."), findsOneWidget);

      // Drain pending close timer.
      await tester.pump(const Duration(milliseconds: 800));
    });

    testWidgets(
      're-tapping a different emoji in energy phase updates selection',
      (tester) async {
        final notifier = await _pumpSheet(tester);

        // Select mood 1 first.
        await tester.tap(find.text('😢'));
        await tester.pump();

        // Energy row visible. Now tap mood 5 to change selection.
        await tester.tap(find.text('😄'));
        await tester.pump();

        // Energy row should still be visible.
        expect(find.text('Energy level?'), findsOneWidget);

        // Now save with "Low" energy — should use updated mood=5.
        await tester.tap(find.text('Low'));
        await tester.pump();
        await tester.pump();

        expect(notifier.calls, hasLength(1));
        expect(notifier.calls.first.mood, equals(5));
        expect(notifier.calls.first.energy, equals(1));

        // Drain pending close timer.
        await tester.pump(const Duration(milliseconds: 800));
      },
    );

    testWidgets('mood emoji count matches kMoodEmojis constant', (
      tester,
    ) async {
      await _pumpSheet(tester);

      // Each emoji in kMoodEmojis should appear exactly once.
      for (final emoji in kMoodEmojis) {
        expect(find.text(emoji), findsOneWidget);
      }
    });
  });
}
