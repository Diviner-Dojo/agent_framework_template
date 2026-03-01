// ===========================================================================
// file: test/services/intent_classifier_task_test.dart
// purpose: Regression tests for task and dayQuery intent classification.
//
// These tests verify:
//   1. Task intent patterns detect correctly
//   2. Day query patterns detect correctly
//   3. Existing journal/query/calendarEvent/reminder patterns NOT regressed
//   4. Disambiguation edge cases (reminder > task, calendar > task)
//   5. Confidence tier boundaries
//   6. Short-message strong signal detection
//
// See: Phase 13 plan (Google Tasks + Personal Assistant)
// ===========================================================================

import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/services/intent_classifier.dart';

void main() {
  late IntentClassifier classifier;

  setUp(() {
    classifier = IntentClassifier();
  });

  // =========================================================================
  // Task intent detection
  // =========================================================================

  group('Task intent detection', () {
    test('"Add a task to buy groceries" → task', () {
      final result = classifier.classify('Add a task to buy groceries');
      expect(result.type, IntentType.task);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"Create a task for the report" → task', () {
      final result = classifier.classify('Create a task for the report');
      expect(result.type, IntentType.task);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"Add buy milk to my task list" → task', () {
      final result = classifier.classify('Add buy milk to my task list');
      expect(result.type, IntentType.task);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"New to-do: finish presentation" → task', () {
      final result = classifier.classify('New to-do: finish presentation');
      expect(result.type, IntentType.task);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"Create a to-do item for laundry" → task', () {
      final result = classifier.classify('Create a to-do item for laundry');
      expect(result.type, IntentType.task);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"Add clean the garage to my to-do list" → task', () {
      final result = classifier.classify(
        'Add clean the garage to my to-do list',
      );
      expect(result.type, IntentType.task);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"Make a task to call the dentist" → task', () {
      final result = classifier.classify('Make a task to call the dentist');
      expect(result.type, IntentType.task);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"Put pick up dry cleaning on my list" → task (weak signal)', () {
      final result = classifier.classify('Put pick up dry cleaning on my list');
      expect(result.type, IntentType.task);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"Add eggs to my list" → task (weak signal via list reference)', () {
      final result = classifier.classify('Add eggs to my list');
      expect(result.type, IntentType.task);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    // Regression: indirect object pronoun between verb and task keyword.
    // "add me a to-do" has "me" between "add" and "a to-do".
    test(
      'indirect object: "add me a to-do item to call Kaiser" → task (regression)',
      () {
        final result = classifier.classify(
          'I need you to add me a to-do item to call Kaiser about makin an appointment with my psychiatrist',
        );
        expect(result.type, IntentType.task);
        expect(result.confidence, greaterThanOrEqualTo(0.5));
      },
    );

    test('indirect object: "add me a task" → task (regression)', () {
      final result = classifier.classify('Add me a task to buy groceries');
      expect(result.type, IntentType.task);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });
  });

  // =========================================================================
  // Task intent: short messages with strong signals
  // =========================================================================

  group('Task intent: short messages', () {
    test('"Add a task" → task (short with strong signal)', () {
      final result = classifier.classify('Add a task');
      expect(result.type, IntentType.task);
    });

    test('"Create task" → task (short with strong signal)', () {
      final result = classifier.classify('Create task');
      expect(result.type, IntentType.task);
    });

    test('"New task" → task', () {
      final result = classifier.classify('New task');
      expect(result.type, IntentType.task);
    });
  });

  // =========================================================================
  // Task intent: things that should NOT be task
  // =========================================================================

  group('Task intent: negative cases', () {
    test('"Buy groceries" → journal (no task keyword)', () {
      final result = classifier.classify('Buy groceries');
      expect(result.type, IntentType.journal);
    });

    test('"I need to fix the sink" → journal (no task keyword)', () {
      final result = classifier.classify('I need to fix the sink');
      expect(result.type, IntentType.journal);
    });

    test('"Clean the house today" → journal (action verb without task)', () {
      final result = classifier.classify('Clean the house today');
      expect(result.type, IntentType.journal);
    });

    test('"The task was challenging" → journal (narrative about tasks)', () {
      final result = classifier.classify(
        'The task was challenging and I struggled with it all day',
      );
      expect(result.type, IntentType.journal);
    });
  });

  // =========================================================================
  // Day query intent detection
  // =========================================================================

  group('Day query intent detection', () {
    test('"What does my day look like?" → dayQuery', () {
      final result = classifier.classify('What does my day look like?');
      expect(result.type, IntentType.dayQuery);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"What\'s happening today?" → dayQuery', () {
      final result = classifier.classify("What's happening today?");
      expect(result.type, IntentType.dayQuery);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"What\'s going on tomorrow?" → dayQuery', () {
      final result = classifier.classify("What's going on tomorrow?");
      expect(result.type, IntentType.dayQuery);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"Tell me about my schedule" → dayQuery', () {
      final result = classifier.classify('Tell me about my schedule');
      expect(result.type, IntentType.dayQuery);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"Show me my calendar" → dayQuery', () {
      final result = classifier.classify('Show me my calendar');
      expect(result.type, IntentType.dayQuery);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"Give me my agenda" → dayQuery', () {
      final result = classifier.classify('Give me my agenda');
      expect(result.type, IntentType.dayQuery);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"What\'s on my schedule?" → dayQuery', () {
      final result = classifier.classify("What's on my schedule?");
      expect(result.type, IntentType.dayQuery);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"How\'s my day shaping up?" → dayQuery', () {
      final result = classifier.classify("How's my day shaping up?");
      expect(result.type, IntentType.dayQuery);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"How does my schedule look?" → dayQuery', () {
      final result = classifier.classify('How does my schedule look?');
      expect(result.type, IntentType.dayQuery);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });
  });

  // =========================================================================
  // Day query: task-specific queries
  // =========================================================================

  group('Day query: task-specific', () {
    test('"Any tasks due today?" → dayQuery', () {
      final result = classifier.classify('Any tasks due today?');
      expect(result.type, IntentType.dayQuery);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"What tasks are due tomorrow?" → dayQuery', () {
      final result = classifier.classify('What tasks are due tomorrow?');
      expect(result.type, IntentType.dayQuery);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"Any tasks for today?" → dayQuery', () {
      final result = classifier.classify('Any tasks for today?');
      expect(result.type, IntentType.dayQuery);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('"What tasks are pending?" → dayQuery', () {
      final result = classifier.classify('What tasks are pending?');
      expect(result.type, IntentType.dayQuery);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });
  });

  // =========================================================================
  // Day query: short messages with strong signals
  // =========================================================================

  group('Day query: short messages', () {
    test('"What\'s my day?" → dayQuery (short with strong signal)', () {
      final result = classifier.classify("What's my day?");
      expect(result.type, IntentType.dayQuery);
    });

    test('"What\'s on today?" → dayQuery (short with strong signal)', () {
      final result = classifier.classify("What's on today?");
      expect(result.type, IntentType.dayQuery);
    });
  });

  // =========================================================================
  // Day query: negative cases
  // =========================================================================

  group('Day query: negative cases', () {
    test('"What did I do yesterday?" → NOT dayQuery (past tense → recall)', () {
      final result = classifier.classify('What did I do yesterday?');
      expect(result.type, isNot(IntentType.dayQuery));
    });

    test('"How was my day yesterday?" → NOT dayQuery (past tense)', () {
      final result = classifier.classify(
        'How was my day yesterday? Did I do anything productive?',
      );
      expect(result.type, isNot(IntentType.dayQuery));
    });
  });

  // =========================================================================
  // Disambiguation: reminder > task
  // =========================================================================

  group('Disambiguation: reminder wins over task', () {
    test('"Remind me to add a task for groceries" → reminder', () {
      final result = classifier.classify(
        'Remind me to add a task for groceries',
      );
      expect(result.type, IntentType.reminder);
    });

    test('"Don\'t forget to create a task for the report" → reminder', () {
      final result = classifier.classify(
        "Don't forget to create a task for the report",
      );
      expect(result.type, IntentType.reminder);
    });

    test('"Remember to add that to my task list" → reminder', () {
      final result = classifier.classify(
        'Remember to add that to my task list',
      );
      expect(result.type, IntentType.reminder);
    });
  });

  // =========================================================================
  // Disambiguation: calendar > task (without explicit task keyword)
  // =========================================================================

  group('Disambiguation: calendar vs task', () {
    test('"Schedule a meeting tomorrow" → calendarEvent (not task)', () {
      final result = classifier.classify('Schedule a meeting tomorrow');
      expect(result.type, IntentType.calendarEvent);
    });

    test('"Book dinner for Friday" → calendarEvent (not task)', () {
      final result = classifier.classify('Book dinner for Friday');
      expect(result.type, IntentType.calendarEvent);
    });

    test(
      '"Add a task for the meeting prep" → task (explicit task keyword)',
      () {
        final result = classifier.classify('Add a task for the meeting prep');
        expect(result.type, IntentType.task);
        expect(result.confidence, greaterThanOrEqualTo(0.5));
      },
    );
  });

  // =========================================================================
  // Regression: existing journal patterns NOT affected
  // =========================================================================

  group('Regression: journal patterns preserved', () {
    test('empty string → journal', () {
      final result = classifier.classify('');
      expect(result.type, IntentType.journal);
    });

    test('simple narrative → journal', () {
      final result = classifier.classify(
        'Today I had a really productive meeting with the design team',
      );
      expect(result.type, IntentType.journal);
    });

    test('"I remember feeling happy" → journal', () {
      final result = classifier.classify('I remember feeling happy today');
      expect(result.type, IntentType.journal);
    });

    test('short conversational: "Really?" → journal', () {
      final result = classifier.classify('Really?');
      expect(result.type, IntentType.journal);
    });

    test('short conversational: "Why not?" → journal', () {
      final result = classifier.classify('Why not?');
      expect(result.type, IntentType.journal);
    });

    test('"Tell me more" → journal', () {
      final result = classifier.classify('Tell me more');
      expect(result.type, IntentType.journal);
    });

    test('"I talked to her last week" → journal', () {
      final result = classifier.classify(
        'I talked to her last week about the project',
      );
      expect(result.type, IntentType.journal);
    });
  });

  // =========================================================================
  // Regression: existing query/recall patterns NOT affected
  // =========================================================================

  group('Regression: query patterns preserved', () {
    test('"What did I write about anxiety?" has query signal', () {
      // Single signal (questionPast) scores 0.4 — below 0.5 threshold,
      // so primary is journal. Query appears as secondary in classifyMulti.
      final results = classifier.classifyMulti(
        'What did I write about anxiety?',
      );
      expect(results.any((r) => r.type == IntentType.query), isTrue);
    });

    test('"When was the last time I exercised?" has query signal', () {
      final results = classifier.classifyMulti(
        'When was the last time I exercised?',
      );
      expect(results.any((r) => r.type == IntentType.query), isTrue);
    });

    test('"How often do I mention stress?" has query signal', () {
      final results = classifier.classifyMulti(
        'How often do I mention stress?',
      );
      expect(results.any((r) => r.type == IntentType.query), isTrue);
    });

    test('combined query signals reach threshold', () {
      // Two signals: questionPast (0.4) + temporal (0.3) = 0.7 → query.
      final result = classifier.classify('What did I write about last week?');
      expect(result.type, IntentType.query);
    });
  });

  // =========================================================================
  // Regression: existing calendarEvent patterns NOT affected
  // =========================================================================

  group('Regression: calendarEvent patterns preserved', () {
    test('"Schedule a meeting tomorrow at 3pm" → calendarEvent', () {
      final result = classifier.classify('Schedule a meeting tomorrow at 3pm');
      expect(result.type, IntentType.calendarEvent);
    });

    test('"Add lunch to my calendar on Friday" → calendarEvent', () {
      final result = classifier.classify('Add lunch to my calendar on Friday');
      expect(result.type, IntentType.calendarEvent);
    });

    test('"Book a dinner reservation for Saturday" → calendarEvent', () {
      final result = classifier.classify(
        'Book a dinner reservation for Saturday',
      );
      expect(result.type, IntentType.calendarEvent);
    });
  });

  // =========================================================================
  // Regression: existing reminder patterns NOT affected
  // =========================================================================

  group('Regression: reminder patterns preserved', () {
    test('"Remind me to call mom tomorrow" → reminder', () {
      final result = classifier.classify('Remind me to call mom tomorrow');
      expect(result.type, IntentType.reminder);
    });

    test('"Don\'t forget to buy milk" → reminder', () {
      final result = classifier.classify("Don't forget to buy milk");
      expect(result.type, IntentType.reminder);
    });

    test('"Remember to submit the form" → reminder', () {
      final result = classifier.classify('Remember to submit the form');
      expect(result.type, IntentType.reminder);
    });
  });

  // =========================================================================
  // Confidence tier boundaries
  // =========================================================================

  group('Confidence tier boundaries', () {
    test('task with explicit keyword ≥ 0.5', () {
      final result = classifier.classify('Add a task for groceries');
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('day query with direct pattern ≥ 0.5', () {
      final result = classifier.classify('What does my day look like?');
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });

    test('journal for ambiguous messages near 1.0', () {
      final result = classifier.classify(
        'I had a great day and accomplished a lot of things',
      );
      expect(result.type, IntentType.journal);
      expect(result.confidence, greaterThanOrEqualTo(0.5));
    });
  });

  // =========================================================================
  // Multi-intent ranking (classifyMulti)
  // =========================================================================

  group('Multi-intent ranking', () {
    test('task intent appears in ranked results', () {
      final results = classifier.classifyMulti(
        'Add a task to finish the report',
      );
      expect(results.any((r) => r.type == IntentType.task), isTrue);
    });

    test('dayQuery intent appears in ranked results', () {
      final results = classifier.classifyMulti(
        'What does my day look like tomorrow?',
      );
      expect(results.any((r) => r.type == IntentType.dayQuery), isTrue);
    });

    test('task is first when task keyword present', () {
      final results = classifier.classifyMulti(
        'Create a task to review the documents',
      );
      expect(results.first.type, IntentType.task);
    });

    test('dayQuery is first for schedule questions', () {
      final results = classifier.classifyMulti("What's happening today?");
      expect(results.first.type, IntentType.dayQuery);
    });
  });

  // =========================================================================
  // Edge cases
  // =========================================================================

  group('Edge cases', () {
    test('mixed case task keywords still detected', () {
      final result = classifier.classify('ADD A TASK for the project');
      expect(result.type, IntentType.task);
    });

    test('mixed case day query still detected', () {
      final result = classifier.classify("WHAT'S ON MY SCHEDULE?");
      expect(result.type, IntentType.dayQuery);
    });

    test('"Add to my calendar" → calendarEvent (not task list)', () {
      final result = classifier.classify('Add the meeting to my calendar');
      expect(result.type, IntentType.calendarEvent);
    });

    test('"Add to my task list" → task (not calendar)', () {
      final result = classifier.classify('Add the meeting to my task list');
      expect(result.type, IntentType.task);
    });

    test('task with due date preserves task type', () {
      final result = classifier.classify(
        'Add a task for the report due next Friday',
      );
      expect(result.type, IntentType.task);
    });

    test('day query with "today" temporal → dayQuery not recall', () {
      final result = classifier.classify("What's on my calendar for today?");
      expect(result.type, IntentType.dayQuery);
    });
  });
}
