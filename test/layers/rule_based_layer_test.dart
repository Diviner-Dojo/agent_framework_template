import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/layers/rule_based_layer.dart';
import 'package:agentic_journal/models/agent_response.dart';

void main() {
  late RuleBasedLayer layer;

  setUp(() {
    layer = RuleBasedLayer();
  });

  group('RuleBasedLayer getGreeting', () {
    test('returns morning greeting between 5 AM and 11:59 AM', () async {
      final morning = DateTime(2026, 2, 23, 8, 0);
      final response = await layer.getGreeting(now: morning);
      expect(
        response.content,
        'Good morning! Any plans or thoughts for today?',
      );
      expect(response.layer, AgentLayer.ruleBasedLocal);
    });

    test('returns afternoon greeting between 12 PM and 4:59 PM', () async {
      final afternoon = DateTime(2026, 2, 23, 14, 0);
      final response = await layer.getGreeting(now: afternoon);
      expect(response.content, "How's your afternoon going?");
      expect(response.layer, AgentLayer.ruleBasedLocal);
    });

    test('returns evening greeting between 5 PM and 9:59 PM', () async {
      final evening = DateTime(2026, 2, 23, 19, 0);
      final response = await layer.getGreeting(now: evening);
      expect(response.content, 'How was your day?');
    });

    test('returns late night greeting between 10 PM and 4:59 AM', () async {
      final lateNight = DateTime(2026, 2, 23, 23, 0);
      final response = await layer.getGreeting(now: lateNight);
      expect(response.content, "Still up? What's on your mind?");
    });

    test('returns gap greeting when last session was 2+ days ago', () async {
      final now = DateTime(2026, 2, 23, 10, 0);
      final twoDaysAgo = DateTime(2026, 2, 21, 10, 0);
      final response = await layer.getGreeting(
        lastSessionDate: twoDaysAgo,
        now: now,
      );
      expect(response.content, "It's been a few days — want to catch up?");
    });

    test(
      'returns time-of-day greeting when last session was 1 day ago',
      () async {
        final now = DateTime(2026, 2, 23, 10, 0);
        final yesterday = DateTime(2026, 2, 22, 10, 0);
        final response = await layer.getGreeting(
          lastSessionDate: yesterday,
          now: now,
        );
        expect(
          response.content,
          'Good morning! Any plans or thoughts for today?',
        );
      },
    );

    test('ignores sessionCount (rule-based has no use for it)', () async {
      final now = DateTime(2026, 2, 23, 10, 0);
      final response = await layer.getGreeting(now: now, sessionCount: 100);
      expect(
        response.content,
        'Good morning! Any plans or thoughts for today?',
      );
    });
  });

  group('RuleBasedLayer getFollowUp', () {
    test('returns emotional follow-up for emotional keywords', () async {
      final result = await layer.getFollowUp(
        latestUserMessage: 'I feel so stressed today',
        conversationHistory: [],
        followUpCount: 0,
      );
      expect(result, isNotNull);
      expect(result!.content, isNotEmpty);
      expect(result.layer, AgentLayer.ruleBasedLocal);
    });

    test('returns social follow-up for social keywords', () async {
      final result = await layer.getFollowUp(
        latestUserMessage: 'Had a great time with my friend',
        conversationHistory: [],
        followUpCount: 0,
      );
      expect(result, isNotNull);
      expect(result!.content, isNotEmpty);
    });

    test('returns work follow-up for work keywords', () async {
      final result = await layer.getFollowUp(
        latestUserMessage: 'Big meeting at the office today',
        conversationHistory: [],
        followUpCount: 0,
      );
      expect(result, isNotNull);
      expect(result!.content, isNotEmpty);
    });

    test('returns null when followUpCount exceeds max', () async {
      final result = await layer.getFollowUp(
        latestUserMessage: 'anything',
        conversationHistory: [],
        followUpCount: 4,
      );
      expect(result, isNull);
    });

    test('returns closing message at follow-up count 3', () async {
      final result = await layer.getFollowUp(
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
        final result = await layer.getFollowUp(
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

    test('ignores allMessages parameter (not used by rule-based)', () async {
      final result = await layer.getFollowUp(
        latestUserMessage: 'I feel happy',
        conversationHistory: [],
        followUpCount: 0,
        allMessages: [
          {'role': 'user', 'content': 'I feel happy'},
        ],
      );
      expect(result, isNotNull);
      expect(result!.layer, AgentLayer.ruleBasedLocal);
    });
  });

  group('RuleBasedLayer generateSummary', () {
    test('returns empty string for empty list', () async {
      final response = await layer.generateSummary(userMessages: []);
      expect(response.content, '');
      expect(response.layer, AgentLayer.ruleBasedLocal);
    });

    test('extracts first sentence from single message', () async {
      final response = await layer.generateSummary(
        userMessages: ['I had a great day today. The weather was perfect.'],
      );
      expect(response.content, 'I had a great day today.');
    });

    test('handles single-word message', () async {
      final response = await layer.generateSummary(userMessages: ['Hello']);
      expect(response.content, 'Hello');
    });

    test('combines first sentences from multiple messages', () async {
      final response = await layer.generateSummary(
        userMessages: [
          'Feeling good today. Sun is out.',
          'Work was productive! Got a lot done.',
        ],
      );
      expect(response.content, contains('Feeling good today.'));
      expect(response.content, contains('Work was productive!'));
    });

    test('metadata is always null for rule-based layer', () async {
      final response = await layer.generateSummary(
        userMessages: ['Test message.'],
      );
      expect(response.metadata, isNull);
    });
  });

  group('RuleBasedLayer getResumeGreeting', () {
    test('returns fixed resume greeting', () async {
      final response = await layer.getResumeGreeting();
      expect(
        response.content,
        "Welcome back! Let's continue where you left off.",
      );
      expect(response.layer, AgentLayer.ruleBasedLocal);
    });
  });

  group('RuleBasedLayer generateLocalSummaryText', () {
    test('is accessible for journal-only mode', () {
      final summary = layer.generateLocalSummaryText([
        'Had a good day. Weather was nice.',
      ]);
      expect(summary, 'Had a good day.');
    });

    test('returns empty for empty input', () {
      expect(layer.generateLocalSummaryText([]), '');
    });
  });
}
