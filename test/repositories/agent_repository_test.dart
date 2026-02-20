import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/repositories/agent_repository.dart';
import 'package:agentic_journal/models/agent_response.dart';

void main() {
  late AgentRepository agent;

  setUp(() {
    // No Claude service or connectivity — tests exercise Layer A only.
    agent = AgentRepository();
  });

  group('getGreeting (Layer A)', () {
    test('returns morning greeting between 5 AM and 11:59 AM', () async {
      final morning = DateTime(2026, 2, 19, 8, 0);
      final response = await agent.getGreeting(now: morning);
      expect(
        response.content,
        'Good morning! Any plans or thoughts for today?',
      );
      expect(response.layer, AgentLayer.ruleBasedLocal);
    });

    test('returns afternoon greeting between 12 PM and 4:59 PM', () async {
      final afternoon = DateTime(2026, 2, 19, 14, 0);
      final response = await agent.getGreeting(now: afternoon);
      expect(response.content, "How's your afternoon going?");
      expect(response.layer, AgentLayer.ruleBasedLocal);
    });

    test('returns evening greeting between 5 PM and 9:59 PM', () async {
      final evening = DateTime(2026, 2, 19, 19, 0);
      final response = await agent.getGreeting(now: evening);
      expect(response.content, 'How was your day?');
      expect(response.layer, AgentLayer.ruleBasedLocal);
    });

    test('returns late night greeting between 10 PM and 4:59 AM', () async {
      final lateNight = DateTime(2026, 2, 19, 23, 0);
      final response = await agent.getGreeting(now: lateNight);
      expect(response.content, "Still up? What's on your mind?");
      expect(response.layer, AgentLayer.ruleBasedLocal);
    });

    test('returns gap greeting when last session was 2+ days ago', () async {
      final now = DateTime(2026, 2, 19, 10, 0);
      final twoDaysAgo = DateTime(2026, 2, 17, 10, 0);
      final response = await agent.getGreeting(
        lastSessionDate: twoDaysAgo,
        now: now,
      );
      expect(response.content, "It's been a few days — want to catch up?");
    });

    test('returns gap greeting when last session was 3+ days ago', () async {
      final now = DateTime(2026, 2, 19, 10, 0);
      final threeDaysAgo = DateTime(2026, 2, 16, 10, 0);
      final response = await agent.getGreeting(
        lastSessionDate: threeDaysAgo,
        now: now,
      );
      expect(response.content, "It's been a few days — want to catch up?");
    });

    test(
      'returns time-of-day greeting when last session was 1 day ago',
      () async {
        final now = DateTime(2026, 2, 19, 10, 0);
        final yesterday = DateTime(2026, 2, 18, 10, 0);
        final response = await agent.getGreeting(
          lastSessionDate: yesterday,
          now: now,
        );
        expect(
          response.content,
          'Good morning! Any plans or thoughts for today?',
        );
      },
    );

    test('returns time-of-day greeting when lastSessionDate is null', () async {
      final now = DateTime(2026, 2, 19, 10, 0);
      final response = await agent.getGreeting(lastSessionDate: null, now: now);
      expect(
        response.content,
        'Good morning! Any plans or thoughts for today?',
      );
    });
  });

  group('getFollowUp (Layer A)', () {
    test('returns emotional follow-up for emotional keywords', () async {
      final result = await agent.getFollowUp(
        latestUserMessage: 'I feel so stressed today',
        conversationHistory: [],
        followUpCount: 0,
      );
      expect(result, isNotNull);
      expect(result!.content, isNotEmpty);
      expect(result.layer, AgentLayer.ruleBasedLocal);
    });

    test('returns social follow-up for social keywords', () async {
      final result = await agent.getFollowUp(
        latestUserMessage: 'Had a great time with my friend',
        conversationHistory: [],
        followUpCount: 0,
      );
      expect(result, isNotNull);
      expect(result!.content, isNotEmpty);
    });

    test('returns work follow-up for work keywords', () async {
      final result = await agent.getFollowUp(
        latestUserMessage: 'Big meeting at the office today',
        conversationHistory: [],
        followUpCount: 0,
      );
      expect(result, isNotNull);
      expect(result!.content, isNotEmpty);
    });

    test('returns null after max follow-ups', () async {
      final result = await agent.getFollowUp(
        latestUserMessage: 'anything',
        conversationHistory: [],
        followUpCount: 4,
      );
      expect(result, isNull);
    });

    test('returns closing message at follow-up count 3', () async {
      final result = await agent.getFollowUp(
        latestUserMessage: 'anything',
        conversationHistory: [],
        followUpCount: 3,
      );
      expect(result, isNotNull);
      expect(result!.content, contains('anything else'));
    });

    test('does not repeat questions in the same session', () async {
      final questions = <String>[];
      for (var i = 0; i < 4; i++) {
        final result = await agent.getFollowUp(
          latestUserMessage: 'I feel stressed',
          conversationHistory: questions,
          followUpCount: i,
        );
        if (result != null) {
          expect(questions, isNot(contains(result.content)));
          questions.add(result.content);
        }
      }
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
        expect(
          agent.shouldEndSession(
            followUpCount: 0,
            latestUserMessage: 'not really sure about that',
          ),
          isFalse,
        );
      },
    );

    test('returns true for "No." with trailing period', () {
      expect(
        agent.shouldEndSession(followUpCount: 1, latestUserMessage: 'No.'),
        isTrue,
      );
    });

    test('returns true for "Nope!" with trailing exclamation', () {
      expect(
        agent.shouldEndSession(followUpCount: 1, latestUserMessage: 'Nope!'),
        isTrue,
      );
    });

    test('returns true for "done" signal', () {
      expect(
        agent.shouldEndSession(followUpCount: 1, latestUserMessage: 'done'),
        isTrue,
      );
    });

    test('returns true for "all good" signal', () {
      expect(
        agent.shouldEndSession(followUpCount: 1, latestUserMessage: 'all good'),
        isTrue,
      );
    });

    test("returns true for \"that's everything\" signal", () {
      expect(
        agent.shouldEndSession(
          followUpCount: 1,
          latestUserMessage: "that's everything",
        ),
        isTrue,
      );
    });

    test('returns true for "bye!" with trailing punctuation', () {
      expect(
        agent.shouldEndSession(followUpCount: 1, latestUserMessage: 'bye!'),
        isTrue,
      );
    });

    test('strips multiple trailing punctuation marks', () {
      expect(
        agent.shouldEndSession(followUpCount: 1, latestUserMessage: 'nope...'),
        isTrue,
      );
    });

    test('does not false-positive on "no regrets"', () {
      expect(
        agent.shouldEndSession(
          followUpCount: 0,
          latestUserMessage: 'no regrets',
        ),
        isFalse,
      );
    });
  });

  group('generateSummary (Layer A)', () {
    test('returns empty string for empty list', () async {
      final response = await agent.generateSummary(userMessages: []);
      expect(response.content, '');
      expect(response.layer, AgentLayer.ruleBasedLocal);
    });

    test('extracts first sentence from single message', () async {
      final response = await agent.generateSummary(
        userMessages: ['I had a great day today. The weather was perfect.'],
      );
      expect(response.content, 'I had a great day today.');
    });

    test('handles single-word message', () async {
      final response = await agent.generateSummary(userMessages: ['Hello']);
      expect(response.content, 'Hello');
    });

    test('combines first sentences from multiple messages', () async {
      final response = await agent.generateSummary(
        userMessages: [
          'Feeling good today. Sun is out.',
          'Work was productive! Got a lot done.',
        ],
      );
      expect(response.content, contains('Feeling good today.'));
      expect(response.content, contains('Work was productive!'));
    });
  });
}
