// ===========================================================================
// file: test/services/voice_command_classifier_test.dart
// purpose: Tests for VoiceCommandClassifier rule-based command detection.
//
// Tests cover:
//   - End-session command patterns (confident and ambiguous)
//   - Discard command patterns
//   - Undo command patterns
//   - False positives ("I'm done with X" should be low confidence)
//   - Edge cases: empty, single word, punctuation
//   - Case insensitivity
// ===========================================================================

import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/services/voice_command_classifier.dart';

void main() {
  late VoiceCommandClassifier classifier;

  setUp(() {
    classifier = VoiceCommandClassifier();
  });

  group('VoiceCommandClassifier', () {
    group('none (normal input)', () {
      test('returns none for empty string', () {
        final result = classifier.classify('');
        expect(result.command, VoiceCommand.none);
        expect(result.confidence, 0.0);
      });

      test('returns none for whitespace-only', () {
        final result = classifier.classify('   ');
        expect(result.command, VoiceCommand.none);
        expect(result.confidence, 0.0);
      });

      test('returns none for normal journal input', () {
        final result = classifier.classify('I had a great day at work today');
        expect(result.command, VoiceCommand.none);
      });

      test('returns none for single unrelated word', () {
        final result = classifier.classify('hello');
        expect(result.command, VoiceCommand.none);
      });

      test('returns none for question about journal', () {
        final result = classifier.classify('What did I write about yesterday?');
        expect(result.command, VoiceCommand.none);
      });
    });

    group('endSession', () {
      test('high confidence for "I\'m done"', () {
        final result = classifier.classify("I'm done");
        expect(result.command, VoiceCommand.endSession);
        expect(result.confidence, greaterThanOrEqualTo(0.8));
      });

      test('high confidence for "goodbye"', () {
        final result = classifier.classify('goodbye');
        expect(result.command, VoiceCommand.endSession);
        expect(result.confidence, greaterThanOrEqualTo(0.8));
      });

      test('high confidence for "that\'s all"', () {
        final result = classifier.classify("that's all");
        expect(result.command, VoiceCommand.endSession);
        expect(result.confidence, greaterThanOrEqualTo(0.8));
      });

      test('high confidence for "wrap it up"', () {
        final result = classifier.classify('wrap it up');
        expect(result.command, VoiceCommand.endSession);
        expect(result.confidence, greaterThanOrEqualTo(0.8));
      });

      test('high confidence for "end session"', () {
        final result = classifier.classify('end session');
        expect(result.command, VoiceCommand.endSession);
        expect(result.confidence, greaterThanOrEqualTo(0.8));
      });

      test('high confidence for "done for today"', () {
        final result = classifier.classify('done for today');
        expect(result.command, VoiceCommand.endSession);
        expect(result.confidence, greaterThanOrEqualTo(0.8));
      });

      test('moderate confidence for "I think I\'m done"', () {
        final result = classifier.classify("I think I'm done");
        expect(result.command, VoiceCommand.endSession);
        expect(result.confidence, lessThan(0.8));
        expect(result.confidence, greaterThanOrEqualTo(0.5));
      });

      test('moderate confidence for "let\'s stop"', () {
        final result = classifier.classify("let's stop");
        expect(result.command, VoiceCommand.endSession);
        expect(result.confidence, lessThan(0.8));
      });

      test(
        'returns none for "I\'m done with the dishes" (topic, not command)',
        () {
          final result = classifier.classify("I'm done with the dishes");
          // Longer phrase does not match ^..$ anchored strong pattern.
          expect(result.command, VoiceCommand.none);
        },
      );

      test('returns none for "I\'m done talking about work" (narrative)', () {
        final result = classifier.classify("I'm done talking about work");
        // Longer phrase does not match ^..$ anchored strong pattern.
        expect(result.command, VoiceCommand.none);
      });

      test('strips trailing punctuation', () {
        final result = classifier.classify("I'm done.");
        expect(result.command, VoiceCommand.endSession);
        expect(result.confidence, greaterThanOrEqualTo(0.8));
      });

      test('case insensitive', () {
        final result = classifier.classify("I'M DONE");
        expect(result.command, VoiceCommand.endSession);
        expect(result.confidence, greaterThanOrEqualTo(0.8));
      });

      test('high confidence for "I am finished"', () {
        final result = classifier.classify('I am finished');
        expect(result.command, VoiceCommand.endSession);
        expect(result.confidence, greaterThanOrEqualTo(0.8));
      });

      test('moderate confidence for "bye" (common word)', () {
        final result = classifier.classify('bye');
        expect(result.command, VoiceCommand.endSession);
        expect(result.confidence, lessThan(0.8));
        expect(result.confidence, greaterThanOrEqualTo(0.5));
      });

      test('moderate confidence for "stop" (common word)', () {
        final result = classifier.classify('stop');
        expect(result.command, VoiceCommand.endSession);
        expect(result.confidence, lessThan(0.8));
        expect(result.confidence, greaterThanOrEqualTo(0.5));
      });

      test('moderate confidence for "finish" (common word)', () {
        final result = classifier.classify('finish');
        expect(result.command, VoiceCommand.endSession);
        expect(result.confidence, lessThan(0.8));
        expect(result.confidence, greaterThanOrEqualTo(0.5));
      });
    });

    group('discard', () {
      test('high confidence for "delete this"', () {
        final result = classifier.classify('delete this');
        expect(result.command, VoiceCommand.discard);
        expect(result.confidence, greaterThanOrEqualTo(0.8));
      });

      test('high confidence for "discard"', () {
        final result = classifier.classify('discard');
        expect(result.command, VoiceCommand.discard);
        expect(result.confidence, greaterThanOrEqualTo(0.8));
      });

      test('high confidence for "throw it away"', () {
        final result = classifier.classify('throw it away');
        expect(result.command, VoiceCommand.discard);
        expect(result.confidence, greaterThanOrEqualTo(0.8));
      });

      test('high confidence for "scrap this"', () {
        final result = classifier.classify('scrap this');
        expect(result.command, VoiceCommand.discard);
        expect(result.confidence, greaterThanOrEqualTo(0.8));
      });

      test('high confidence for "erase everything"', () {
        final result = classifier.classify('erase everything');
        expect(result.command, VoiceCommand.discard);
        expect(result.confidence, greaterThanOrEqualTo(0.8));
      });

      test('moderate confidence for "delete this entry"', () {
        final result = classifier.classify('delete this entry');
        expect(result.command, VoiceCommand.discard);
        expect(result.confidence, greaterThanOrEqualTo(0.5));
      });

      test('moderate confidence for "don\'t save this"', () {
        final result = classifier.classify("don't save this");
        expect(result.command, VoiceCommand.discard);
        expect(result.confidence, greaterThanOrEqualTo(0.5));
      });

      test('moderate confidence for "get rid of this"', () {
        final result = classifier.classify('get rid of this');
        expect(result.command, VoiceCommand.discard);
        expect(result.confidence, greaterThanOrEqualTo(0.5));
      });

      test('case insensitive', () {
        final result = classifier.classify('DELETE THIS');
        expect(result.command, VoiceCommand.discard);
        expect(result.confidence, greaterThanOrEqualTo(0.8));
      });

      test('strips trailing punctuation', () {
        final result = classifier.classify('discard!');
        expect(result.command, VoiceCommand.discard);
        expect(result.confidence, greaterThanOrEqualTo(0.8));
      });
    });

    group('undo', () {
      test('high confidence for "undo"', () {
        final result = classifier.classify('undo');
        expect(result.command, VoiceCommand.undo);
        expect(result.confidence, greaterThanOrEqualTo(0.8));
      });

      test('high confidence for "go back"', () {
        final result = classifier.classify('go back');
        expect(result.command, VoiceCommand.undo);
        expect(result.confidence, greaterThanOrEqualTo(0.8));
      });

      test('high confidence for "take it back"', () {
        final result = classifier.classify('take it back');
        expect(result.command, VoiceCommand.undo);
        expect(result.confidence, greaterThanOrEqualTo(0.8));
      });

      test('high confidence for "reopen"', () {
        final result = classifier.classify('reopen');
        expect(result.command, VoiceCommand.undo);
        expect(result.confidence, greaterThanOrEqualTo(0.8));
      });

      test('high confidence for "continue my journal"', () {
        final result = classifier.classify('continue my journal');
        expect(result.command, VoiceCommand.undo);
        expect(result.confidence, greaterThanOrEqualTo(0.8));
      });

      test('moderate confidence for "undo that"', () {
        final result = classifier.classify('undo that');
        expect(result.command, VoiceCommand.undo);
        expect(result.confidence, greaterThanOrEqualTo(0.5));
      });

      test('moderate confidence for "take that back"', () {
        final result = classifier.classify('take that back');
        expect(result.command, VoiceCommand.undo);
        expect(result.confidence, greaterThanOrEqualTo(0.5));
      });

      test("moderate confidence for \"wait I'm not done\"", () {
        final result = classifier.classify("wait I'm not done");
        expect(result.command, VoiceCommand.undo);
        expect(result.confidence, greaterThanOrEqualTo(0.5));
      });

      test('case insensitive', () {
        final result = classifier.classify('UNDO');
        expect(result.command, VoiceCommand.undo);
        expect(result.confidence, greaterThanOrEqualTo(0.8));
      });

      test('strips trailing punctuation', () {
        final result = classifier.classify('undo!');
        expect(result.command, VoiceCommand.undo);
        expect(result.confidence, greaterThanOrEqualTo(0.8));
      });
    });

    group('VoiceCommandResult toString', () {
      test('formats correctly', () {
        const result = VoiceCommandResult(
          command: VoiceCommand.endSession,
          confidence: 0.9,
        );
        expect(
          result.toString(),
          'VoiceCommandResult(command: VoiceCommand.endSession, confidence: 0.9)',
        );
      });
    });
  });
}
