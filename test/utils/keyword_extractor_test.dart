import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/utils/keyword_extractor.dart';

void main() {
  group('extractCategory', () {
    test('detects emotional keywords', () {
      expect(
        extractCategory('I feel stressed today'),
        KeywordCategory.emotional,
      );
      expect(extractCategory('So happy right now'), KeywordCategory.emotional);
      expect(extractCategory('I am really anxious'), KeywordCategory.emotional);
    });

    test('detects social keywords', () {
      expect(extractCategory('Had lunch with mom'), KeywordCategory.social);
      expect(extractCategory('My friend called me'), KeywordCategory.social);
      expect(extractCategory('She told me something'), KeywordCategory.social);
    });

    test('detects work keywords', () {
      expect(extractCategory('Big meeting tomorrow'), KeywordCategory.work);
      // Note: "The deadline is Friday" would detect "Friday" as a proper noun
      // (social category). This is a known limitation of simple capitalization
      // detection — Phase 3's AI will handle this correctly.
      expect(
        extractCategory('I have a deadline coming up'),
        KeywordCategory.work,
      );
      expect(
        extractCategory('need to finish this presentation'),
        KeywordCategory.work,
      );
    });

    test('prioritizes emotional over social and work', () {
      // Contains both emotional ("stressed") and work ("deadline").
      expect(
        extractCategory("I'm stressed about the deadline"),
        KeywordCategory.emotional,
      );
    });

    test('prioritizes social over work', () {
      // Contains both social ("boss") and work ("meeting") — but "boss"
      // appears in both lists. Social list is checked first, so social wins.
      expect(
        extractCategory('My friend has a meeting'),
        KeywordCategory.social,
      );
    });

    test('is case insensitive', () {
      expect(extractCategory('STRESSED'), KeywordCategory.emotional);
      expect(extractCategory('Stressed'), KeywordCategory.emotional);
      expect(extractCategory('stressed'), KeywordCategory.emotional);
    });

    test('returns none for empty string', () {
      expect(extractCategory(''), KeywordCategory.none);
    });

    test('returns none for input with no matching keywords', () {
      expect(extractCategory('The weather is nice'), KeywordCategory.none);
      expect(extractCategory('I ate pizza for lunch'), KeywordCategory.none);
    });

    test('detects proper nouns mid-sentence as social', () {
      // "Mike" is capitalized mid-sentence → detected as proper noun.
      expect(
        extractCategory('I talked to Mike about it'),
        KeywordCategory.social,
      );
    });
  });
}
