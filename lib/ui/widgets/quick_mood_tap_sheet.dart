// ===========================================================================
// file: lib/ui/widgets/quick_mood_tap_sheet.dart
// purpose: Bottom sheet for Quick Mood Tap (Phase 3B ADHD roadmap).
//
// Three-second flow: tap a mood emoji → energy level appears → optional
// energy tap → auto-save → brief success state → auto-close.
//
// No session navigation, no LLM call. Opens as a modal overlay on the home
// screen. The save is handled by [QuickMoodNotifier.saveMoodTap] which writes
// a minimal [JournalSession] of mode `quick_mood_tap` directly via SessionDao.
//
// ADHD UX constraints:
//   - No evaluative language about mood scores
//   - No progress counters or streak references
//   - Energy is optional — user can skip with one tap
//   - ~3 seconds from open to close on the happy path
//
// See: SPEC-20260302-adhd-informed-feature-roadmap § Phase 3B
//      lib/providers/quick_mood_providers.dart
// ===========================================================================

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../providers/quick_mood_providers.dart';

/// Show the Quick Mood Tap bottom sheet overlay on the home screen.
///
/// Does not return a value — the save is performed inside the sheet and the
/// sheet auto-closes after a brief success flash.
Future<void> showQuickMoodTapSheet(BuildContext context) {
  return showModalBottomSheet<void>(
    context: context,
    isDismissible: true,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (ctx) => const _QuickMoodTapSheet(),
  );
}

// ---------------------------------------------------------------------------
// Internal widget
// ---------------------------------------------------------------------------

enum _Phase { mood, energy, saving, saved }

class _QuickMoodTapSheet extends ConsumerStatefulWidget {
  const _QuickMoodTapSheet();

  @override
  ConsumerState<_QuickMoodTapSheet> createState() => _QuickMoodTapSheetState();
}

class _QuickMoodTapSheetState extends ConsumerState<_QuickMoodTapSheet> {
  _Phase _phase = _Phase.mood;
  int? _selectedMood;

  /// Cancelable timer for auto-close after success flash.
  /// Cancelled in [dispose] so no pending-timer assertion fires in tests.
  Timer? _closeTimer;

  @override
  void dispose() {
    _closeTimer?.cancel();
    super.dispose();
  }

  /// User tapped a mood emoji. Transitions from [_Phase.mood] to
  /// [_Phase.energy]. In energy phase, allows re-selection of a different
  /// emoji without going back to the mood phase.
  void _onMoodTap(int mood) {
    setState(() {
      _selectedMood = mood;
      if (_phase == _Phase.mood) {
        _phase = _Phase.energy;
      }
    });
  }

  /// User tapped an energy level or the "Skip" link. Saves and closes.
  Future<void> _onEnergy(int? energy) async {
    if (_selectedMood == null) return;

    setState(() => _phase = _Phase.saving);

    final ok = await ref
        .read(quickMoodProvider.notifier)
        .saveMoodTap(mood: _selectedMood!, energy: energy);

    if (!mounted) return;

    if (ok) {
      setState(() => _phase = _Phase.saved);
      // Brief success pause then close. Stored so dispose() can cancel it
      // and avoid a pending-timer assertion in tests.
      _closeTimer = Timer(const Duration(milliseconds: 700), () {
        if (mounted) {
          ref.read(quickMoodProvider.notifier).reset();
          Navigator.of(context).pop();
        }
      });
    } else {
      // Save failed — show brief error feedback before closing.
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Couldn't save. Try again.")),
        );
      }
      ref.read(quickMoodProvider.notifier).reset();
      Navigator.of(context).pop();
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(24, 20, 24, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            _buildHandle(theme),
            if (_phase == _Phase.saved) ...[
              _buildSavedState(theme),
            ] else if (_phase == _Phase.saving) ...[
              _buildSavingState(theme),
            ] else ...[
              _buildMoodHeader(theme),
              const SizedBox(height: 16),
              _buildMoodRow(theme),
              if (_phase == _Phase.energy) ...[
                const SizedBox(height: 20),
                _buildEnergyHeader(theme),
                const SizedBox(height: 10),
                _buildEnergyRow(),
                const SizedBox(height: 4),
                TextButton(
                  onPressed: () => _onEnergy(null),
                  child: const Text('Skip'),
                ),
              ],
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildHandle(ThemeData theme) {
    return Container(
      width: 32,
      height: 4,
      margin: const EdgeInsets.only(bottom: 20),
      decoration: BoxDecoration(
        color: theme.colorScheme.onSurfaceVariant.withValues(alpha: 0.4),
        borderRadius: BorderRadius.circular(2),
      ),
    );
  }

  Widget _buildMoodHeader(ThemeData theme) {
    return Text('How are you feeling?', style: theme.textTheme.titleMedium);
  }

  Widget _buildMoodRow(ThemeData theme) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
      children: List.generate(kMoodEmojis.length, (i) {
        final mood = i + 1; // 1–5
        final selected = _selectedMood == mood;
        return Semantics(
          label: kMoodLabels[i],
          button: true,
          selected: selected,
          child: ConstrainedBox(
            constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
            child: GestureDetector(
              onTap: () => _onMoodTap(mood),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 150),
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: selected
                      ? theme.colorScheme.primaryContainer
                      : Colors.transparent,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  kMoodEmojis[i],
                  style: TextStyle(fontSize: selected ? 44 : 36),
                ),
              ),
            ),
          ),
        );
      }),
    );
  }

  Widget _buildEnergyHeader(ThemeData theme) {
    return Text(
      'Energy level?',
      style: theme.textTheme.bodyMedium?.copyWith(
        color: theme.colorScheme.onSurfaceVariant,
      ),
    );
  }

  Widget _buildEnergyRow() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
      children: List.generate(kEnergyLabels.length, (i) {
        final energy = i + 1; // 1–3
        return FilledButton.tonal(
          onPressed: () => _onEnergy(energy),
          child: Text(kEnergyLabels[i]),
        );
      }),
    );
  }

  Widget _buildSavingState(ThemeData theme) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 20),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const CircularProgressIndicator(),
          const SizedBox(height: 12),
          Text('Saving…', style: theme.textTheme.bodyMedium),
        ],
      ),
    );
  }

  Widget _buildSavedState(ThemeData theme) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 20),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.check_circle_outline,
            size: 48,
            color: theme.colorScheme.primary,
          ),
          const SizedBox(height: 8),
          Text(
            "Saved. That's enough.",
            style: theme.textTheme.titleMedium?.copyWith(
              color: theme.colorScheme.primary,
            ),
          ),
        ],
      ),
    );
  }
}
