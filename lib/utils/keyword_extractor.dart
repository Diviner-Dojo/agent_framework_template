// ===========================================================================
// file: lib/utils/keyword_extractor.dart
// purpose: Keyword detection for the Layer A rule-based agent (Phase 1).
//
// The agent uses keyword extraction to select contextually relevant
// follow-up questions. This is deliberately simple — no NLP, no ML.
// Phase 3 replaces this with Claude API-based understanding.
//
// Priority order when multiple categories match: emotional > social > work.
// Rationale: emotional states are the most important to explore in journaling.
// ===========================================================================

/// The category detected from keyword analysis.
///
/// The agent selects follow-up questions based on this category.
/// [none] means no keywords matched — the agent will use a generic follow-up.
enum KeywordCategory { emotional, social, work, none }

/// Keywords that indicate emotional content.
///
/// These are common emotion words that a journaling user might use.
/// Case-insensitive matching is applied during extraction.
const List<String> _emotionalKeywords = [
  'stressed',
  'angry',
  'happy',
  'excited',
  'sad',
  'anxious',
  'frustrated',
  'worried',
  'overwhelmed',
  'grateful',
  'proud',
  'lonely',
  'confused',
  'hopeful',
  'tired',
  'exhausted',
  'energetic',
  'calm',
  'nervous',
];

/// Keywords that indicate social/relational content.
///
/// Includes both relationship words and common references to people.
/// Proper noun detection (capitalized words mid-sentence) is handled
/// separately in [extractCategory].
const List<String> _socialKeywords = [
  'he',
  'she',
  'they',
  'we',
  'mom',
  'dad',
  'brother',
  'sister',
  'friend',
  'boss',
  'coworker',
  'partner',
  'husband',
  'wife',
  'family',
];

/// Keywords that indicate work/project content.
const List<String> _workKeywords = [
  'meeting',
  'deadline',
  'project',
  'client',
  'boss',
  'presentation',
  'email',
  'office',
  'work',
  'job',
  'interview',
  'promotion',
  'salary',
  'task',
  'report',
];

/// Extract the dominant keyword category from a user message.
///
/// Applies case-insensitive whole-word matching against the keyword lists.
/// When multiple categories match, returns the highest-priority category:
///   emotional > social > work > none
///
/// Examples:
///   "I'm feeling stressed about the deadline" → KeywordCategory.emotional
///   "Had lunch with my mom today" → KeywordCategory.social
///   "Big presentation tomorrow" → KeywordCategory.work
///   "The weather is nice" → KeywordCategory.none
KeywordCategory extractCategory(String message) {
  if (message.isEmpty) return KeywordCategory.none;

  // Convert to lowercase for case-insensitive matching.
  final lower = message.toLowerCase();

  // Split into words for whole-word matching.
  // This prevents partial matches like "the" matching inside "therapist".
  final words = lower.split(RegExp(r'[\s,.\-!?;:]+'));

  // Check categories in priority order: emotional > social > work.
  // Return as soon as any keyword matches — the first match in priority
  // order determines the category.
  for (final keyword in _emotionalKeywords) {
    if (words.contains(keyword)) return KeywordCategory.emotional;
  }

  for (final keyword in _socialKeywords) {
    if (words.contains(keyword)) return KeywordCategory.social;
  }

  // Also check for proper nouns (capitalized words mid-sentence) as social.
  // Split original (not lowered) message to preserve case.
  final originalWords = message.split(RegExp(r'[\s,.\-!?;:]+'));
  if (originalWords.length > 1) {
    // Skip the first word (always capitalized at sentence start).
    for (var i = 1; i < originalWords.length; i++) {
      final word = originalWords[i];
      if (word.isNotEmpty &&
          word[0] == word[0].toUpperCase() &&
          word[0] != word[0].toLowerCase() &&
          word.length > 1) {
        // Capitalized word mid-sentence — likely a proper noun (person name).
        return KeywordCategory.social;
      }
    }
  }

  for (final keyword in _workKeywords) {
    if (words.contains(keyword)) return KeywordCategory.work;
  }

  return KeywordCategory.none;
}
