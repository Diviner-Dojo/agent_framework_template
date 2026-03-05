// ===========================================================================
// file: lib/providers/quick_mood_providers.dart
// purpose: Provider for saving Quick Mood Tap entries (Phase 3B).
//
// Quick Mood Tap is a 3-second mood + energy snapshot that does NOT go
// through the full session lifecycle (no LLM greeting call). It creates a
// minimal JournalSession of type 'quick_mood_tap' using SessionDao directly,
// stores the mood/energy in the session summary, and ends the session
// immediately. These sessions are excluded from the main session list view.
//
// See: SPEC-20260302-adhd-informed-feature-roadmap § Phase 3B
// ===========================================================================

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';

import 'database_provider.dart';

/// State for a pending quick mood tap save operation.
enum QuickMoodSaveStatus { idle, saving, saved, error }

/// Emoji labels for mood values 1–5.
const List<String> kMoodEmojis = ['😢', '😕', '😐', '🙂', '😄'];

/// Descriptions for mood values 1–5 (accessible label, not shown in UI).
const List<String> kMoodLabels = [
  'Very low',
  'Low',
  'Neutral',
  'Good',
  'Great',
];

/// Descriptions for energy values 1–3.
const List<String> kEnergyLabels = ['Low', 'Medium', 'High'];

/// Notifier for Quick Mood Tap save operations.
///
/// Exposes [saveMoodTap] to persist a quick mood entry as a minimal
/// [JournalSession] of mode `quick_mood_tap` without invoking the LLM.
class QuickMoodNotifier extends Notifier<QuickMoodSaveStatus> {
  @override
  QuickMoodSaveStatus build() => QuickMoodSaveStatus.idle;

  /// Save a quick mood tap entry.
  ///
  /// [mood] — 1–5 (index 0–4 into [kMoodEmojis]).
  /// [energy] — 1–3 (optional: 1=Low, 2=Medium, 3=High).
  ///
  /// Creates a minimal session of mode `quick_mood_tap` without calling
  /// the LLM, stores the summary, and ends the session immediately.
  /// Returns true on success, false on error.
  Future<bool> saveMoodTap({required int mood, int? energy}) async {
    state = QuickMoodSaveStatus.saving;

    final sessionDao = ref.read(sessionDaoProvider);
    final sessionId = const Uuid().v4();
    final now = DateTime.now().toUtc();

    // Build human-readable summary before writing to the database.
    final moodLabel = mood >= 1 && mood <= 5
        ? kMoodLabels[mood - 1]
        : 'Unknown';
    final moodEmoji = mood >= 1 && mood <= 5 ? kMoodEmojis[mood - 1] : '?';
    final energyPart = energy != null && energy >= 1 && energy <= 3
        ? ' · Energy: ${kEnergyLabels[energy - 1]}'
        : '';
    final summary = 'Mood: $moodEmoji $moodLabel$energyPart';

    try {
      // Single atomic INSERT — journalingMode, endTime, and summary are all
      // written together so no partial session is left if the app crashes.
      // A multi-step sequence (createSession → updateJournalingMode →
      // endSession) would leave a phantom session with journalingMode=null
      // that resumeLatestSession() would attempt to resume as a regular
      // journaling session. See SessionDao.createQuickMoodSession.
      await sessionDao.createQuickMoodSession(
        sessionId,
        now,
        _localTimezone(),
        summary,
      );

      state = QuickMoodSaveStatus.saved;
      return true;
    } on Exception {
      state = QuickMoodSaveStatus.error;
      return false;
    }
  }

  /// Reset to idle (called after the sheet closes).
  void reset() => state = QuickMoodSaveStatus.idle;

  String _localTimezone() {
    // Flutter timezone detection is complex; UTC offset is sufficient for
    // quick mood tap sessions (not displayed with timezone information).
    final offset = DateTime.now().timeZoneOffset;
    final sign = offset.isNegative ? '-' : '+';
    final hours = offset.inHours.abs().toString().padLeft(2, '0');
    final minutes = (offset.inMinutes.abs() % 60).toString().padLeft(2, '0');
    return 'UTC$sign$hours:$minutes';
  }
}

/// Provider for [QuickMoodNotifier].
final quickMoodProvider =
    NotifierProvider<QuickMoodNotifier, QuickMoodSaveStatus>(
      QuickMoodNotifier.new,
    );
