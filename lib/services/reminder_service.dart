// ===========================================================================
// file: lib/services/reminder_service.dart
// purpose: Adaptive non-escalating reminder service (Phase 4D).
//
// Manages daily journal reminders that:
//   - Are context-sensitive to user-configured time-of-day windows.
//   - Auto-disable after 3 consecutive dismissals (never escalate).
//   - Support a "Snooze forever" (disable) first-class option.
//   - Show at most once per day per reminder type.
//   - Reset the dismissal counter when the user acts on the reminder.
//
// All state is persisted in SharedPreferences — no database needed.
// State lives in SharedPreferences so it survives app restarts without
// requiring an async database read on every session-list build.
//
// ADHD clinical UX contract (CLAUDE.md):
//   - Reminders must not escalate after dismissal.
//   - Auto-disable after 3 consecutive dismissals.
//   - "Snooze forever" is a first-class option.
//   - Never show reminder copy that mentions missed days or gaps.
//
// See: SPEC-20260302-adhd-informed-feature-roadmap § 4D
// ===========================================================================

import 'package:shared_preferences/shared_preferences.dart';

/// Supported reminder categories.
enum ReminderType {
  /// Prompt to start a daily journal entry.
  dailyJournal,
}

/// Time-of-day windows a user can choose for their reminder.
enum ReminderWindow { morning, afternoon, evening }

/// Human-readable label for each window (shown in settings UI).
extension ReminderWindowLabel on ReminderWindow {
  String get label => switch (this) {
    ReminderWindow.morning => 'Morning (7–9 AM)',
    ReminderWindow.afternoon => 'Afternoon (12–2 PM)',
    ReminderWindow.evening => 'Evening (7–9 PM)',
  };

  /// Start hour of the 2-hour display window (24-hour clock).
  int get startHour => switch (this) {
    ReminderWindow.morning => 7,
    ReminderWindow.afternoon => 12,
    ReminderWindow.evening => 19,
  };

  String get prefValue => name; // stored as 'morning' | 'afternoon' | 'evening'

  static ReminderWindow fromPrefValue(String? value) =>
      ReminderWindow.values.firstWhere(
        (w) => w.prefValue == value,
        orElse: () => ReminderWindow.morning,
      );
}

/// Adaptive non-escalating reminder service.
///
/// All public methods are synchronous reads or fire-and-forget async writes
/// against SharedPreferences — suitable for use inside Riverpod Provider
/// (synchronous) without awaiting.
class ReminderService {
  ReminderService(this._prefs);

  final SharedPreferences _prefs;

  /// Number of consecutive dismissals before the reminder auto-disables.
  static const int maxConsecutiveDismissals = 3;

  /// Duration of each time window (reminder is eligible for 2 hours).
  static const int _windowDurationHours = 2;

  // ---------------------------------------------------------------------------
  // Visibility
  // ---------------------------------------------------------------------------

  /// Whether [type] should be shown right now.
  ///
  /// Returns false if:
  ///   - The reminder type is disabled (by the user or by auto-disable).
  ///   - The dismissal count has reached [maxConsecutiveDismissals].
  ///   - The reminder was already shown today.
  ///   - The current time is outside the user's chosen window.
  ///
  /// The caller must additionally check whether the user has already
  /// completed the relevant activity today (e.g., has a journal session).
  bool shouldShow(ReminderType type) {
    if (!isEnabled(type)) return false;
    if (consecutiveDismissals(type) >= maxConsecutiveDismissals) return false;
    if (_wasShownToday(type)) return false;
    return _isInWindow(type);
  }

  // ---------------------------------------------------------------------------
  // User actions
  // ---------------------------------------------------------------------------

  /// Record a dismissal for [type].
  ///
  /// Increments the consecutive dismissal counter. Auto-disables the reminder
  /// when [maxConsecutiveDismissals] is reached (ADHD non-escalating contract).
  /// Stamps the last-shown date so the reminder does not re-appear today.
  Future<void> dismiss(ReminderType type) async {
    final count = consecutiveDismissals(type) + 1;
    await _prefs.setInt(_dismissKey(type), count);
    await _prefs.setInt(
      _lastShownKey(type),
      DateTime.now().millisecondsSinceEpoch,
    );
    if (count >= maxConsecutiveDismissals) {
      await _prefs.setBool(_enabledKey(type), false);
    }
  }

  /// Record that the user acted on the reminder (e.g., started a journal
  /// entry). Resets the consecutive dismissal counter.
  Future<void> acknowledge(ReminderType type) async {
    await _prefs.setInt(_dismissKey(type), 0);
  }

  /// Permanently disable [type] ("Snooze forever").
  ///
  /// Also resets the dismissal counter so that re-enabling in settings
  /// starts fresh rather than immediately auto-disabling again.
  Future<void> snoozeForever(ReminderType type) async {
    await _prefs.setBool(_enabledKey(type), false);
    await _prefs.setInt(_dismissKey(type), 0);
  }

  // ---------------------------------------------------------------------------
  // Settings helpers (called from settings_screen / reminder_providers)
  // ---------------------------------------------------------------------------

  /// Whether [type] is enabled in settings. Defaults to false (opt-in).
  bool isEnabled(ReminderType type) =>
      _prefs.getBool(_enabledKey(type)) ?? false;

  /// Set enabled state for [type].
  Future<void> setEnabled(ReminderType type, {required bool value}) async {
    await _prefs.setBool(_enabledKey(type), value);
    // Enabling clears the auto-disable dismissal count so a fresh start.
    if (value) {
      await _prefs.setInt(_dismissKey(type), 0);
    }
  }

  /// The user's configured [ReminderWindow] for [type]. Defaults to morning.
  ReminderWindow getWindow(ReminderType type) =>
      ReminderWindowLabel.fromPrefValue(_prefs.getString(_windowKey(type)));

  /// Persist the user's chosen [ReminderWindow] for [type].
  Future<void> setWindow(ReminderType type, ReminderWindow window) async {
    await _prefs.setString(_windowKey(type), window.prefValue);
  }

  /// Number of consecutive dismissals for [type] (0 = none yet).
  int consecutiveDismissals(ReminderType type) =>
      _prefs.getInt(_dismissKey(type)) ?? 0;

  // ---------------------------------------------------------------------------
  // Internal helpers
  // ---------------------------------------------------------------------------

  bool _isInWindow(ReminderType type) {
    final window = getWindow(type);
    final now = DateTime.now();
    final hour = now.hour;
    return hour >= window.startHour &&
        hour < window.startHour + _windowDurationHours;
  }

  bool _wasShownToday(ReminderType type) {
    final lastShownMs = _prefs.getInt(_lastShownKey(type));
    if (lastShownMs == null) return false;
    final lastShown = DateTime.fromMillisecondsSinceEpoch(lastShownMs);
    final now = DateTime.now();
    return lastShown.year == now.year &&
        lastShown.month == now.month &&
        lastShown.day == now.day;
  }

  // ---------------------------------------------------------------------------
  // SharedPreferences key helpers
  // ---------------------------------------------------------------------------

  String _enabledKey(ReminderType type) => 'reminder_${type.name}_enabled';
  String _windowKey(ReminderType type) => 'reminder_${type.name}_window';
  String _dismissKey(ReminderType type) =>
      'reminder_${type.name}_dismiss_count';
  String _lastShownKey(ReminderType type) => 'reminder_${type.name}_last_shown';
}
