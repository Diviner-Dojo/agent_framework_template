// ===========================================================================
// file: test/providers/last_capture_mode_provider_test.dart
// purpose: Unit tests for LastCaptureModeNotifier + lastCaptureModeProvider.
//
// Tests cover:
//   - Initial state is null when no SharedPreferences value exists
//   - Initial state reads existing SharedPreferences value
//   - setMode persists mode key and updates state
//   - setMode(null) clears preference and resets state to null
//   - All valid mode keys round-trip correctly
//
// See: lib/providers/last_capture_mode_provider.dart, SPEC-20260302 Phase 3A
// ===========================================================================

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:agentic_journal/providers/last_capture_mode_provider.dart';
import 'package:agentic_journal/providers/onboarding_providers.dart';

void main() {
  group('LastCaptureModeNotifier', () {
    late SharedPreferences prefs;

    setUp(() async {
      SharedPreferences.setMockInitialValues({});
      prefs = await SharedPreferences.getInstance();
    });

    ProviderContainer makeContainer() => ProviderContainer(
      overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
    );

    test('initial state is null when no preference exists', () {
      final container = makeContainer();
      addTearDown(container.dispose);

      expect(container.read(lastCaptureModeProvider), isNull);
    });

    test('initial state reads existing SharedPreferences value', () async {
      SharedPreferences.setMockInitialValues({'last_capture_mode': 'voice'});
      prefs = await SharedPreferences.getInstance();
      final container = makeContainer();
      addTearDown(container.dispose);

      expect(container.read(lastCaptureModeProvider), equals('voice'));
    });

    test('setMode persists mode key and updates state', () async {
      final container = makeContainer();
      addTearDown(container.dispose);

      await container.read(lastCaptureModeProvider.notifier).setMode('text');

      expect(container.read(lastCaptureModeProvider), equals('text'));
      expect(prefs.getString('last_capture_mode'), equals('text'));
    });

    test('setMode(null) clears preference and resets state to null', () async {
      final container = makeContainer();
      addTearDown(container.dispose);

      await container.read(lastCaptureModeProvider.notifier).setMode('voice');
      await container.read(lastCaptureModeProvider.notifier).setMode(null);

      expect(container.read(lastCaptureModeProvider), isNull);
      expect(prefs.getString('last_capture_mode'), isNull);
    });

    test('all valid mode keys round-trip through setMode', () async {
      const modes = [
        'text',
        'voice',
        'photo',
        '__quick_mood_tap__',
        'pulse_check_in',
      ];

      for (final mode in modes) {
        final container = makeContainer();
        addTearDown(container.dispose);

        await container.read(lastCaptureModeProvider.notifier).setMode(mode);

        expect(
          container.read(lastCaptureModeProvider),
          equals(mode),
          reason: 'mode key $mode should round-trip',
        );
        expect(prefs.getString('last_capture_mode'), equals(mode));
      }
    });

    test('successive setMode calls update to latest value', () async {
      final container = makeContainer();
      addTearDown(container.dispose);

      await container.read(lastCaptureModeProvider.notifier).setMode('text');
      await container
          .read(lastCaptureModeProvider.notifier)
          .setMode('pulse_check_in');

      expect(container.read(lastCaptureModeProvider), equals('pulse_check_in'));
      expect(prefs.getString('last_capture_mode'), equals('pulse_check_in'));
    });
  });
}
