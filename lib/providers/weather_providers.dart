// ===========================================================================
// file: lib/providers/weather_providers.dart
// purpose: Riverpod provider for the WeatherService singleton (Phase 4C).
//
// Weather capture piggybacks on the location toggle — no separate permission
// or settings toggle is needed. Weather is captured iff location is enabled
// and location capture succeeds (coordinates are then passed to WeatherService).
//
// See: lib/providers/location_providers.dart (locationEnabledProvider)
//      lib/services/weather_service.dart
//      lib/providers/session_providers.dart (_captureWeatherAsync)
// ===========================================================================

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/weather_service.dart';

/// Provides the singleton WeatherService instance.
///
/// Override in tests with a WeatherService configured with a fake fetch
/// callback to avoid real network calls.
final weatherServiceProvider = Provider<WeatherService>((ref) {
  return WeatherService();
});
