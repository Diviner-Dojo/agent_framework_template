import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:agentic_journal/providers/location_providers.dart';
import 'package:agentic_journal/providers/onboarding_providers.dart';
import 'package:agentic_journal/services/location_service.dart';

void main() {
  group('LocationEnabledNotifier', () {
    test('defaults to false when no preference set', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );

      expect(container.read(locationEnabledProvider), false);
      container.dispose();
    });

    test('reads true from SharedPreferences', () async {
      SharedPreferences.setMockInitialValues({locationEnabledKey: true});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );

      expect(container.read(locationEnabledProvider), true);
      container.dispose();
    });

    test('setEnabled persists and updates state', () async {
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();

      final container = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );

      expect(container.read(locationEnabledProvider), false);

      await container.read(locationEnabledProvider.notifier).setEnabled(true);
      expect(container.read(locationEnabledProvider), true);
      expect(prefs.getBool(locationEnabledKey), true);

      await container.read(locationEnabledProvider.notifier).setEnabled(false);
      expect(container.read(locationEnabledProvider), false);
      expect(prefs.getBool(locationEnabledKey), false);

      container.dispose();
    });
  });

  group('locationServiceProvider', () {
    test('provides a LocationService instance', () {
      final container = ProviderContainer();
      final service = container.read(locationServiceProvider);
      expect(service, isA<LocationService>());
      container.dispose();
    });
  });
}
