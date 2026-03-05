// ===========================================================================
// file: lib/services/resurfacing_service.dart
// purpose: Spaced-repetition resurfacing of past journal entries.
//
// Selects a single past entry to show as a "Gift" card on the home screen.
// Algorithm: tries three windows (~7d, ~30d, ~90d ago, each ±3 days) in
// randomized order. Returns the first eligible session found, or null if
// none qualifies.
//
// Eligibility criteria:
//   - Session is completed (endTime != null)
//   - Session has a summary (non-null, non-empty)
//   - Session is not a quick_mood_tap entry (trivial content)
//   - Session has not been excluded by the user via skipSession()
//
// User exclusions are persisted in SharedPreferences so skipped entries are
// never resurfaced in future app sessions.
//
// ADHD UX constraints:
//   - Never resurface negative-tagged entries (future: when tags exist)
//   - One entry at a time — never show multiple resurfaced cards
//   - No implicit framing about frequency, gaps, or missed days
//
// See: SPEC-20260302-adhd-informed-feature-roadmap § Phase 3C
// ===========================================================================

import 'package:shared_preferences/shared_preferences.dart';

import '../database/app_database.dart';
import '../database/daos/session_dao.dart';

/// Service for selecting a past session to resurface as a home screen "Gift".
class ResurfacingService {
  final SessionDao _sessionDao;
  final SharedPreferences _prefs;

  /// SharedPreferences key for the set of excluded session IDs.
  static const _excludedKey = 'resurfacing_excluded_session_ids';

  /// Window centers in days (spaced-repetition-inspired).
  static const _windowCenters = [7, 30, 90];

  /// ±radius around each window center in days.
  static const _windowRadius = 3;

  ResurfacingService(this._sessionDao, this._prefs);

  /// Pick a past session to resurface, or null if none qualifies.
  ///
  /// Tries each window in random order for variety. Within each window,
  /// selects randomly so the same session is not always shown first.
  Future<JournalSession?> pickResurfacedSession() async {
    final now = DateTime.now().toUtc();
    final excluded = _excludedIds;

    // Shuffle window order so different time horizons surface with equal
    // frequency rather than always preferring the 7-day window.
    final windows = List<int>.from(_windowCenters)..shuffle();

    for (final center in windows) {
      final windowEnd = now.subtract(Duration(days: center - _windowRadius));
      final windowStart = now.subtract(Duration(days: center + _windowRadius));

      final sessions = await _sessionDao.getSessionsByDateRange(
        windowStart,
        windowEnd,
      );

      final eligible = sessions
          .where(
            (s) =>
                s.endTime != null &&
                s.summary != null &&
                (s.summary?.isNotEmpty ?? false) &&
                s.journalingMode != 'quick_mood_tap' &&
                !excluded.contains(s.sessionId),
          )
          .toList();

      if (eligible.isNotEmpty) {
        eligible.shuffle();
        return eligible.first;
      }
    }
    return null;
  }

  /// Exclude a session from future resurfacing.
  ///
  /// Persisted across app sessions in SharedPreferences.
  ///
  /// TODO: consider pruning IDs for sessions older than the max window
  /// (~93 days = 90d center + 3d radius) — they can never resurface anyway
  /// and grow the stored list without bound over time.
  Future<void> skipSession(String sessionId) async {
    final ids = _excludedIds..add(sessionId);
    await _prefs.setStringList(_excludedKey, ids.toList());
  }

  Set<String> get _excludedIds =>
      (_prefs.getStringList(_excludedKey) ?? []).toSet();
}
