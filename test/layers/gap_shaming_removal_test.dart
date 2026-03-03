// ===========================================================================
// file: test/layers/gap_shaming_removal_test.dart
// purpose: Regression tests for Phase 2A gap-shaming removal.
//
// Verifies that none of the AI layers inject days-since-last into their
// greeting output, regardless of how many days have passed.
//
// Tagged @Tags(['regression']) — these tests must not be removed or weakened
// without explicit developer approval. See memory/bugs/regression-ledger.md.
// ===========================================================================

@Tags(['regression'])
library;

import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/layers/rule_based_layer.dart';

void main() {
  group('Phase 2A — gap-shaming removal', () {
    late RuleBasedLayer layer;

    setUp(() {
      layer = RuleBasedLayer();
    });

    test(
      'rule_based_layer greeting does not mention days or gap after 2-day absence',
      () async {
        // 2-day gap previously triggered "It's been a few days — want to catch up?"
        final response = await layer.getGreeting(
          lastSessionDate: DateTime.now().subtract(const Duration(days: 2)),
          sessionCount: 5,
        );
        final content = response.content.toLowerCase();
        expect(content, isNot(contains('been')));
        expect(content, isNot(contains('days')));
        expect(content, isNot(contains('while')));
        expect(content, isNot(contains('catch up')));
      },
    );

    test(
      'rule_based_layer greeting does not mention gap after 30-day absence',
      () async {
        final response = await layer.getGreeting(
          lastSessionDate: DateTime.now().subtract(const Duration(days: 30)),
          sessionCount: 10,
        );
        final content = response.content.toLowerCase();
        expect(content, isNot(contains('been')));
        expect(content, isNot(contains('days')));
        expect(content, isNot(contains('month')));
      },
    );

    test(
      'rule_based_layer returns present-focused greeting at any time of day',
      () async {
        // Morning greeting
        final morning = await layer.getGreeting(
          lastSessionDate: DateTime.now().subtract(const Duration(days: 7)),
          sessionCount: 3,
          now: DateTime(2026, 3, 3, 9, 0), // 9 AM
        );
        expect(morning.content, isNotEmpty);
        expect(morning.content.toLowerCase(), isNot(contains('been')));
        expect(morning.content.toLowerCase(), isNot(contains('7 days')));

        // Evening greeting
        final evening = await layer.getGreeting(
          lastSessionDate: DateTime.now().subtract(const Duration(days: 7)),
          sessionCount: 3,
          now: DateTime(2026, 3, 3, 19, 0), // 7 PM
        );
        expect(evening.content, isNotEmpty);
        expect(evening.content.toLowerCase(), isNot(contains('been')));
      },
    );
  });
}
