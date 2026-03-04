// ===========================================================================
// file: lib/providers/last_capture_mode_provider.dart
// purpose: Persists the last-used quick capture mode across sessions.
//
// Design:
//   - Backed by SharedPreferences key 'last_capture_mode'
//   - Null means no preference yet (first-time user)
//   - Mode keys match journaling mode strings used throughout the app
//     plus two specials: 'voice' (text session with voice pre-enabled)
//     and '__quick_mood_tap__' (Quick Mood Tap overlay)
//
// ADHD UX rationale:
//   Remembering the user's last capture mode eliminates the mode-selection
//   step on repeat visits — the most recent mode is pre-highlighted in the
//   palette so the user can tap once to continue their pattern.
//
// See: lib/ui/widgets/quick_capture_palette.dart, SPEC-20260302 Phase 3A
// ===========================================================================

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'onboarding_providers.dart';

/// SharedPreferences key for the last-used capture mode.
const _kLastCaptureModeKey = 'last_capture_mode';

/// Reads and writes the last-used capture mode string.
///
/// Null indicates no preference has been recorded (first-time users see all
/// options with equal weight — no mode is pre-highlighted).
class LastCaptureModeNotifier extends StateNotifier<String?> {
  LastCaptureModeNotifier(this._prefs)
    : super(_prefs.getString(_kLastCaptureModeKey));

  final SharedPreferences _prefs;

  /// Persists [mode] as the new last-used capture mode.
  ///
  /// Accepts any mode key valid for the quick capture palette:
  ///   - null: clear preference (resets to no default)
  ///   - 'text': free-form text journal session
  ///   - 'voice': text session with voice mode pre-enabled
  ///   - '__quick_mood_tap__': Quick Mood Tap overlay
  ///   - 'pulse_check_in': Pulse Check-In slider flow
  ///
  /// Note: 'photo' is reserved for future camera-open dispatch but is not
  /// currently presented in the palette.
  Future<void> setMode(String? mode) async {
    state = mode;
    if (mode == null) {
      await _prefs.remove(_kLastCaptureModeKey);
    } else {
      await _prefs.setString(_kLastCaptureModeKey, mode);
    }
  }
}

/// Provider for the last-used capture mode (null = no preference yet).
final lastCaptureModeProvider =
    StateNotifierProvider<LastCaptureModeNotifier, String?>((ref) {
      final prefs = ref.watch(sharedPreferencesProvider);
      return LastCaptureModeNotifier(prefs);
    });

/// In-memory pending widget launch mode set by app.dart when the app is
/// launched from the Quick Capture home screen widget (Phase 4B).
///
/// SessionListScreen listens for this to become non-null and dispatches the
/// capture mode immediately. The listener clears the value after consuming it.
///
/// Not persisted — null at every cold start until the widget launch path sets
/// it. A null value means no pending dispatch.
final pendingWidgetLaunchModeProvider = StateProvider<String?>((_) => null);
