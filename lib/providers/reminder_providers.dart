// ===========================================================================
// file: lib/providers/reminder_providers.dart
// purpose: Riverpod providers for adaptive non-escalating reminders (Phase 4D).
//
// reminderServiceProvider     — singleton ReminderService instance.
// dailyReminderVisibleProvider — true when the daily journal reminder should
//                               be shown (right time window, not dismissed
//                               today, user has no session today).
//
// Invalidate dailyReminderVisibleProvider to re-evaluate visibility after a
// dismiss or acknowledge:
//   ref.invalidate(dailyReminderVisibleProvider);
//
// See: lib/services/reminder_service.dart
//      SPEC-20260302-adhd-informed-feature-roadmap § Phase 4D
// ===========================================================================

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/reminder_service.dart';
import 'onboarding_providers.dart';
import 'session_providers.dart';

/// Singleton [ReminderService] wired to the shared [SharedPreferences] instance.
final reminderServiceProvider = Provider<ReminderService>((ref) {
  return ReminderService(ref.watch(sharedPreferencesProvider));
});

/// Whether the daily journal reminder card should be visible on the home screen.
///
/// Returns true only when ALL of:
///   - Journal reminder is enabled in settings.
///   - Consecutive dismissals < [ReminderService.maxConsecutiveDismissals].
///   - The reminder has not already been shown today.
///   - Current time is within the user's configured window.
///   - The user has no completed journal session today (quick_mood_tap excluded).
///
/// Reads synchronously from the session stream — returns false while loading
/// or on error so no reminder flickers appear during start-up.
final dailyReminderVisibleProvider = Provider<bool>((ref) {
  final service = ref.watch(reminderServiceProvider);

  // Fast-path: if the service says no (disabled / dismissed / wrong time),
  // skip the more expensive session-list check.
  if (!service.shouldShow(ReminderType.dailyJournal)) return false;

  // Check whether the user has already journaled today.  The stream is already
  // live by the time this provider is read (session_list_screen watches it).
  final sessionsAsync = ref.watch(allSessionsProvider);
  return sessionsAsync.when(
    data: (sessions) {
      final today = DateTime.now();
      final hasJournaledToday = sessions.any((s) {
        final local = s.startTime.toLocal();
        final isToday =
            local.year == today.year &&
            local.month == today.month &&
            local.day == today.day;
        // quick_mood_tap sessions are not real journaling sessions — they
        // are excluded from the "has journaled today" check.
        final isRealSession = s.journalingMode != 'quick_mood_tap';
        return isToday && isRealSession;
      });
      return !hasJournaledToday;
    },
    // While loading or on error, suppress the reminder to avoid flicker.
    loading: () => false,
    error: (_, _) => false,
  );
});
