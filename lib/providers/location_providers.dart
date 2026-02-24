// ===========================================================================
// file: lib/providers/location_providers.dart
// purpose: Riverpod providers for location awareness (Phase 10).
//
// Manages:
//   - locationEnabledProvider: opt-in toggle persisted via SharedPreferences
//     (default: off per ADR-0019 §1)
//   - locationServiceProvider: singleton LocationService instance
//
// The fire-and-forget location capture at session start lives in
// session_providers.dart (SessionNotifier.startSession), not here.
// This file only provides the service and the setting.
//
// See: ADR-0019 (Location Tracking)
// ===========================================================================

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/location_service.dart';
import 'onboarding_providers.dart';

/// SharedPreferences key for the location enabled toggle.
const locationEnabledKey = 'location_enabled';

/// Controls whether location capture is enabled for new sessions.
///
/// Default: false (opt-in per ADR-0019 §1). When enabled, session start
/// captures GPS coordinates in a fire-and-forget pattern. When disabled,
/// location capture is skipped entirely.
///
/// Persisted in SharedPreferences so the setting survives app restarts.
/// Uses the same Notifier pattern as [VoiceModeNotifier].
class LocationEnabledNotifier extends Notifier<bool> {
  @override
  bool build() {
    final prefs = ref.watch(sharedPreferencesProvider);
    return prefs.getBool(locationEnabledKey) ?? false;
  }

  /// Set location tracking on or off. Persists to SharedPreferences.
  Future<void> setEnabled(bool enabled) async {
    final prefs = ref.read(sharedPreferencesProvider);
    await prefs.setBool(locationEnabledKey, enabled);
    state = enabled;
  }
}

/// Provider for the location enabled toggle.
///
/// Watch for the bool value; call `.notifier.setEnabled(bool)` to change.
final locationEnabledProvider = NotifierProvider<LocationEnabledNotifier, bool>(
  LocationEnabledNotifier.new,
);

/// Provides the singleton LocationService instance.
///
/// Uses default geolocator/geocoding implementations in production.
/// Override in tests with a LocationService configured with fake callables.
final locationServiceProvider = Provider<LocationService>((ref) {
  return LocationService();
});
