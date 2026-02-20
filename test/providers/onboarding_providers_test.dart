// ===========================================================================
// file: test/providers/onboarding_providers_test.dart
// purpose: Tests for onboarding state management providers.
//
// Setup:
//   SharedPreferences.setMockInitialValues({}) is called in setUp() to
//   ensure test isolation. Without this, SharedPreferences retains state
//   across test cases, producing order-dependent results.
// ===========================================================================

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:agentic_journal/providers/onboarding_providers.dart';

void main() {
  group('OnboardingNotifier', () {
    setUp(() {
      // Reset SharedPreferences before each test for isolation.
      SharedPreferences.setMockInitialValues({});
    });

    test('initial state is false when no key exists', () async {
      final prefs = await SharedPreferences.getInstance();
      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      final hasOnboarded = container.read(onboardingNotifierProvider);
      expect(hasOnboarded, isFalse);
    });

    test(
      'initial state is true when key exists in SharedPreferences',
      () async {
        // Pre-set the onboarding key to true.
        SharedPreferences.setMockInitialValues({onboardingCompleteKey: true});
        final prefs = await SharedPreferences.getInstance();
        final container = ProviderContainer(
          overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
        );
        addTearDown(container.dispose);

        final hasOnboarded = container.read(onboardingNotifierProvider);
        expect(hasOnboarded, isTrue);
      },
    );

    test('completeOnboarding sets state to true', () async {
      final prefs = await SharedPreferences.getInstance();
      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      // Initially false.
      expect(container.read(onboardingNotifierProvider), isFalse);

      // Complete onboarding.
      await container
          .read(onboardingNotifierProvider.notifier)
          .completeOnboarding();

      // Now true.
      expect(container.read(onboardingNotifierProvider), isTrue);

      // Verify it was persisted to SharedPreferences.
      expect(prefs.getBool(onboardingCompleteKey), isTrue);
    });

    test('completeOnboarding is idempotent — calling twice is safe', () async {
      final prefs = await SharedPreferences.getInstance();
      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      addTearDown(container.dispose);

      // Call twice — should not throw.
      await container
          .read(onboardingNotifierProvider.notifier)
          .completeOnboarding();
      await container
          .read(onboardingNotifierProvider.notifier)
          .completeOnboarding();

      expect(container.read(onboardingNotifierProvider), isTrue);
    });

    test('sharedPreferencesProvider throws when not overridden', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      expect(
        () => container.read(sharedPreferencesProvider),
        throwsA(isA<UnimplementedError>()),
      );
    });
  });
}
