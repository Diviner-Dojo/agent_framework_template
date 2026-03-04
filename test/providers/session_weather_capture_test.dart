// ===========================================================================
// file: test/providers/session_weather_capture_test.dart
// purpose: Tests for fire-and-forget weather capture at session start (4C).
//
// Tests verify:
//   - Weather is written to the session row when location is enabled and
//     location capture succeeds (the two preconditions for weather capture).
//   - Weather is NOT written when the weather service returns null (API down).
// ===========================================================================

import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:drift/native.dart';
import 'package:geolocator/geolocator.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/providers/database_provider.dart';
import 'package:agentic_journal/providers/location_providers.dart';
import 'package:agentic_journal/providers/onboarding_providers.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/providers/weather_providers.dart';
import 'package:agentic_journal/repositories/agent_repository.dart';
import 'package:agentic_journal/services/location_service.dart';
import 'package:agentic_journal/services/weather_service.dart';

/// Creates a fake Position for testing.
Position _makePosition(double lat, double lng) {
  return Position(
    latitude: lat,
    longitude: lng,
    timestamp: DateTime.utc(2026, 3, 4),
    accuracy: 20.0,
    altitude: 0.0,
    altitudeAccuracy: 0.0,
    heading: 0.0,
    headingAccuracy: 0.0,
    speed: 0.0,
    speedAccuracy: 0.0,
  );
}

void main() {
  group('Session weather capture (fire-and-forget)', () {
    late AppDatabase database;

    tearDown(() => database.close());

    test(
      'writes weather to session when location enabled and API succeeds',
      () async {
        SharedPreferences.setMockInitialValues({locationEnabledKey: true});
        final prefs = await SharedPreferences.getInstance();
        database = AppDatabase.forTesting(NativeDatabase.memory());

        final fakeLocationService = LocationService(
          isLocationServiceEnabled: () async => true,
          checkPermission: () async => LocationPermission.always,
          requestPermission: () async => LocationPermission.always,
          getLastKnownPosition: () async => _makePosition(39.74, -104.99),
          getCurrentPosition:
              ({
                LocationAccuracy desiredAccuracy = LocationAccuracy.low,
                Duration? timeLimit,
              }) async => _makePosition(39.74, -104.99),
          reverseGeocode: (_, _) async => [],
        );

        final fakeWeatherService = WeatherService(
          fetch: (_) async => {
            'current': {'temperature_2m': 14.5, 'weather_code': 1},
          },
        );

        final container = ProviderContainer(
          overrides: [
            databaseProvider.overrideWithValue(database),
            agentRepositoryProvider.overrideWithValue(AgentRepository()),
            sharedPreferencesProvider.overrideWithValue(prefs),
            locationServiceProvider.overrideWithValue(fakeLocationService),
            weatherServiceProvider.overrideWithValue(fakeWeatherService),
            deviceTimezoneProvider.overrideWith(
              (ref) async => 'America/New_York',
            ),
          ],
        );
        addTearDown(container.dispose);

        final notifier = container.read(sessionNotifierProvider.notifier);
        final sessionId = await notifier.startSession();

        // Fire-and-forget completes asynchronously — wait a tick.
        await Future<void>.delayed(const Duration(milliseconds: 100));

        final sessionDao = container.read(sessionDaoProvider);
        final session = await sessionDao.getSessionById(sessionId);

        expect(session!.weatherTempC, equals(14.5));
        expect(session.weatherCode, equals(1));
        expect(session.weatherDescription, equals('Mainly clear'));
      },
    );

    test('does not write weather when weather API returns null', () async {
      SharedPreferences.setMockInitialValues({locationEnabledKey: true});
      final prefs = await SharedPreferences.getInstance();
      database = AppDatabase.forTesting(NativeDatabase.memory());

      final fakeLocationService = LocationService(
        isLocationServiceEnabled: () async => true,
        checkPermission: () async => LocationPermission.always,
        requestPermission: () async => LocationPermission.always,
        getLastKnownPosition: () async => _makePosition(39.74, -104.99),
        getCurrentPosition:
            ({
              LocationAccuracy desiredAccuracy = LocationAccuracy.low,
              Duration? timeLimit,
            }) async => _makePosition(39.74, -104.99),
        reverseGeocode: (_, _) async => [],
      );

      // Weather API fails — returns null.
      final failingWeatherService = WeatherService(
        fetch: (_) async => throw Exception('API down'),
      );

      final container = ProviderContainer(
        overrides: [
          databaseProvider.overrideWithValue(database),
          agentRepositoryProvider.overrideWithValue(AgentRepository()),
          sharedPreferencesProvider.overrideWithValue(prefs),
          locationServiceProvider.overrideWithValue(fakeLocationService),
          weatherServiceProvider.overrideWithValue(failingWeatherService),
          deviceTimezoneProvider.overrideWith(
            (ref) async => 'America/New_York',
          ),
        ],
      );
      addTearDown(container.dispose);

      final notifier = container.read(sessionNotifierProvider.notifier);
      final sessionId = await notifier.startSession();

      await Future<void>.delayed(const Duration(milliseconds: 100));

      final sessionDao = container.read(sessionDaoProvider);
      final session = await sessionDao.getSessionById(sessionId);

      // Weather columns remain null — session still created successfully.
      expect(session!.weatherTempC, isNull);
      expect(session.weatherCode, isNull);
      expect(session.weatherDescription, isNull);
    });

    test('does not write weather when location is disabled', () async {
      // Location disabled → location capture never fires → weather never fires.
      SharedPreferences.setMockInitialValues({locationEnabledKey: false});
      final prefs = await SharedPreferences.getInstance();
      database = AppDatabase.forTesting(NativeDatabase.memory());

      var weatherCallCount = 0;
      final trackingWeatherService = WeatherService(
        fetch: (_) async {
          weatherCallCount++;
          return {
            'current': {'temperature_2m': 10.0, 'weather_code': 0},
          };
        },
      );

      final container = ProviderContainer(
        overrides: [
          databaseProvider.overrideWithValue(database),
          agentRepositoryProvider.overrideWithValue(AgentRepository()),
          sharedPreferencesProvider.overrideWithValue(prefs),
          weatherServiceProvider.overrideWithValue(trackingWeatherService),
          deviceTimezoneProvider.overrideWith(
            (ref) async => 'America/New_York',
          ),
        ],
      );
      addTearDown(container.dispose);

      final notifier = container.read(sessionNotifierProvider.notifier);
      await notifier.startSession();

      await Future<void>.delayed(const Duration(milliseconds: 100));

      expect(
        weatherCallCount,
        equals(0),
        reason: 'weather must not be called when location is disabled',
      );
    });
  });
}
