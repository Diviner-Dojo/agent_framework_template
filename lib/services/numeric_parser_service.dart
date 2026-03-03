// ===========================================================================
// file: lib/services/numeric_parser_service.dart
// purpose: Parse spoken/typed numeric responses for the Pulse Check-In voice
//          flow. Stateless pure function — no external dependencies.
//
// Accepts natural language input ("seven", "about a six", "I'd say a 7") and
// returns the integer value if it is within the active scale range, or null
// for out-of-range, non-numeric, empty, or explicit skip inputs.
//
// The parser is scale-aware: out-of-range detection uses the caller-supplied
// [scaleMin] and [scaleMax], not hardcoded 1-10 bounds. This supports custom
// templates with different scales (e.g., 1-100).
//
// Full 14-row input contract:
//   "7"                 → 7
//   "seven"             → 7
//   "um, like a 7"      → 7  (hedged digit)
//   "ten"               → 10 (upper bound, 1-10 scale)
//   "ten out of ten"    → 10 (qualified word form)
//   "about a six"       → 6  (hedged word form)
//   "I'd say a seven"   → 7  (conversational)
//   "zero"              → null (out of range, min=1)
//   "eleven"            → null (out of range, max=10)
//   "six point five"    → null (decimal — reject, do not round)
//   "I don't know"      → null (explicit uncertainty)
//   "skip"              → null (explicit skip)
//   ""                  → null (empty)
//   "  "                → null (whitespace only)
//
// See: SPEC-20260302-ADHD Phase 1 Task 6.
// ===========================================================================

/// Stateless service that parses numeric responses for the Pulse Check-In
/// voice flow.
///
/// All methods are pure functions — no state, no async, no side effects.
class NumericParserService {
  const NumericParserService();

  // ---------------------------------------------------------------------------
  // Word-to-number mapping (English cardinal numbers 0–100)
  // ---------------------------------------------------------------------------

  static const Map<String, int> _wordMap = {
    'zero': 0,
    'one': 1,
    'two': 2,
    'three': 3,
    'four': 4,
    'five': 5,
    'six': 6,
    'seven': 7,
    'eight': 8,
    'nine': 9,
    'ten': 10,
    'eleven': 11,
    'twelve': 12,
    'thirteen': 13,
    'fourteen': 14,
    'fifteen': 15,
    'sixteen': 16,
    'seventeen': 17,
    'eighteen': 18,
    'nineteen': 19,
    'twenty': 20,
    'thirty': 30,
    'forty': 40,
    'fifty': 50,
    'sixty': 60,
    'seventy': 70,
    'eighty': 80,
    'ninety': 90,
    'hundred': 100,
    // Common STT homophones / mishearing correction
    'too': 2,
    'to': 2,
    'for': 4,
    'ate': 8,
    'won': 1,
    'won\'t': 1,
    'nein': 9,
  };

  // ---------------------------------------------------------------------------
  // Explicit skip / uncertainty patterns
  // ---------------------------------------------------------------------------

  static final _skipPattern = RegExp(
    "\\b(skip|pass|n/?a|no answer|i don'?t know|not sure|unsure|unclear)\\b",
    caseSensitive: false,
  );

  // Reject decimal inputs (e.g., "six point five", "6.5")
  static final _decimalPattern = RegExp(
    r'\b\d+\.\d+\b|'
    r'\b(zero|one|two|three|four|five|six|seven|eight|nine|ten)\s+point\s+(zero|one|two|three|four|five|six|seven|eight|nine)\b',
    caseSensitive: false,
  );

  // ---------------------------------------------------------------------------
  // Public API
  // ---------------------------------------------------------------------------

  /// Parse [input] and return an integer within [[scaleMin], [scaleMax]],
  /// or null if the input cannot be mapped to a valid in-range value.
  ///
  /// Returns null for:
  /// - Empty or whitespace-only input
  /// - Explicit skip / uncertainty phrases ("skip", "I don't know")
  /// - Decimal inputs ("six point five", "6.5") — never rounded
  /// - Out-of-range values (below [scaleMin] or above [scaleMax])
  /// - Inputs that contain no recognizable numeric token
  int? parse(String input, {int scaleMin = 1, int scaleMax = 10}) {
    final trimmed = input.trim();
    if (trimmed.isEmpty) return null;

    // Reject explicit skips before attempting to extract a number.
    if (_skipPattern.hasMatch(trimmed)) return null;

    // Reject decimal inputs — do not round.
    if (_decimalPattern.hasMatch(trimmed)) return null;

    final value = _extractNumber(trimmed);
    if (value == null) return null;

    // Range check — null means out of range (not 0 or a sentinel).
    if (value < scaleMin || value > scaleMax) return null;

    return value;
  }

  // ---------------------------------------------------------------------------
  // Internal extraction
  // ---------------------------------------------------------------------------

  /// Attempt to extract a single integer from [input].
  ///
  /// Strategy:
  /// 1. Look for a bare digit sequence (e.g., "7", "um, like a 7", "3 of 6").
  ///    Returns the first digit sequence found if it is a standalone number
  ///    (not part of a fraction like "3 of 6" which would give 3, not 0.5).
  /// 2. Look for word forms from [_wordMap].
  /// 3. Handle compound word forms ("twenty one" → 21, "forty two" → 42).
  ///
  /// Returns null if no numeric token is found.
  int? _extractNumber(String input) {
    final lower = input.toLowerCase();

    // 1. Digit sequence — prefer explicit digit strings over word forms.
    final digitMatch = RegExp(r'\b(\d+)\b').firstMatch(lower);
    if (digitMatch != null) {
      return int.tryParse(digitMatch.group(1)!);
    }

    // 2. Word forms — single token lookup.
    for (final entry in _wordMap.entries) {
      // Full-word match to avoid "eight" matching inside "eighteen".
      final wordPattern = RegExp(r'\b' + RegExp.escape(entry.key) + r'\b');
      if (wordPattern.hasMatch(lower)) {
        // Check for compound: "twenty one", "forty two", etc.
        final compound = _extractCompound(lower, entry.key, entry.value);
        return compound ?? entry.value;
      }
    }

    return null;
  }

  /// Attempt to extract a compound word number (tens + units).
  ///
  /// Handles: "twenty one" → 21, "thirty three" → 33, etc.
  /// Returns null if no compound form is found after the tens word.
  int? _extractCompound(String lower, String tensWord, int tensValue) {
    if (tensValue < 20 || tensValue % 10 != 0) return null;

    // Look for a units word immediately after the tens word.
    final units = {
      'one': 1,
      'two': 2,
      'three': 3,
      'four': 4,
      'five': 5,
      'six': 6,
      'seven': 7,
      'eight': 8,
      'nine': 9,
    };

    for (final entry in units.entries) {
      final pattern = RegExp(
        r'\b' +
            RegExp.escape(tensWord) +
            r'\s*' +
            RegExp.escape(entry.key) +
            r'\b',
      );
      if (pattern.hasMatch(lower)) {
        return tensValue + entry.value;
      }
    }
    return null;
  }
}
