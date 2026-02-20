import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/models/agent_response.dart';

void main() {
  group('AgentMetadata.fromJson', () {
    test('parses all fields from valid JSON', () {
      final metadata = AgentMetadata.fromJson({
        'summary': 'User had a productive day.',
        'mood_tags': ['happy', 'energetic'],
        'people': ['Sarah', 'Mike'],
        'topic_tags': ['work', 'exercise'],
      });

      expect(metadata.summary, 'User had a productive day.');
      expect(metadata.moodTags, ['happy', 'energetic']);
      expect(metadata.people, ['Sarah', 'Mike']);
      expect(metadata.topicTags, ['work', 'exercise']);
    });

    test('returns null for missing fields', () {
      final metadata = AgentMetadata.fromJson({});

      expect(metadata.summary, isNull);
      expect(metadata.moodTags, isNull);
      expect(metadata.people, isNull);
      expect(metadata.topicTags, isNull);
    });

    test('handles summary being non-string gracefully', () {
      final metadata = AgentMetadata.fromJson({
        'summary': 42,
        'mood_tags': ['happy'],
      });

      expect(metadata.summary, isNull);
      expect(metadata.moodTags, ['happy']);
    });

    test('handles mood_tags being string instead of array', () {
      final metadata = AgentMetadata.fromJson({
        'summary': 'A good day',
        'mood_tags': 'happy',
      });

      expect(metadata.summary, 'A good day');
      expect(metadata.moodTags, isNull);
    });

    test('filters non-string elements from arrays', () {
      final metadata = AgentMetadata.fromJson({
        'mood_tags': ['happy', 42, true, 'sad'],
        'people': ['Sarah', null, 'Mike'],
      });

      expect(metadata.moodTags, ['happy', 'sad']);
      expect(metadata.people, ['Sarah', 'Mike']);
    });

    test('handles empty arrays', () {
      final metadata = AgentMetadata.fromJson({
        'mood_tags': <String>[],
        'people': <String>[],
      });

      expect(metadata.moodTags, isEmpty);
      expect(metadata.people, isEmpty);
    });
  });

  group('AgentResponse', () {
    test('creates with required fields', () {
      const response = AgentResponse(
        content: 'Hello!',
        layer: AgentLayer.ruleBasedLocal,
      );

      expect(response.content, 'Hello!');
      expect(response.layer, AgentLayer.ruleBasedLocal);
      expect(response.metadata, isNull);
    });

    test('creates with metadata', () {
      const metadata = AgentMetadata(summary: 'test', moodTags: ['happy']);
      const response = AgentResponse(
        content: 'Hello!',
        layer: AgentLayer.llmRemote,
        metadata: metadata,
      );

      expect(response.layer, AgentLayer.llmRemote);
      expect(response.metadata, isNotNull);
      expect(response.metadata!.summary, 'test');
    });
  });

  group('AgentLayer', () {
    test('has two values', () {
      expect(AgentLayer.values, hasLength(2));
    });

    test('ruleBasedLocal is the offline layer', () {
      expect(AgentLayer.ruleBasedLocal.name, 'ruleBasedLocal');
    });

    test('llmRemote is the online layer', () {
      expect(AgentLayer.llmRemote.name, 'llmRemote');
    });
  });
}
