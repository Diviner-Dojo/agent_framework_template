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

  // ===========================================================================
  // Sprint N+1 regression tests: word-count wildcard + voice preamble anchor.
  //
  // Root cause: .{0,15} char-count wildcard in both _calendarIntentPattern and
  // _hasStrongCalendarSignal broke for brand-modifier calendar names whose
  // prefix exceeds 15 chars ("an Outlook Calendar " = 20 chars).
  //
  // Fix: replaced with (\s+[\w-]+){0,4} word-count wildcard (brand-agnostic,
  // handles hyphenated tokens like "follow-up" as a single word).
  // Also: ^ anchor → \b in _calendarIntentPattern only (voice preamble support).
  // _hasStrongCalendarSignal retains ^ anchor (short-message guard intent).
  // Both locations updated together via _calendarEventNouns shared constant.
  // See SPEC-20260303-010332, DISC-20260303-011131.
  // ===========================================================================
  group('word-count wildcard and voice preamble anchor regressions', () {
    // --- Brand-name calendar tests (long-message path, >4 words) ---
    // These exercise _calendarIntentPattern directly (skips short-message guard).

    test(
      '"Add an Outlook Calendar meeting" classified as calendarEvent (regression)',
      () {
        final result = classifier.classify('Add an Outlook Calendar meeting');
        expect(result.type, IntentType.calendarEvent);
        expect(result.confidence, greaterThanOrEqualTo(0.5));
      },
    );

    test(
      '"Set an iCloud Calendar appointment" classified as calendarEvent (regression)',
      () {
        final result = classifier.classify(
          'Set an iCloud Calendar appointment',
        );
        expect(result.type, IntentType.calendarEvent);
        expect(result.confidence, greaterThanOrEqualTo(0.5));
      },
    );

    // --- Short-message guard path (≤4 words, exercises _hasStrongCalendarSignal) ---

    test(
      '"Add an Outlook meeting" (4 words) classified as calendarEvent via short-message guard (regression)',
      () {
        final result = classifier.classify('Add an Outlook meeting');
        expect(result.type, IntentType.calendarEvent);
        expect(result.confidence, greaterThanOrEqualTo(0.5));
      },
    );

    test(
      '"Set an iCloud call" (4 words) classified as calendarEvent via short-message guard (regression)',
      () {
        final result = classifier.classify('Set an iCloud call');
        expect(result.type, IntentType.calendarEvent);
        expect(result.confidence, greaterThanOrEqualTo(0.5));
      },
    );

    // --- Voice preamble (^ → \b anchor change in _calendarIntentPattern) ---

    test(
      '"Okay add a meeting tomorrow" classified as calendarEvent (voice preamble regression)',
      () {
        final result = classifier.classify('Okay add a meeting tomorrow');
        expect(result.type, IntentType.calendarEvent);
        expect(result.confidence, greaterThanOrEqualTo(0.5));
      },
    );

    // --- Word-count boundary (4-word modifier, at the {0,4} limit) ---

    test(
      '"Add a new Google Calendar meeting" (4-word modifier) classified as calendarEvent (boundary)',
      () {
        final result = classifier.classify('Add a new Google Calendar meeting');
        expect(result.type, IntentType.calendarEvent);
        expect(result.confidence, greaterThanOrEqualTo(0.5));
      },
    );

    // --- False-positive guards (de-anchored \b must not match non-calendar) ---

    test(
      '"I set a record at the gym today" classified as journal (false-positive guard)',
      () {
        final result = classifier.classify('I set a record at the gym today');
        expect(result.type, IntentType.journal);
      },
    );

    test(
      '"She asked me to add notes to the doc" classified as journal (false-positive guard)',
      () {
        final result = classifier.classify(
          'She asked me to add notes to the doc',
        );
        expect(result.type, IntentType.journal);
      },
    );

    test(
      '"Add a really very long extra meeting" (5-word modifier) classified as journal (out-of-bounds guard)',
      () {
        // 5 intervening words: "a", "really", "very", "long", "extra" — exceeds
        // the {0,4} word-count limit, so the wildcard sub-pattern does not match.
        // No other strong calendar signal present, so falls to journal.
        final result = classifier.classify(
          'Add a really very long extra meeting',
        );
        expect(result.type, IntentType.journal);
      },
    );

    // --- Word-count new-territory FP documentation (SPEC-20260303-010332 risk table) ---
    // The word-count wildcard is broader than the prior .{0,15} char-count pattern.
    // "Add context to the call summary" (4 intervening words before 'call', a
    // _calendarEventNouns member) now matches. This is accepted behavior: the
    // confirmation gate (ADR-0020 §8) prevents auto-creation; the message reaches
    // specialist routing for human decision rather than silent incorrect action.
    // This test DOCUMENTS the tradeoff — it is not a failing assertion.
    test(
      '"Add context to the call summary" classifies as calendarEvent (new word-count FP territory, accepted via confirmation gate)',
      () {
        final result = classifier.classify('Add context to the call summary');
        // The wildcard matches 'add [context to the] call' (3 intervening words).
        // This is accepted: the confirmation gate (ADR-0020 §8) backstops it.
        expect(result.type, IntentType.calendarEvent);
        expect(result.confidence, equals(0.5)); // No temporal boost.
      },
    );
  });

  // Regression: "add a task to call mom in 10 minutes" was routed as journal.
  // Root cause: _temporalPattern did not include relative duration expressions
  // ("in N minutes/hours"), so the temporal boost (+0.15) never fired, leaving
  // the task score sub-threshold in some inputs.
  // Fix: Added "in \d+ (minute|...)" and "in (a|an) (minute|...)" alternates
  // to _temporalPattern.
  group('in N minutes routed as task (temporal boost fires) (regression)', () {
    test(
      '"add a task to call mom in 10 minutes" classifies as task (regression)',
      tags: ['regression'],
      () {
        final result = classifier.classify(
          'add a task to call mom in 10 minutes',
        );
        expect(result.type, IntentType.task);
        expect(
          result.confidence,
          greaterThanOrEqualTo(0.5),
          reason: 'temporal boost must fire for "in 10 minutes"',
        );
      },
    );

    test('"add a task in 2 hours" classifies as task', () {
      final result = classifier.classify('add a task in 2 hours');
      expect(result.type, IntentType.task);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"add a task in an hour" classifies as task', () {
      final result = classifier.classify('add a task in an hour');
      expect(result.type, IntentType.task);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"add a task in a minute" classifies as task', () {
      final result = classifier.classify('add a task in a minute');
      expect(result.type, IntentType.task);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });
  });

  // Regression: "I need to set a calendar item for Friday night with Shawn"
  // was routed as journal — three gaps:
  //   1. "calendar item" not matched (only explicit event nouns like "meeting")
  //   2. "Friday night" not in _futureTemporalPattern (only "on friday", "tonight")
  //   3. _hasFutureActionContext didn't include "set"/"make" verbs
  // Fix: Added \bcalendar\s+(item|entry)\b compound pattern to _calendarIntentPattern;
  //      added weekday+time-of-day, this-weekday, for-weekday to temporal patterns;
  //      added |set|make to _hasFutureActionContext.
  // See: memory/bugs/regression-ledger.md — 'Calendar item / Friday night not recognized'
  group('calendar item and weekday temporal patterns (regression)', () {
    test(
      '"I need to set a calendar item for Friday night with Shawn" classifies as calendarEvent (regression)',
      tags: ['regression'],
      () {
        final result = classifier.classify(
          'I need to set a calendar item for Friday night with Shawn',
        );
        expect(result.type, IntentType.calendarEvent);
        expect(
          result.confidence,
          greaterThanOrEqualTo(0.5),
          reason: '"calendar item" compound pattern must fire',
        );
      },
    );

    test(
      '"I want to create a calendar entry for Saturday morning" classifies as calendarEvent',
      () {
        final result = classifier.classify(
          'I want to create a calendar entry for Saturday morning',
        );
        expect(result.type, IntentType.calendarEvent);
        expect(result.confidence, greaterThanOrEqualTo(0.5));
      },
    );

    test('"add a dinner for Friday evening" classifies as calendarEvent', () {
      // event noun "dinner" + future temporal "friday evening" → +0.4 boost
      final result = classifier.classify('add a dinner for Friday evening');
      expect(result.type, IntentType.calendarEvent);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"set a meeting for this Friday" classifies as calendarEvent', () {
      // "set a meeting" (event noun) + "this friday" (future temporal)
      final result = classifier.classify('set a meeting for this Friday');
      expect(result.type, IntentType.calendarEvent);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test(
      '"I had a meeting last week" still classifies as journal (no regression)',
      () {
        // Past temporal with no scheduling verb — must route to journal.
        final result = classifier.classify('I had a meeting last week');
        expect(result.type, IntentType.journal);
      },
    );

    // False-positive guards for the \bcalendar\s+(item|entry)\b compound pattern.
    // The pattern requires a scheduling verb (preceding) or future-temporal preposition
    // (following) to prevent past-narrative sentences from triggering calendarEvent.
    test(
      '"I remember we had a calendar item last week" classifies as journal (false-positive guard)',
      () {
        final result = classifier.classify(
          'I remember we had a calendar item last week',
        );
        expect(
          result.type,
          IntentType.journal,
          reason:
              '"calendar item" without scheduling verb must not route as calendar',
        );
      },
    );

    test(
      '"The calendar entry got deleted" classifies as journal (false-positive guard)',
      () {
        final result = classifier.classify('The calendar entry got deleted');
        expect(result.type, IntentType.journal);
      },
    );

    test(
      '"I need to set a calendar entry for next Monday" classifies as calendarEvent',
      () {
        // Isolates the calendar-entry compound noun pattern (verb arm fires).
        final result = classifier.classify(
          'I need to set a calendar entry for next Monday',
        );
        expect(result.type, IntentType.calendarEvent);
        expect(result.confidence, greaterThanOrEqualTo(0.5));
      },
    );

    test(
      '"I need to make a reservation for Saturday night" classifies as calendarEvent',
      () {
        // "make" added to _hasFutureActionContext; "reservation" is an event noun.
        final result = classifier.classify(
          'I need to make a reservation for Saturday night',
        );
        expect(result.type, IntentType.calendarEvent);
        expect(result.confidence, greaterThanOrEqualTo(0.5));
      },
    );

    test(
      '"I need to make a note about this Friday" classifies as journal (false-positive guard)',
      () {
        // "need to make" fires _hasFutureActionContext, "this friday" fires temporal.
        // But "note" is not in _eventNounPattern and calendarIntentPattern does not
        // match — so calendarScore should stay 0 and temporal boost should not fire.
        final result = classifier.classify(
          'I need to make a note about this Friday',
        );
        expect(
          result.type,
          isNot(IntentType.calendarEvent),
          reason: '"need to make a note" must not route as calendar',
        );
      },
    );
  });
}
