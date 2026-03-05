// ===========================================================================
// file: lib/services/weekly_digest_service.dart
// purpose: Weekly celebratory digest shown on the home screen (Phase 3D).
//
// Queries completed sessions from the past 7 days and returns a digest that
// celebrates what the user captured. Shown once per week — dismissal is
// stored in SharedPreferences and expires after 7 days so the card
// resurfaces the following week.
//
// ADHD UX constraints:
//   - Copy focuses ONLY on what was captured — never references missed days,
//     gaps, frequency, streaks, or consistency.
//   - One card per week — when dismissed it stays hidden for exactly 7 days.
//   - No comparison to prior weeks (no "X more than last week").
//   - quick_mood_tap sessions do not count as "captured moments" — they are
//     trivial entries excluded from the celebratory count.
//
// See: SPEC-20260302-adhd-informed-feature-roadmap § Phase 3D
// ===========================================================================

import 'package:shared_preferences/shared_preferences.dart';

import '../database/app_database.dart';
import '../database/daos/session_dao.dart';

/// Digest data returned by [WeeklyDigestService.getDigest].
///
/// [sessionCount] is the number of completed non-quick_mood_tap sessions
/// captured in the past 7 days.
/// [highlightSession] is the most recent session with a non-empty summary
/// from that set, or null when no session has a summary.
class WeeklyDigest {
  final int sessionCount;
  final JournalSession? highlightSession;

  WeeklyDigest({required this.sessionCount, this.highlightSession});
}

/// Service for generating a weekly celebratory digest card.
class WeeklyDigestService {
  final SessionDao _sessionDao;
  final SharedPreferences _prefs;

  static const _dismissedKey = 'weekly_digest_dismissed_at';

  /// Number of days in the look-back window and the dismissal TTL.
  static const _windowDays = 7;

  WeeklyDigestService(this._sessionDao, this._prefs);

  /// Return the weekly digest, or null when the card should not be shown.
  ///
  /// Returns null when:
  ///   - The user dismissed the card within the past [_windowDays] days.
  ///   - There are no eligible sessions (completed, non-quick_mood_tap) this
  ///     week.
  Future<WeeklyDigest?> getDigest() async {
    if (_isDismissedThisWeek()) return null;

    final now = DateTime.now().toUtc();
    final weekStart = now.subtract(const Duration(days: _windowDays));
    final sessions = await _sessionDao.getSessionsByDateRange(weekStart, now);

    // Count only completed non-quick_mood_tap sessions.
    final eligible = sessions
        .where((s) => s.endTime != null && s.journalingMode != 'quick_mood_tap')
        .toList();

    if (eligible.isEmpty) return null;

    // Highlight: most recent session with a non-empty summary.
    // getSessionsByDateRange returns sessions ordered newest-first.
    final withSummary = eligible
        .where((s) => s.summary != null && s.summary!.isNotEmpty)
        .toList();

    return WeeklyDigest(
      sessionCount: eligible.length,
      highlightSession: withSummary.isNotEmpty ? withSummary.first : null,
    );
  }

  /// Dismiss the digest card for the next [_windowDays] days.
  ///
  /// Stores the current UTC epoch milliseconds in SharedPreferences.
  Future<void> dismissDigest() async {
    await _prefs.setInt(
      _dismissedKey,
      DateTime.now().toUtc().millisecondsSinceEpoch,
    );
  }

  bool _isDismissedThisWeek() {
    final stored = _prefs.getInt(_dismissedKey);
    if (stored == null) return false;
    final dismissedAt = DateTime.fromMillisecondsSinceEpoch(
      stored,
      isUtc: true,
    );
    final age = DateTime.now().toUtc().difference(dismissedAt);
    return age.inDays < _windowDays;
  }
}
