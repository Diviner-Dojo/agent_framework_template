import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:agentic_journal/providers/task_providers.dart';

void main() {
  group('TaskAutoSuggestNotifier', () {
    setUp(() {
      SharedPreferences.setMockInitialValues({});
    });

    test('defaults to true', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      expect(container.read(taskAutoSuggestProvider), isTrue);
    });

    test('setEnabled(false) updates state', () async {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      final notifier = container.read(taskAutoSuggestProvider.notifier);

      await notifier.setEnabled(false);
      expect(container.read(taskAutoSuggestProvider), isFalse);
    });

    test('setEnabled(true) after false restores state', () async {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      final notifier = container.read(taskAutoSuggestProvider.notifier);

      await notifier.setEnabled(false);
      await notifier.setEnabled(true);
      expect(container.read(taskAutoSuggestProvider), isTrue);
    });

    test('persists to SharedPreferences', () async {
      final container = ProviderContainer();
      addTearDown(container.dispose);
      final notifier = container.read(taskAutoSuggestProvider.notifier);

      await notifier.setEnabled(false);

      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getBool('task_auto_suggest'), isFalse);
    });

    test('loads persisted value on init', () async {
      SharedPreferences.setMockInitialValues({'task_auto_suggest': false});
      final container = ProviderContainer();

      // Read the provider to trigger creation, then give async _load time.
      container.read(taskAutoSuggestProvider);
      await Future<void>.delayed(const Duration(milliseconds: 100));

      expect(container.read(taskAutoSuggestProvider), isFalse);
      container.dispose();
    });
  });
}
