// ===========================================================================
// file: test/models/personality_config_test.dart
// purpose: Tests for PersonalityConfig data model, serialization, and
//          custom prompt sanitization.
//
// See: SPEC-20260224-014525 §R5, §R8
// ===========================================================================

import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/models/personality_config.dart';

void main() {
  group('PersonalityConfig.defaults()', () {
    test('returns expected default values', () {
      final config = PersonalityConfig.defaults();
      expect(config.name, 'Guy');
      expect(config.conversationStyle, ConversationStyle.warm);
      expect(config.customPrompt, isNull);
      expect(config.systemPrompt, contains('journaling companion'));
    });

    test('effectiveSystemPrompt equals systemPrompt when no custom', () {
      final config = PersonalityConfig.defaults();
      expect(config.effectiveSystemPrompt, config.systemPrompt);
    });
  });

  group('effectiveSystemPrompt', () {
    test('appends custom prompt when present', () {
      final config = PersonalityConfig.defaults().copyWith(
        customPrompt: 'Be extra gentle.',
      );
      expect(config.effectiveSystemPrompt, contains(config.systemPrompt));
      expect(config.effectiveSystemPrompt, contains('Be extra gentle.'));
      expect(config.effectiveSystemPrompt, contains('\n\n'));
    });

    test('ignores empty custom prompt', () {
      final config = PersonalityConfig.defaults().copyWith(customPrompt: '');
      expect(config.effectiveSystemPrompt, config.systemPrompt);
    });
  });

  group('Serialization', () {
    test('toJson/fromJson round-trip preserves all fields', () {
      const config = PersonalityConfig(
        name: 'Ava',
        systemPrompt: 'You are Ava.',
        conversationStyle: ConversationStyle.curious,
        customPrompt: 'Be playful.',
      );
      final json = config.toJson();
      final restored = PersonalityConfig.fromJson(json);
      expect(restored, config);
    });

    test('toJsonString/fromJsonString round-trip', () {
      const config = PersonalityConfig(
        name: 'Test',
        systemPrompt: 'Test prompt.',
        conversationStyle: ConversationStyle.professional,
      );
      final jsonStr = config.toJsonString();
      final restored = PersonalityConfig.fromJsonString(jsonStr);
      expect(restored, config);
    });

    test('fromJson ignores unknown keys', () {
      final json = {
        'name': 'Guy',
        'systemPrompt': 'Prompt',
        'conversationStyle': 'warm',
        'unknownField': 42,
        'anotherOne': true,
      };
      final config = PersonalityConfig.fromJson(json);
      expect(config.name, 'Guy');
      expect(config.systemPrompt, 'Prompt');
      expect(config.conversationStyle, ConversationStyle.warm);
    });

    test('fromJson uses defaults for missing required fields', () {
      final config = PersonalityConfig.fromJson({});
      final defaults = PersonalityConfig.defaults();
      expect(config.name, defaults.name);
      expect(config.systemPrompt, defaults.systemPrompt);
      expect(config.conversationStyle, defaults.conversationStyle);
    });

    test('fromJson uses defaults for wrong types', () {
      final config = PersonalityConfig.fromJson({
        'name': 123,
        'systemPrompt': true,
        'conversationStyle': 42,
      });
      final defaults = PersonalityConfig.defaults();
      expect(config.name, defaults.name);
      expect(config.systemPrompt, defaults.systemPrompt);
      expect(config.conversationStyle, defaults.conversationStyle);
    });

    test('fromJson handles unknown conversationStyle gracefully', () {
      final config = PersonalityConfig.fromJson({
        'conversationStyle': 'nonexistent',
      });
      expect(
        config.conversationStyle,
        PersonalityConfig.defaults().conversationStyle,
      );
    });

    test('fromJsonString returns defaults on corrupted JSON', () {
      final config = PersonalityConfig.fromJsonString('not valid json');
      final defaults = PersonalityConfig.defaults();
      expect(config.name, defaults.name);
    });

    test('fromJsonString returns defaults on JSON array', () {
      final config = PersonalityConfig.fromJsonString('[1, 2, 3]');
      final defaults = PersonalityConfig.defaults();
      expect(config.name, defaults.name);
    });

    test('fromJsonString returns defaults on empty string', () {
      final config = PersonalityConfig.fromJsonString('');
      final defaults = PersonalityConfig.defaults();
      expect(config.name, defaults.name);
    });

    test('toJson includes null customPrompt', () {
      const config = PersonalityConfig(
        name: 'Guy',
        systemPrompt: 'Prompt',
        conversationStyle: ConversationStyle.warm,
      );
      final json = config.toJson();
      expect(json.containsKey('customPrompt'), isTrue);
      expect(json['customPrompt'], isNull);
    });
  });

  group('sanitizeCustomPrompt', () {
    test('trims whitespace', () {
      expect(PersonalityConfig.sanitizeCustomPrompt('  hello  '), 'hello');
    });

    test('strips control characters except newlines', () {
      expect(
        PersonalityConfig.sanitizeCustomPrompt('hello\x00world\x01'),
        'helloworld',
      );
    });

    test('preserves newlines', () {
      expect(
        PersonalityConfig.sanitizeCustomPrompt('line1\nline2'),
        'line1\nline2',
      );
    });

    test('strips ChatML markers', () {
      expect(
        PersonalityConfig.sanitizeCustomPrompt('<|im_start|>system'),
        'system',
      );
      expect(PersonalityConfig.sanitizeCustomPrompt('text<|im_end|>'), 'text');
    });

    test('strips Human: and Assistant: role markers', () {
      expect(PersonalityConfig.sanitizeCustomPrompt('Human: hello'), 'hello');
      expect(PersonalityConfig.sanitizeCustomPrompt('Assistant: hi'), 'hi');
    });

    test('strips ### System markers', () {
      expect(
        PersonalityConfig.sanitizeCustomPrompt('### System prompt'),
        'prompt',
      );
    });

    test('accepts exactly 500 characters', () {
      final input = 'a' * 500;
      expect(PersonalityConfig.sanitizeCustomPrompt(input).length, 500);
    });

    test('truncates at 501 characters', () {
      final input = 'a' * 501;
      expect(PersonalityConfig.sanitizeCustomPrompt(input).length, 500);
    });

    test('returns empty string for only control characters', () {
      expect(PersonalityConfig.sanitizeCustomPrompt('\x00\x01\x02'), isEmpty);
    });

    test('returns empty string for only whitespace', () {
      expect(PersonalityConfig.sanitizeCustomPrompt('   '), isEmpty);
    });

    test('strips Llama format markers', () {
      expect(
        PersonalityConfig.sanitizeCustomPrompt('[INST]do this[/INST]'),
        'do this',
      );
    });

    test('strips generic role markers', () {
      expect(
        PersonalityConfig.sanitizeCustomPrompt(
          '<|system|>prompt<|user|>hi<|assistant|>',
        ),
        'prompthi',
      );
    });

    test('handles combined sanitization rules', () {
      final input = '  <|im_start|>Human: be nice\x00  ';
      final result = PersonalityConfig.sanitizeCustomPrompt(input);
      expect(result, 'be nice');
    });
  });

  group('Equality', () {
    test('equal configs are equal', () {
      const a = PersonalityConfig(
        name: 'Guy',
        systemPrompt: 'Prompt',
        conversationStyle: ConversationStyle.warm,
      );
      const b = PersonalityConfig(
        name: 'Guy',
        systemPrompt: 'Prompt',
        conversationStyle: ConversationStyle.warm,
      );
      expect(a, b);
      expect(a.hashCode, b.hashCode);
    });

    test('different name means not equal', () {
      const a = PersonalityConfig(
        name: 'Guy',
        systemPrompt: 'Prompt',
        conversationStyle: ConversationStyle.warm,
      );
      const b = PersonalityConfig(
        name: 'Ava',
        systemPrompt: 'Prompt',
        conversationStyle: ConversationStyle.warm,
      );
      expect(a, isNot(b));
    });

    test('different customPrompt means not equal', () {
      const a = PersonalityConfig(
        name: 'Guy',
        systemPrompt: 'Prompt',
        conversationStyle: ConversationStyle.warm,
        customPrompt: 'Hello',
      );
      const b = PersonalityConfig(
        name: 'Guy',
        systemPrompt: 'Prompt',
        conversationStyle: ConversationStyle.warm,
      );
      expect(a, isNot(b));
    });
  });

  group('copyWith', () {
    test('copies with name change', () {
      final config = PersonalityConfig.defaults();
      final updated = config.copyWith(name: 'Ava');
      expect(updated.name, 'Ava');
      expect(updated.systemPrompt, config.systemPrompt);
      expect(updated.conversationStyle, config.conversationStyle);
    });

    test('copies with conversationStyle change', () {
      final config = PersonalityConfig.defaults();
      final updated = config.copyWith(
        conversationStyle: ConversationStyle.professional,
      );
      expect(updated.conversationStyle, ConversationStyle.professional);
      expect(updated.name, config.name);
    });

    test('copies with customPrompt', () {
      final config = PersonalityConfig.defaults();
      final updated = config.copyWith(customPrompt: 'Be gentle.');
      expect(updated.customPrompt, 'Be gentle.');
    });

    test('clearCustomPrompt sets customPrompt to null', () {
      const config = PersonalityConfig(
        name: 'Guy',
        systemPrompt: 'P',
        conversationStyle: ConversationStyle.warm,
        customPrompt: 'Something',
      );
      final updated = config.copyWith(clearCustomPrompt: true);
      expect(updated.customPrompt, isNull);
    });
  });

  group('ConversationStyle', () {
    test('all styles have correct names', () {
      expect(ConversationStyle.warm.name, 'warm');
      expect(ConversationStyle.professional.name, 'professional');
      expect(ConversationStyle.curious.name, 'curious');
    });

    test('all styles survive JSON round-trip', () {
      for (final style in ConversationStyle.values) {
        final config = PersonalityConfig(
          name: 'Test',
          systemPrompt: 'Prompt',
          conversationStyle: style,
        );
        final jsonStr = config.toJsonString();
        final restored = PersonalityConfig.fromJsonString(jsonStr);
        expect(restored.conversationStyle, style);
      }
    });
  });
}
