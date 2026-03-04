// ===========================================================================
// file: lib/ui/widgets/quick_capture_palette.dart
// purpose: Quick Capture Palette — Phase 3A home-screen entry point.
//
// A modal bottom sheet presenting five large, icon-led capture mode tiles.
// Tapping a tile dismisses the sheet and returns the mode key to the caller.
//
// The caller (session_list_screen.dart) is responsible for:
//   - Persisting the selected mode via lastCaptureModeProvider
//   - Dispatching to the appropriate flow (voice pre-enable, navigation, etc.)
//
// Mode keys returned:
//   'text'               — free-form text journal session
//   'voice'              — text session with voice mode pre-enabled
//   '__quick_mood_tap__' — Quick Mood Tap overlay (no full session)
//   'pulse_check_in'     — Pulse Check-In slider flow
//
// Note: 'photo' mode key is reserved but NOT included in the palette until
// camera-open dispatch is implemented (see Bug 2 in BUILD_STATUS.md).
//
// ADHD UX constraints:
//   - "What's on your mind? A few words is enough." — no pressure framing
//   - Last-used mode highlighted with primaryContainer background
//   - 48dp minimum tap targets on all mode tiles
//   - No session-count references, no streak language
//
// See: lib/providers/last_capture_mode_provider.dart, SPEC-20260302 Phase 3A
// ===========================================================================

import 'package:flutter/material.dart';

/// Named record type for a capture mode entry.
///
/// Fields: label (display text), icon (leading icon), key (mode key string).
typedef _ModeEntry = ({String label, IconData icon, String key});

const _kModes = <_ModeEntry>[
  (label: 'Write', icon: Icons.edit_note_outlined, key: 'text'),
  (label: 'Voice', icon: Icons.mic_outlined, key: 'voice'),
  (label: 'Mood Tap', icon: Icons.mood_outlined, key: '__quick_mood_tap__'),
  (
    label: 'Check-In',
    icon: Icons.monitor_heart_outlined,
    key: 'pulse_check_in',
  ),
];

/// Show the Quick Capture Palette and return the chosen mode key.
///
/// Displays five large capture mode tiles. The tile matching [lastMode] is
/// pre-highlighted with a filled background so repeat users see their
/// preferred mode at a glance — eliminating the mode-selection decision for
/// habitual users.
///
/// Returns null if the user dismisses the sheet without selecting.
Future<String?> showQuickCapturePalette(
  BuildContext context, {
  String? lastMode,
}) {
  return showModalBottomSheet<String>(
    context: context,
    isDismissible: true,
    // isScrollControlled lets the sheet exceed the default 50% max height
    // so the 5-tile grid always fits without overflow on small screens.
    isScrollControlled: true,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (ctx) => _QuickCapturePalette(lastMode: lastMode),
  );
}

// ---------------------------------------------------------------------------
// Internal widget
// ---------------------------------------------------------------------------

class _QuickCapturePalette extends StatelessWidget {
  final String? lastMode;

  const _QuickCapturePalette({this.lastMode});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            _buildHandle(theme),
            Text("What's on your mind?", style: theme.textTheme.titleMedium),
            const SizedBox(height: 4),
            Text(
              'A few words is enough.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 20),
            // Row 1: Write, Voice
            Row(
              children: [
                Expanded(
                  child: _ModeButton(
                    mode: _kModes[0],
                    isHighlighted: lastMode == _kModes[0].key,
                    onTap: () => Navigator.of(context).pop(_kModes[0].key),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _ModeButton(
                    mode: _kModes[1],
                    isHighlighted: lastMode == _kModes[1].key,
                    onTap: () => Navigator.of(context).pop(_kModes[1].key),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            // Row 2: Mood Tap, Check-In
            Row(
              children: [
                Expanded(
                  child: _ModeButton(
                    mode: _kModes[2],
                    isHighlighted: lastMode == _kModes[2].key,
                    onTap: () => Navigator.of(context).pop(_kModes[2].key),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _ModeButton(
                    mode: _kModes[3],
                    isHighlighted: lastMode == _kModes[3].key,
                    onTap: () => Navigator.of(context).pop(_kModes[3].key),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHandle(ThemeData theme) {
    return Container(
      width: 32,
      height: 4,
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: theme.colorScheme.onSurfaceVariant.withValues(alpha: 0.4),
        borderRadius: BorderRadius.circular(2),
      ),
    );
  }
}

/// A single capture mode tile in the palette grid.
///
/// The tap action is provided via [onTap] from [_QuickCapturePalette], which
/// holds the correct [BuildContext] for the modal route. This ensures
/// [Navigator.of(context).pop()] resolves to the sheet's own route, not the
/// underlying screen's navigator.
class _ModeButton extends StatelessWidget {
  final _ModeEntry mode;

  /// Whether this tile corresponds to the last-used mode.
  ///
  /// True: rendered with [ColorScheme.primaryContainer] background.
  /// False: rendered with [ColorScheme.surfaceContainerHighest] background.
  final bool isHighlighted;

  /// Called when the tile is tapped. Provided by the parent widget to ensure
  /// the correct navigator context is used.
  final VoidCallback onTap;

  const _ModeButton({
    required this.mode,
    required this.isHighlighted,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final bgColor = isHighlighted
        ? theme.colorScheme.primaryContainer
        : theme.colorScheme.surfaceContainerHighest;
    final fgColor = isHighlighted
        ? theme.colorScheme.onPrimaryContainer
        : theme.colorScheme.onSurfaceVariant;

    return Semantics(
      button: true,
      label: '${mode.label}${isHighlighted ? ', last used' : ''}',
      child: Material(
        color: bgColor,
        borderRadius: BorderRadius.circular(16),
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 12),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(mode.icon, size: 32, color: fgColor),
                const SizedBox(height: 8),
                Text(
                  mode.label,
                  style: theme.textTheme.labelLarge?.copyWith(color: fgColor),
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
