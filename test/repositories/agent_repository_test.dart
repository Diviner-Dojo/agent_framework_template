import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/repositories/agent_repository.dart';

void main() {
  late AgentRepository agent;

  setUp(() {
    agent = AgentRepository();
  });

  group('getGreeting', () {
    test('returns morning greeting between 5 AM and 11:59 AM', () {
      final morning = DateTime(2026, 2, 19, 8, 0); // 8 AM
      expect(
        agent.getGreeting(now: morning),
        'Good morning! Any plans or thoughts for today?',
      );
    });

    test('returns afternoon greeting between 12 PM and 4:59 PM', () {
      final afternoon = DateTime(2026, 2, 19, 14, 0); // 2 PM
      expect(agent.getGreeting(now: afternoon), "How's your afternoon going?");
    });

    test('returns evening greeting between 5 PM and 9:59 PM', () {
      final evening = DateTime(2026, 2, 19, 19, 0); // 7 PM
      expect(agent.getGreeting(now: evening), 'How was your day?');
    });

    test('returns late night greeting between 10 PM and 4:59 AM', () {
      final lateNight = DateTime(2026, 2, 19, 23, 0); // 11 PM
      expect(
        agent.getGreeting(now: lateNight),
        "Still up? What's on your mind?",
      );
    });

    test('returns gap greeting when last session was 2+ days ago', () {
      final now = DateTime(2026, 2, 19, 10, 0);
      final twoDaysAgo = DateTime(2026, 2, 17, 10, 0);
      expect(
        agent.getGreeting(lastSessionDate: twoDaysAgo, now: now),
        "It's been a few days — want to catch up?",
      );
    });

    test('returns gap greeting when last session was 3+ days ago', () {
      final now = DateTime(2026, 2, 19, 10, 0);
      final threeDaysAgo = DateTime(2026, 2, 16, 10, 0);
      expect(
        agent.getGreeting(lastSessionDate: threeDaysAgo, now: now),
        "It's been a few days — want to catch up?",
      );
    });

    test('returns time-of-day greeting when last session was 1 day ago', () {
      final now = DateTime(2026, 2, 19, 10, 0);
      final yesterday = DateTime(2026, 2, 18, 10, 0);
      expect(
        agent.getGreeting(lastSessionDate: yesterday, now: now),
        'Good morning! Any plans or thoughts for today?',
      );
    });

    test('returns time-of-day greeting when lastSessionDate is null', () {
      final now = DateTime(2026, 2, 19, 10, 0);
      expect(
        agent.getGreeting(lastSessionDate: null, now: now),
        'Good morning! Any plans or thoughts for today?',
      );
    });
  });

  group('getFollowUp', () {
    test('returns emotional follow-up for emotional keywords', () {
      final result = agent.getFollowUp(
        latestUserMessage: 'I feel so stressed today',
        conversationHistory: [],
        followUpCount: 0,
      );
      expect(result, isNotNull);
      expect(result, isNotEmpty);
    });

    test('returns social follow-up for social keywords', () {
      final result = agent.getFollowUp(
        latestUserMessage: 'Had a great time with my friend',
        conversationHistory: [],
        followUpCount: 0,
      );
      expect(result, isNotNull);
      expect(result, isNotEmpty);
    });

    test('returns work follow-up for work keywords', () {
      final result = agent.getFollowUp(
        latestUserMessage: 'Big meeting at the office today',
        conversationHistory: [],
        followUpCount: 0,
      );
      expect(result, isNotNull);
      expect(result, isNotEmpty);
    });

    test('returns null after max follow-ups', () {
      final result = agent.getFollowUp(
        latestUserMessage: 'anything',
        conversationHistory: [],
        followUpCount: 4,
      );
      expect(result, isNull);
    });

    test('returns closing message at follow-up count 3', () {
      final result = agent.getFollowUp(
        latestUserMessage: 'anything',
        conversationHistory: [],
        followUpCount: 3,
      );
      expect(result, contains('anything else'));
    });

    test('does not repeat questions in the same session', () {
      final questions = <String>[];
      for (var i = 0; i < 4; i++) {
        final result = agent.getFollowUp(
          latestUserMessage: 'I feel stressed',
          conversationHistory: questions,
          followUpCount: i,
        );
        if (result != null) {
          // Verify this question hasn't been asked before.
          expect(questions, isNot(contains(result)));
          questions.add(result);
        }
      }
      // Should have gotten at least 3 distinct questions.
      expect(questions.length, greaterThanOrEqualTo(3));
    });
  });

  group('shouldEndSession', () {
    test('returns true for "no"', () {
      expect(
        agent.shouldEndSession(followUpCount: 1, latestUserMessage: 'no'),
        isTrue,
      );
    });

    test('returns true for "nope"', () {
      expect(
        agent.shouldEndSession(followUpCount: 1, latestUserMessage: 'nope'),
        isTrue,
      );
    });

    test("returns true for \"I'm done\"", () {
      expect(
        agent.shouldEndSession(followUpCount: 1, latestUserMessage: "I'm done"),
        isTrue,
      );
    });

    test("returns true for \"that's all\"", () {
      expect(
        agent.shouldEndSession(
          followUpCount: 1,
          latestUserMessage: "that's all",
        ),
        isTrue,
      );
    });

    test('returns true when followUpCount exceeds max', () {
      expect(
        agent.shouldEndSession(followUpCount: 4, latestUserMessage: 'anything'),
        isTrue,
      );
    });

    test('returns false for normal messages at low follow-up count', () {
      expect(
        agent.shouldEndSession(
          followUpCount: 1,
          latestUserMessage: "I'm done with the project for now",
        ),
        isFalse,
      );
    });

    test(
      'returns false for messages that contain but are not done signals',
      () {
        // "I'm done with the project" contains "done" but the full message
        // doesn't match any done signal exactly. Design choice: we match
        // the whole trimmed message to avoid false positives.
        expect(
          agent.shouldEndSession(
            followUpCount: 0,
            latestUserMessage: 'not really sure about that',
          ),
          isFalse,
        );
      },
    );
  });

  group('generateLocalSummary', () {
    test('returns empty string for empty list', () {
      expect(agent.generateLocalSummary([]), '');
    });

    test('extracts first sentence from single message', () {
      final result = agent.generateLocalSummary([
        'I had a great day today. The weather was perfect.',
      ]);
      expect(result, 'I had a great day today.');
    });

    test('handles single-word message', () {
      final result = agent.generateLocalSummary(['Hello']);
      expect(result, 'Hello');
    });

    test('combines first sentences from multiple messages', () {
      final result = agent.generateLocalSummary([
        'Feeling good today. Sun is out.',
        'Work was productive! Got a lot done.',
      ]);
      expect(result, contains('Feeling good today.'));
      expect(result, contains('Work was productive!'));
    });
  });
}
