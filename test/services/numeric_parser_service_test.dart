// ===========================================================================
// file: test/services/numeric_parser_service_test.dart
// purpose: Unit tests for NumericParserService — full 14-row input contract
//          from SPEC-20260302-ADHD Phase 1 Task 6.
// ===========================================================================

import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/services/numeric_parser_service.dart';

void main() {
  late NumericParserService parser;

  setUp(() {
    parser = const NumericParserService();
  });

  // ---------------------------------------------------------------------------
  // Full 14-row input contract from spec (1-10 scale)
  // ---------------------------------------------------------------------------

  group('14-row input contract (scaleMin=1, scaleMax=10)', () {
    int? parse(String input) => parser.parse(input, scaleMin: 1, scaleMax: 10);

    test('"7" → 7 (digit string)', () {
      expect(parse('7'), 7);
    });

    test('"seven" → 7 (word form)', () {
      expect(parse('seven'), 7);
    });

    test('"um, like a 7" → 7 (hedged digit)', () {
      expect(parse('um, like a 7'), 7);
    });

    test('"ten" → 10 (upper bound)', () {
      expect(parse('ten'), 10);
    });

    test('"ten out of ten" → 10 (qualified word form)', () {
      expect(parse('ten out of ten'), 10);
    });

    test('"about a six" → 6 (hedged word form)', () {
      expect(parse('about a six'), 6);
    });

    test('"I\'d say a seven" → 7 (conversational form)', () {
      expect(parse("I'd say a seven"), 7);
    });

    test('"zero" → null (out of range, min=1)', () {
      expect(parse('zero'), isNull);
    });

    test('"eleven" → null (out of range, max=10)', () {
      expect(parse('eleven'), isNull);
    });

    test('"six point five" → null (decimal rejected)', () {
      expect(parse('six point five'), isNull);
    });

    test('"I don\'t know" → null (explicit uncertainty)', () {
      expect(parse("I don't know"), isNull);
    });

    test('"skip" → null (explicit skip)', () {
      expect(parse('skip'), isNull);
    });

    test('"" → null (empty string)', () {
      expect(parse(''), isNull);
    });

    test('"  " → null (whitespace only)', () {
      expect(parse('  '), isNull);
    });
  });

  // ---------------------------------------------------------------------------
  // Scale-aware: out-of-range depends on active template bounds
  // ---------------------------------------------------------------------------

  group('scale-aware range validation', () {
    test('zero is valid on 0-10 scale', () {
      expect(parser.parse('zero', scaleMin: 0, scaleMax: 10), 0);
    });

    test('eleven is valid on 1-100 scale', () {
      expect(parser.parse('eleven', scaleMin: 1, scaleMax: 100), 11);
    });

    test('5 is invalid on 7-10 scale', () {
      expect(parser.parse('5', scaleMin: 7, scaleMax: 10), isNull);
    });

    test('upper bound on 1-100 scale accepts 100', () {
      expect(parser.parse('100', scaleMin: 1, scaleMax: 100), 100);
    });
  });

  // ---------------------------------------------------------------------------
  // Additional coverage
  // ---------------------------------------------------------------------------

  group('additional patterns', () {
    test('digit with surrounding words', () {
      expect(parser.parse('I would say 8', scaleMin: 1, scaleMax: 10), 8);
    });

    test('pass → null (explicit skip)', () {
      expect(parser.parse('pass', scaleMin: 1, scaleMax: 10), isNull);
    });

    test('n/a → null (explicit skip)', () {
      expect(parser.parse('n/a', scaleMin: 1, scaleMax: 10), isNull);
    });

    test('decimal digit string rejected', () {
      // "6.5" should not match — callers must re-prompt
      expect(parser.parse('6.5', scaleMin: 1, scaleMax: 10), isNull);
    });

    test('picks first valid number from multi-word response', () {
      // "about 7 or maybe 8" → should return 7 (first valid)
      final result = parser.parse(
        'about 7 or maybe 8',
        scaleMin: 1,
        scaleMax: 10,
      );
      expect(result, 7);
    });

    test('one → 1 (lower bound)', () {
      expect(parser.parse('one', scaleMin: 1, scaleMax: 10), 1);
    });

    test('not sure → null', () {
      expect(parser.parse('not sure', scaleMin: 1, scaleMax: 10), isNull);
    });
  });
}
