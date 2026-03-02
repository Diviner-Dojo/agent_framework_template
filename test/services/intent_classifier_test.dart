import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/services/intent_classifier.dart';

void main() {
  late IntentClassifier classifier;

  setUp(() {
    classifier = IntentClassifier();
  });

  group('IntentClassifier.classify', () {
    group('returns journal for non-query messages', () {
      test('empty string', () {
        final result = classifier.classify('');
        expect(result.type, IntentType.journal);
        expect(result.confidence, 0.0);
      });

      test('whitespace-only', () {
        final result = classifier.classify('   ');
        expect(result.type, IntentType.journal);
        expect(result.confidence, 0.0);
      });

      test('short conversational: "What?"', () {
        final result = classifier.classify('What?');
        expect(result.type, IntentType.journal);
      });

      test('short conversational: "Really?"', () {
        final result = classifier.classify('Really?');
        expect(result.type, IntentType.journal);
      });

      test('short conversational: "Why not?"', () {
        final result = classifier.classify('Why not?');
        expect(result.type, IntentType.journal);
      });

      test('temporal in social context: "I talked to her last week"', () {
        final result = classifier.classify(
          'I talked to her last week about the project',
        );
        expect(result.type, IntentType.journal);
      });

      test('recall verb in journal context: "I remember feeling happy"', () {
        final result = classifier.classify('I remember feeling happy today');
        expect(result.type, IntentType.journal);
      });

      test('recall verb in journal context: "I recall being nervous"', () {
        final result = classifier.classify('I recall being nervous');
        expect(result.type, IntentType.journal);
      });

      test('simple narrative statement', () {
        final result = classifier.classify(
          'Today was a good day at work with the team',
        );
        expect(result.type, IntentType.journal);
      });

      test('mixed case narrative', () {
        final result = classifier.classify(
          'I Had A Really Great Conversation With My Boss Today',
        );
        expect(result.type, IntentType.journal);
      });

      test('"Tell me more" is journal (short, no strong signal)', () {
        final result = classifier.classify('Tell me more');
        expect(result.type, IntentType.journal);
      });

      test('single-signal recall verb without question structure', () {
        // "Find entries about anxiety" — only scores 0.35 from recall verb.
        // Below 0.5 threshold, so conservative default to journal.
        final result = classifier.classify('Find entries about anxiety');
        expect(result.type, IntentType.journal);
        // But it should have some confidence that it's NOT journal.
      });
    });

    group('returns query for multi-signal recall messages', () {
      test(
        'question + past tense + temporal: "What did I do last Thursday?"',
        () {
          // questionPastPattern (+0.4) + temporalPattern with question (+0.3)
          final result = classifier.classify('What did I do last Thursday?');
          expect(result.type, IntentType.query);
          expect(result.confidence, greaterThanOrEqualTo(0.5));
          expect(result.searchTerms, isNotEmpty);
        },
      );

      test('question + past tense: "What did I write about work?"', () {
        // questionPastPattern: "what...did i" → +0.4
        // Plus "?" → question structure.
        final result = classifier.classify(
          'What did I write about work last week?',
        );
        expect(result.type, IntentType.query);
        expect(result.confidence, greaterThanOrEqualTo(0.5));
      });

      test(
        'recall + question: "Do you remember when I talked about work?"',
        () {
          // recallVerbPattern (+0.35) as query context.
          // questionPastPattern may also match.
          final result = classifier.classify(
            'Do you remember when I talked about work?',
          );
          expect(result.type, IntentType.query);
        },
      );

      test('temporal + question: "What did I write about last week?"', () {
        final result = classifier.classify('What did I write about last week?');
        expect(result.type, IntentType.query);
      });

      test('recall with trailing question mark adds recall score', () {
        // Must be >4 words to pass short-message guard.
        // "remember" triggers _recallVerbPattern, question mark triggers the
        // endsWith('?') fallback in _isRecallAsQuery.
        final result = classifier.classify(
          'You said you remember something about that trip?',
        );
        expect(result.confidence, greaterThan(0));
      });

      test('past tense only scores 0.4 — below threshold', () {
        // Single-signal (questionPast at 0.4) → journal (conservative default).
        final result = classifier.classify(
          'What did I say when I talked to Mike?',
        );
        expect(result.type, IntentType.journal);
      });

      test('handles mixed case query', () {
        final result = classifier.classify('WHAT DID I DO YESTERDAY?');
        expect(result.type, IntentType.query);
      });
    });

    group('meta-question patterns', () {
      test('single meta-question signal (0.45) stays below threshold', () {
        // metaQuestionPattern (+0.45) alone is below 0.5 threshold.
        // Conservative default: treat as journal.
        final result = classifier.classify(
          'How often do I mention feeling stressed about work?',
        );
        expect(result.type, IntentType.journal);
      });

      test('"Do I ever talk about exercise?" is single-signal → journal', () {
        // metaQuestionPattern "do i ever" → +0.45, below threshold.
        final result = classifier.classify(
          'Do I ever talk about exercise in my journal?',
        );
        expect(result.type, IntentType.journal);
      });

      test(
        '"How many times have I mentioned anxiety?" combines two signals',
        () {
          // metaQuestionPattern "how many times" → +0.45
          // questionPastPattern "how...have i" + "i mentioned" → +0.4
          // Total: 0.85 → query
          final result = classifier.classify(
            'How many times have I mentioned anxiety?',
          );
          expect(result.type, IntentType.query);
        },
      );

      test('meta-question + past tense reaches query threshold', () {
        // "How often did I mention..." → metaQuestion (+0.45) + questionPast (+0.4)
        final result = classifier.classify(
          'How often did I mention feeling stressed about work?',
        );
        expect(result.type, IntentType.query);
        expect(result.confidence, greaterThanOrEqualTo(0.5));
      });
    });

    group('search terms extraction', () {
      test('extracts meaningful terms from query', () {
        final result = classifier.classify(
          'What did I write about work last week?',
        );
        expect(result.type, IntentType.query);
        expect(result.searchTerms, isNotEmpty);
        // Should contain "work" after stripping question words.
        expect(
          result.searchTerms.any((t) => t.toLowerCase().contains('work')),
          isTrue,
        );
      });

      test('journal messages have empty search terms', () {
        final result = classifier.classify(
          'Today was a wonderful day and I feel grateful for everything',
        );
        expect(result.type, IntentType.journal);
        expect(result.searchTerms, isEmpty);
      });
    });

    group('confidence values', () {
      test('empty input has 0 confidence', () {
        final result = classifier.classify('');
        expect(result.confidence, 0.0);
      });

      test('journal messages have confidence > 0', () {
        final result = classifier.classify(
          'Today was a wonderful day and I feel grateful for everything',
        );
        expect(result.type, IntentType.journal);
        expect(result.confidence, greaterThan(0.0));
      });

      test('strong query has high confidence', () {
        // Multiple signals: questionPast + temporal.
        final result = classifier.classify('What did I do last Thursday?');
        expect(result.type, IntentType.query);
        expect(result.confidence, greaterThanOrEqualTo(0.7));
      });
    });

    group('temporal modifier with future action context', () {
      test(
        'future action verb + temporal gives sub-threshold calendar signal',
        () {
          // "I need to create something awesome for tomorrow" has:
          //   - No explicit calendar intent pattern ("create" is not in the
          //     calendar intent verb list)
          //   - Temporal pattern ("tomorrow")
          //   - Future action context ("need to create" matches
          //     _hasFutureActionContext's intent expression pattern)
          // This should give a sub-threshold calendar signal via the temporal
          // modifier's _hasFutureActionContext branch.
          final results = classifier.classifyMulti(
            'I need to create something awesome for tomorrow',
          );
          // Primary intent is journal (calendar sub-threshold).
          expect(results.first.type, IntentType.journal);
          // Should include a sub-threshold calendar intent.
          final calendarResults = results.where(
            (r) => r.type == IntentType.calendarEvent,
          );
          expect(calendarResults, isNotEmpty);
          expect(calendarResults.first.confidence, lessThan(0.5));
          expect(calendarResults.first.confidence, greaterThan(0.0));
        },
      );
    });
  });

  // Regression tests — calendar intent detection with "Google Calendar" modifier.
  // Bug: "Add a Google Calendar meeting" bypassed intent routing and reached Claude
  // because "a Google Calendar " (19 chars) exceeded the .{0,15} character limit.
  // Fix: added (google\s+)?calendar sub-pattern and (google\s+)? to "to ... calendar".
  // Follow-up: "set" added alongside "add" — "set a calendar meeting" was not matched.
  group('calendar intent with Google Calendar modifier (regression)', () {
    test(
      '"Add a Google Calendar meeting" is classified as calendarEvent (regression)',
      () {
        final result = classifier.classify('Add a Google Calendar meeting');
        expect(result.type, IntentType.calendarEvent);
        expect(result.confidence, greaterThanOrEqualTo(0.5));
      },
    );

    test(
      '"Add a Google Calendar meeting tomorrow at 2pm" has high confidence',
      () {
        final result = classifier.classify(
          'Add a Google Calendar meeting tomorrow at 2pm',
        );
        expect(result.type, IntentType.calendarEvent);
        expect(result.confidence, greaterThanOrEqualTo(0.8));
      },
    );

    test(
      '"Add a meeting to my Google Calendar" is classified as calendarEvent',
      () {
        final result = classifier.classify(
          'Add a meeting to my Google Calendar',
        );
        expect(result.type, IntentType.calendarEvent);
        expect(result.confidence, greaterThanOrEqualTo(0.5));
      },
    );

    test(
      '"Schedule a Google Calendar appointment" is classified as calendarEvent',
      () {
        final result = classifier.classify(
          'Schedule a Google Calendar appointment for next Monday',
        );
        expect(result.type, IntentType.calendarEvent);
        expect(result.confidence, greaterThanOrEqualTo(0.5));
      },
    );

    test(
      '"Set a calendar meeting" is classified as calendarEvent (regression)',
      () {
        final result = classifier.classify('Set a calendar meeting');
        expect(result.type, IntentType.calendarEvent);
        expect(result.confidence, greaterThanOrEqualTo(0.5));
      },
    );

    test('"Set a Google Calendar meeting" is classified as calendarEvent', () {
      final result = classifier.classify('Set a Google Calendar meeting');
      expect(result.type, IntentType.calendarEvent);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });
  });
}
