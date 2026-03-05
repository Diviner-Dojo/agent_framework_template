import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/models/journaling_mode.dart';

void main() {
  group('JournalingMode', () {
    test('has seven values', () {
      expect(JournalingMode.values, hasLength(7));
    });

    test('displayName returns human-readable names', () {
      expect(JournalingMode.free.displayName, 'Free Journal');
      expect(JournalingMode.gratitude.displayName, 'Gratitude');
      expect(JournalingMode.dreamAnalysis.displayName, 'Dream Analysis');
      expect(JournalingMode.moodCheckIn.displayName, 'Mood Check-In');
      expect(JournalingMode.onboarding.displayName, 'Onboarding');
      expect(JournalingMode.pulseCheckIn.displayName, 'Pulse Check-In');
      expect(JournalingMode.quickMoodTap.displayName, 'Quick Mood Tap');
    });

    test('systemPromptFragment is empty for free mode', () {
      expect(JournalingMode.free.systemPromptFragment, '');
    });

    test('systemPromptFragment is non-empty for guided modes', () {
      expect(JournalingMode.gratitude.systemPromptFragment, isNotEmpty);
      expect(JournalingMode.dreamAnalysis.systemPromptFragment, isNotEmpty);
      expect(JournalingMode.moodCheckIn.systemPromptFragment, isNotEmpty);
      expect(JournalingMode.onboarding.systemPromptFragment, isNotEmpty);
    });

    test('pulseCheckIn systemPromptFragment is empty (form-driven mode)', () {
      // pulseCheckIn is driven by CheckInNotifier — the LLM is not prompted
      // to read questionnaire items. The prompt fragment must be empty.
      expect(JournalingMode.pulseCheckIn.systemPromptFragment, isEmpty);
    });

    test('quickMoodTap systemPromptFragment is empty (no LLM)', () {
      // quickMoodTap saves a minimal session without any AI conversation.
      expect(JournalingMode.quickMoodTap.systemPromptFragment, isEmpty);
    });

    test('gratitude prompt contains numbered steps', () {
      final prompt = JournalingMode.gratitude.systemPromptFragment;
      expect(prompt, contains('Step 1'));
      expect(prompt, contains('Step 2'));
      expect(prompt, contains('Step 3'));
      expect(prompt, contains('Gratitude Practice'));
    });

    test('dreamAnalysis prompt contains four steps', () {
      final prompt = JournalingMode.dreamAnalysis.systemPromptFragment;
      expect(prompt, contains('Step 1'));
      expect(prompt, contains('Step 4'));
      expect(prompt, contains('Dream Analysis'));
    });

    test('moodCheckIn prompt contains three steps', () {
      final prompt = JournalingMode.moodCheckIn.systemPromptFragment;
      expect(prompt, contains('Step 1'));
      expect(prompt, contains('Step 3'));
      expect(prompt, contains('Mood Check-In'));
    });

    test('onboarding prompt contains four steps', () {
      final prompt = JournalingMode.onboarding.systemPromptFragment;
      expect(prompt, contains('Step 1'));
      expect(prompt, contains('Step 4'));
      expect(prompt, contains('Onboarding'));
    });
  });

  group('JournalingMode.toDbString', () {
    test('converts to snake_case strings', () {
      expect(JournalingMode.free.toDbString(), 'free');
      expect(JournalingMode.gratitude.toDbString(), 'gratitude');
      expect(JournalingMode.dreamAnalysis.toDbString(), 'dream_analysis');
      expect(JournalingMode.moodCheckIn.toDbString(), 'mood_check_in');
      expect(JournalingMode.onboarding.toDbString(), 'onboarding');
      expect(JournalingMode.pulseCheckIn.toDbString(), 'pulse_check_in');
      expect(JournalingMode.quickMoodTap.toDbString(), 'quick_mood_tap');
    });
  });

  group('JournalingMode.fromDbString', () {
    test('parses all known values', () {
      expect(JournalingMode.fromDbString('free'), JournalingMode.free);
      expect(
        JournalingMode.fromDbString('gratitude'),
        JournalingMode.gratitude,
      );
      expect(
        JournalingMode.fromDbString('dream_analysis'),
        JournalingMode.dreamAnalysis,
      );
      expect(
        JournalingMode.fromDbString('mood_check_in'),
        JournalingMode.moodCheckIn,
      );
      expect(
        JournalingMode.fromDbString('onboarding'),
        JournalingMode.onboarding,
      );
      expect(
        JournalingMode.fromDbString('pulse_check_in'),
        JournalingMode.pulseCheckIn,
      );
      expect(
        JournalingMode.fromDbString('quick_mood_tap'),
        JournalingMode.quickMoodTap,
      );
    });

    test('returns null for null input', () {
      expect(JournalingMode.fromDbString(null), isNull);
    });

    test('returns null for unrecognized values (forward compatibility)', () {
      expect(JournalingMode.fromDbString('future_mode'), isNull);
      expect(JournalingMode.fromDbString(''), isNull);
      expect(JournalingMode.fromDbString('GRATITUDE'), isNull);
    });

    test('round-trips for all values', () {
      for (final mode in JournalingMode.values) {
        final dbString = mode.toDbString();
        final roundTripped = JournalingMode.fromDbString(dbString);
        expect(roundTripped, mode);
      }
    });
  });
}
