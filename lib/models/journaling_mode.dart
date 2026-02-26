// ===========================================================================
// file: lib/models/journaling_mode.dart
// purpose: Activity-scoped journaling mode templates that shape the LLM's
//          conversation flow with numbered steps.
//
// Each mode defines a system prompt fragment that composes with (not replaces)
// the base personality prompt. The mode is stored per-session and immutable
// once the session starts.
//
// See: ADR-0025 (Journaling Mode Templates)
// ===========================================================================

/// Activity-scoped journaling modes.
///
/// Each mode provides a [displayName] for UI and a [systemPromptFragment]
/// that is appended to the personality system prompt. The [free] mode has
/// an empty fragment (current default behavior).
enum JournalingMode {
  /// Free-form journaling — no additional prompt guidance.
  free,

  /// Guided gratitude practice with 3 numbered steps.
  gratitude,

  /// Dream exploration with 4 numbered steps.
  dreamAnalysis,

  /// Mood assessment with 3 numbered steps.
  moodCheckIn,

  /// Conversational onboarding — first-launch experience as a real session.
  onboarding;

  /// Human-readable name for UI display.
  String get displayName => switch (this) {
    free => 'Free Journal',
    gratitude => 'Gratitude',
    dreamAnalysis => 'Dream Analysis',
    moodCheckIn => 'Mood Check-In',
    onboarding => 'Onboarding',
  };

  /// System prompt fragment appended to the personality prompt.
  ///
  /// Returns empty string for [free] mode (no additional guidance).
  /// Other modes define numbered conversation steps that the LLM follows.
  String get systemPromptFragment => switch (this) {
    free => '',
    gratitude => _gratitudePrompt,
    dreamAnalysis => _dreamAnalysisPrompt,
    moodCheckIn => _moodCheckInPrompt,
    onboarding => _onboardingPrompt,
  };

  /// Convert to the string stored in SQLite/Supabase.
  ///
  /// Uses snake_case format: 'free', 'gratitude', 'dream_analysis', 'mood_check_in'.
  String toDbString() => switch (this) {
    free => 'free',
    gratitude => 'gratitude',
    dreamAnalysis => 'dream_analysis',
    moodCheckIn => 'mood_check_in',
    onboarding => 'onboarding',
  };

  /// Parse from a database string value.
  ///
  /// Returns null for unrecognized values (defensive — new modes added
  /// server-side won't crash old clients).
  static JournalingMode? fromDbString(String? value) {
    if (value == null) return null;
    return switch (value) {
      'free' => JournalingMode.free,
      'gratitude' => JournalingMode.gratitude,
      'dream_analysis' => JournalingMode.dreamAnalysis,
      'mood_check_in' => JournalingMode.moodCheckIn,
      'onboarding' => JournalingMode.onboarding,
      _ => null,
    };
  }
}

// ---------------------------------------------------------------------------
// Mode-specific prompt templates
// ---------------------------------------------------------------------------

const _gratitudePrompt = '''

JOURNALING MODE: Gratitude Practice
Guide the user through these steps. Move to the next step after they respond.

Step 1: Ask the user to name one specific thing they are grateful for today.
Step 2: Ask them to describe why this matters to them and how it makes them feel.
Step 3: Ask them to think about one small way they could express or share this gratitude.

Keep responses warm and encouraging. Acknowledge what they share before prompting the next step.''';

const _dreamAnalysisPrompt = '''

JOURNALING MODE: Dream Analysis
Guide the user through these steps. Move to the next step after they respond.

Step 1: Ask the user to describe their dream in as much detail as they remember.
Step 2: Ask about the emotions they felt during the dream and upon waking.
Step 3: Ask if any elements of the dream connect to something happening in their waking life.
Step 4: Help them reflect on what the dream might be telling them about their current state of mind.

Be curious and non-judgmental. Avoid definitive dream interpretations — help them explore their own meaning.''';

const _moodCheckInPrompt = '''

JOURNALING MODE: Mood Check-In
Guide the user through these steps. Move to the next step after they respond.

Step 1: Ask the user to describe their current mood in a few words or a sentence.
Step 2: Ask what they think is contributing most to this mood right now.
Step 3: Ask what one thing might shift their mood — either to maintain it if positive, or to improve it if difficult.

Be empathetic and validating. Reflect back what they share before moving to the next step.''';

const _onboardingPrompt = '''

JOURNALING MODE: Onboarding
This is the user's very first journal session. Guide them through a warm welcome conversation.

Step 1: Welcome them and ask what brings them to journaling — what are they hoping to get out of it?
Step 2: Acknowledge their answer warmly. Mention they can journal by voice or text, whichever feels natural.
Step 3: Ask about their journaling preferences — when do they usually like to reflect? Morning, evening, or whenever the mood strikes?
Step 4: Wrap up with encouragement. Let them know this first entry is already saved, and they can come back anytime.

Keep it conversational and brief. This is their first impression — be welcoming, not overwhelming.''';
