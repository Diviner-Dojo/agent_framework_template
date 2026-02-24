import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/services/intent_classifier.dart';

void main() {
  late IntentClassifier classifier;

  setUp(() {
    classifier = IntentClassifier();
  });

  // =========================================================================
  // Step 2a: Recall regression suite — must not change.
  //
  // These test cases are extracted from intent_classifier_test.dart and pin
  // both expected intent types AND minimum confidence values. Any classifier
  // change that causes a regression here is a blocking failure.
  // =========================================================================
  group('recall regression suite — must not change', () {
    // --- Journal cases (must remain journal) ---

    test('empty string → journal, confidence 0.0', () {
      final result = classifier.classify('');
      expect(result.type, IntentType.journal);
      expect(result.confidence, 0.0);
    });

    test('whitespace-only → journal, confidence 0.0', () {
      final result = classifier.classify('   ');
      expect(result.type, IntentType.journal);
      expect(result.confidence, 0.0);
    });

    test('"What?" → journal (short conversational)', () {
      final result = classifier.classify('What?');
      expect(result.type, IntentType.journal);
      expect(result.confidence, 0.1);
    });

    test('"Really?" → journal (short conversational)', () {
      final result = classifier.classify('Really?');
      expect(result.type, IntentType.journal);
      expect(result.confidence, 0.1);
    });

    test('"Why not?" → journal (short conversational)', () {
      final result = classifier.classify('Why not?');
      expect(result.type, IntentType.journal);
      expect(result.confidence, 0.1);
    });

    test('"Tell me more" → journal (short, no strong signal)', () {
      final result = classifier.classify('Tell me more');
      expect(result.type, IntentType.journal);
      expect(result.confidence, 0.1);
    });

    test('temporal in narrative: "I talked to her last week" → journal', () {
      final result = classifier.classify(
        'I talked to her last week about the project',
      );
      expect(result.type, IntentType.journal);
      expect(result.confidence, greaterThanOrEqualTo(0.9));
    });

    test('"I remember feeling happy today" → journal', () {
      final result = classifier.classify('I remember feeling happy today');
      expect(result.type, IntentType.journal);
    });

    test('"I recall being nervous" → journal', () {
      final result = classifier.classify('I recall being nervous');
      expect(result.type, IntentType.journal);
    });

    test('simple narrative → journal', () {
      final result = classifier.classify(
        'Today was a good day at work with the team',
      );
      expect(result.type, IntentType.journal);
      expect(result.confidence, 1.0);
    });

    test('mixed case narrative → journal', () {
      final result = classifier.classify(
        'I Had A Really Great Conversation With My Boss Today',
      );
      expect(result.type, IntentType.journal);
    });

    test('"Find entries about anxiety" → journal (single signal 0.35)', () {
      final result = classifier.classify('Find entries about anxiety');
      expect(result.type, IntentType.journal);
    });

    test('past tense only 0.4 → journal (below threshold)', () {
      final result = classifier.classify(
        'What did I say when I talked to Mike?',
      );
      expect(result.type, IntentType.journal);
    });

    test('single meta-question 0.45 → journal (below threshold)', () {
      final result = classifier.classify(
        'How often do I mention feeling stressed about work?',
      );
      expect(result.type, IntentType.journal);
    });

    test('"Do I ever talk about exercise?" → journal (single signal)', () {
      final result = classifier.classify(
        'Do I ever talk about exercise in my journal?',
      );
      expect(result.type, IntentType.journal);
    });

    // --- Query cases (must remain query with pinned minimum confidence) ---

    test('"What did I do last Thursday?" → query, confidence >= 0.7', () {
      final result = classifier.classify('What did I do last Thursday?');
      expect(result.type, IntentType.query);
      expect(result.confidence, greaterThanOrEqualTo(0.7));
    });

    test('"What did I write about work last week?" → query, >= 0.5', () {
      final result = classifier.classify(
        'What did I write about work last week?',
      );
      expect(result.type, IntentType.query);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"Do you remember when I talked about work?" → query', () {
      final result = classifier.classify(
        'Do you remember when I talked about work?',
      );
      expect(result.type, IntentType.query);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"What did I write about last week?" → query', () {
      final result = classifier.classify('What did I write about last week?');
      expect(result.type, IntentType.query);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"WHAT DID I DO YESTERDAY?" → query (mixed case)', () {
      final result = classifier.classify('WHAT DID I DO YESTERDAY?');
      expect(result.type, IntentType.query);
      expect(result.confidence, greaterThanOrEqualTo(0.7));
    });

    test('"How many times have I mentioned anxiety?" → query, >= 0.8', () {
      final result = classifier.classify(
        'How many times have I mentioned anxiety?',
      );
      expect(result.type, IntentType.query);
      expect(result.confidence, greaterThanOrEqualTo(0.8));
    });

    test('"How often did I mention feeling stressed?" → query, >= 0.5', () {
      final result = classifier.classify(
        'How often did I mention feeling stressed about work?',
      );
      expect(result.type, IntentType.query);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    // --- Search terms ---

    test('query extracts search terms containing "work"', () {
      final result = classifier.classify(
        'What did I write about work last week?',
      );
      expect(result.type, IntentType.query);
      expect(result.searchTerms, isNotEmpty);
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

  // =========================================================================
  // Calendar intent tests
  // =========================================================================
  group('calendar intent detection', () {
    test('"Schedule a meeting for tomorrow" → calendarEvent', () {
      final result = classifier.classify('Schedule a meeting for tomorrow');
      expect(result.type, IntentType.calendarEvent);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"Book dinner on Friday" → calendarEvent', () {
      final result = classifier.classify('Book dinner on Friday');
      expect(result.type, IntentType.calendarEvent);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"Add that to my calendar" → calendarEvent', () {
      final result = classifier.classify(
        'Add that to my calendar for next week',
      );
      expect(result.type, IntentType.calendarEvent);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"Put the team meeting on my calendar" → calendarEvent', () {
      final result = classifier.classify('Put the team meeting on my calendar');
      expect(result.type, IntentType.calendarEvent);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"I want to schedule a dentist appointment" → calendarEvent', () {
      final result = classifier.classify(
        'I want to schedule a dentist appointment next week',
      );
      expect(result.type, IntentType.calendarEvent);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"Can you book a call for tomorrow?" → calendarEvent', () {
      final result = classifier.classify('Can you book a call for tomorrow?');
      expect(result.type, IntentType.calendarEvent);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"Add a meeting for next Monday" → calendarEvent', () {
      final result = classifier.classify('Add a meeting for next Monday');
      expect(result.type, IntentType.calendarEvent);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('event noun + future temporal → calendarEvent', () {
      final result = classifier.classify('I have a meeting tomorrow at 3pm');
      expect(result.type, IntentType.calendarEvent);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('event noun + future day → calendarEvent', () {
      final result = classifier.classify(
        'We should have dinner on Friday evening',
      );
      expect(result.type, IntentType.calendarEvent);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"Set up a call with the team" → calendarEvent', () {
      final result = classifier.classify('Set up a call with the team');
      expect(result.type, IntentType.calendarEvent);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('short "Schedule dinner" → calendarEvent (strong signal)', () {
      final result = classifier.classify('Schedule dinner');
      expect(result.type, IntentType.calendarEvent);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });
  });

  // =========================================================================
  // Reminder intent tests
  // =========================================================================
  group('reminder intent detection', () {
    test('"Remind me to call Mom on Friday" → reminder', () {
      final result = classifier.classify('Remind me to call Mom on Friday');
      expect(result.type, IntentType.reminder);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"Don\'t let me forget to buy groceries" → reminder', () {
      final result = classifier.classify(
        "Don't let me forget to buy groceries tomorrow",
      );
      expect(result.type, IntentType.reminder);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"Remember to submit the report" → reminder', () {
      final result = classifier.classify(
        'Remember to submit the report by Friday',
      );
      expect(result.type, IntentType.reminder);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"Make sure I take my medication" → reminder', () {
      final result = classifier.classify(
        'Make sure I take my medication tomorrow',
      );
      expect(result.type, IntentType.reminder);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('short "Remind me" → reminder (strong signal)', () {
      final result = classifier.classify('Remind me');
      expect(result.type, IntentType.reminder);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"Don\'t forget the dentist" → reminder', () {
      final result = classifier.classify(
        "Don't forget the dentist appointment next week",
      );
      expect(result.type, IntentType.reminder);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });
  });

  // =========================================================================
  // Temporal collision tests (blocking review finding B4)
  // =========================================================================
  group('temporal collision disambiguation', () {
    test('"What did I schedule for last Monday?" → recall (past-tense)', () {
      final result = classifier.classify(
        'What did I schedule for last Monday?',
      );
      expect(result.type, IntentType.query);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"Add a meeting for next Monday" → calendarEvent (future)', () {
      final result = classifier.classify('Add a meeting for next Monday');
      expect(result.type, IntentType.calendarEvent);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"Remind me about what I wrote last week" → multi-intent', () {
      final results = classifier.classifyMulti(
        'Remind me about what I wrote last week',
      );
      // Primary intent should be reminder (explicit "remind me").
      expect(results.first.type, IntentType.reminder);
      expect(results.first.confidence, greaterThanOrEqualTo(0.5));
      // Secondary intent should include query (past-tense "what I wrote").
      final hasQuerySecondary = results.any((r) => r.type == IntentType.query);
      expect(hasQuerySecondary, isTrue);
    });

    test('"What meetings did I add last Tuesday?" → recall', () {
      final result = classifier.classify(
        'What meetings did I add last Tuesday?',
      );
      expect(result.type, IntentType.query);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('future temporal boosts calendar, not recall', () {
      final result = classifier.classify('Schedule lunch for tomorrow');
      expect(result.type, IntentType.calendarEvent);
      // Should not be query.
      final results = classifier.classifyMulti('Schedule lunch for tomorrow');
      final queryResults = results.where((r) => r.type == IntentType.query);
      expect(queryResults, isEmpty);
    });

    test('past temporal boosts recall, not calendar', () {
      final result = classifier.classify('What did I do last Thursday?');
      expect(result.type, IntentType.query);
      // Should not be calendarEvent.
      final results = classifier.classifyMulti('What did I do last Thursday?');
      final calendarResults = results.where(
        (r) => r.type == IntentType.calendarEvent,
      );
      expect(calendarResults, isEmpty);
    });
  });

  // =========================================================================
  // Multi-intent ranking tests
  // =========================================================================
  group('classifyMulti ranked results', () {
    test('returns list with primary intent first', () {
      final results = classifier.classifyMulti('What did I do last Thursday?');
      expect(results, isNotEmpty);
      expect(results.first.type, IntentType.query);
    });

    test('journal messages return journal as primary', () {
      final results = classifier.classifyMulti('Today was a good day at work');
      expect(results.first.type, IntentType.journal);
    });

    test('calendar intent returns calendarEvent as primary', () {
      final results = classifier.classifyMulti(
        'Schedule a team meeting for tomorrow at 2pm',
      );
      expect(results.first.type, IntentType.calendarEvent);
    });

    test('reminder intent returns reminder as primary', () {
      final results = classifier.classifyMulti(
        'Remind me to call the doctor tomorrow',
      );
      expect(results.first.type, IntentType.reminder);
    });

    test('results are sorted by confidence descending', () {
      final results = classifier.classifyMulti(
        'Remind me about what I wrote last week',
      );
      for (var i = 0; i < results.length - 1; i++) {
        expect(
          results[i].confidence,
          greaterThanOrEqualTo(results[i + 1].confidence),
        );
      }
    });

    test('empty input returns single journal result', () {
      final results = classifier.classifyMulti('');
      expect(results.length, 1);
      expect(results.first.type, IntentType.journal);
      expect(results.first.confidence, 0.0);
    });
  });

  // =========================================================================
  // Calendar vs recall disambiguation edge cases
  // =========================================================================
  group('calendar vs recall edge cases', () {
    test('"I had a meeting last week" → journal (narrative, no question)', () {
      final result = classifier.classify('I had a meeting last week');
      expect(result.type, IntentType.journal);
    });

    test('"Remember to schedule the meeting" → reminder (not recall)', () {
      final result = classifier.classify('Remember to schedule the meeting');
      expect(result.type, IntentType.reminder);
    });

    test('"I remember scheduling a meeting" → journal (narrative recall)', () {
      // "I remember" + gerund = journal context
      final result = classifier.classify(
        'I remember scheduling a meeting with the team',
      );
      expect(result.type, IntentType.journal);
    });

    test('narrative with future temporal stays journal', () {
      // "I'm going to the gym tomorrow" — no calendar intent.
      final result = classifier.classify(
        "I'm excited about going to the gym tomorrow",
      );
      expect(result.type, IntentType.journal);
    });
  });
}
