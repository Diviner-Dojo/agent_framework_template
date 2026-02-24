import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:drift/native.dart';
import 'package:geocoding/geocoding.dart';
import 'package:geolocator/geolocator.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/providers/database_provider.dart';
import 'package:agentic_journal/providers/location_providers.dart';
import 'package:agentic_journal/providers/onboarding_providers.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/repositories/agent_repository.dart';
import 'package:agentic_journal/services/location_service.dart';

/// Creates a fake Position for testing.
Position _makePosition(double lat, double lng) {
  return Position(
    latitude: lat,
    longitude: lng,
    timestamp: DateTime.utc(2026, 2, 25),
    accuracy: 25.0,
    altitude: 0.0,
    altitudeAccuracy: 0.0,
    heading: 0.0,
    headingAccuracy: 0.0,
    speed: 0.0,
    speedAccuracy: 0.0,
  );
}

void main() {
  group('Session location capture (fire-and-forget)', () {
    late ProviderContainer container;
    late AppDatabase database;

    test('captures location when enabled', () async {
      SharedPreferences.setMockInitialValues({locationEnabledKey: true});
      final prefs = await SharedPreferences.getInstance();
      database = AppDatabase.forTesting(NativeDatabase.memory());

      final fakeLocationService = LocationService(
        isLocationServiceEnabled: () async => true,
        checkPermission: () async => LocationPermission.always,
        requestPermission: () async => LocationPermission.always,
        getLastKnownPosition: () async => _makePosition(39.7392, -104.9903),
        getCurrentPosition:
            ({
              LocationAccuracy desiredAccuracy = LocationAccuracy.low,
              Duration? timeLimit,
            }) async => _makePosition(39.7392, -104.9903),
        reverseGeocode: (lat, lng) async => [],
      );

      container = ProviderContainer(
        overrides: [
          databaseProvider.overrideWithValue(database),
          agentRepositoryProvider.overrideWithValue(AgentRepository()),
          sharedPreferencesProvider.overrideWithValue(prefs),
          locationServiceProvider.overrideWithValue(fakeLocationService),
        ],
      );

      final notifier = container.read(sessionNotifierProvider.notifier);
      final sessionId = await notifier.startSession();

      // The fire-and-forget capture runs asynchronously.
      // Give it a tick to complete.
      await Future<void>.delayed(const Duration(milliseconds: 100));

      final sessionDao = container.read(sessionDaoProvider);
      final session = await sessionDao.getSessionById(sessionId);

      // Location should have been captured.
      expect(session!.latitude, 39.74);
      expect(session.longitude, -104.99);

      container.dispose();
      await database.close();
    });

    test('skips location capture when disabled', () async {
      SharedPreferences.setMockInitialValues({locationEnabledKey: false});
      final prefs = await SharedPreferences.getInstance();
      database = AppDatabase.forTesting(NativeDatabase.memory());

      container = ProviderContainer(
        overrides: [
          databaseProvider.overrideWithValue(database),
          agentRepositoryProvider.overrideWithValue(AgentRepository()),
          sharedPreferencesProvider.overrideWithValue(prefs),
        ],
      );

      final notifier = container.read(sessionNotifierProvider.notifier);
      final sessionId = await notifier.startSession();

      await Future<void>.delayed(const Duration(milliseconds: 100));

      final sessionDao = container.read(sessionDaoProvider);
      final session = await sessionDao.getSessionById(sessionId);

      // Location should NOT have been captured.
      expect(session!.latitude, isNull);
      expect(session.longitude, isNull);

      container.dispose();
      await database.close();
    });

    test('captures location with geocoded name', () async {
      SharedPreferences.setMockInitialValues({locationEnabledKey: true});
      final prefs = await SharedPreferences.getInstance();
      database = AppDatabase.forTesting(NativeDatabase.memory());

      final fakeLocationService = LocationService(
        isLocationServiceEnabled: () async => true,
        checkPermission: () async => LocationPermission.always,
        requestPermission: () async => LocationPermission.always,
        getLastKnownPosition: () async => _makePosition(39.7392, -104.9903),
        getCurrentPosition:
            ({
              LocationAccuracy desiredAccuracy = LocationAccuracy.low,
              Duration? timeLimit,
            }) async => _makePosition(39.7392, -104.9903),
        reverseGeocode: (lat, lng) async => [
          Placemark(
            locality: 'Denver',
            administrativeArea: 'Colorado',
            country: 'United States',
          ),
        ],
      );

      container = ProviderContainer(
        overrides: [
          databaseProvider.overrideWithValue(database),
          agentRepositoryProvider.overrideWithValue(AgentRepository()),
          sharedPreferencesProvider.overrideWithValue(prefs),
          locationServiceProvider.overrideWithValue(fakeLocationService),
        ],
      );

      final notifier = container.read(sessionNotifierProvider.notifier);
      final sessionId = await notifier.startSession();

      await Future<void>.delayed(const Duration(milliseconds: 100));

      final sessionDao = container.read(sessionDaoProvider);
      final session = await sessionDao.getSessionById(sessionId);

      expect(session!.locationName, 'Denver, Colorado');

      container.dispose();
      await database.close();
    });

    test('handles location failure gracefully', () async {
      SharedPreferences.setMockInitialValues({locationEnabledKey: true});
      final prefs = await SharedPreferences.getInstance();
      database = AppDatabase.forTesting(NativeDatabase.memory());

      // Location service that returns null (permission denied).
      final fakeLocationService = LocationService(
        isLocationServiceEnabled: () async => false,
        checkPermission: () async => LocationPermission.denied,
        requestPermission: () async => LocationPermission.denied,
        getLastKnownPosition: () async => null,
        getCurrentPosition:
            ({
              LocationAccuracy desiredAccuracy = LocationAccuracy.low,
              Duration? timeLimit,
            }) async => _makePosition(0, 0),
        reverseGeocode: (lat, lng) async => [],
      );

      container = ProviderContainer(
        overrides: [
          databaseProvider.overrideWithValue(database),
          agentRepositoryProvider.overrideWithValue(AgentRepository()),
          sharedPreferencesProvider.overrideWithValue(prefs),
          locationServiceProvider.overrideWithValue(fakeLocationService),
        ],
      );

      final notifier = container.read(sessionNotifierProvider.notifier);
      final sessionId = await notifier.startSession();

      await Future<void>.delayed(const Duration(milliseconds: 100));

      final sessionDao = container.read(sessionDaoProvider);
      final session = await sessionDao.getSessionById(sessionId);

      // Session should be created but no location.
      expect(session!.latitude, isNull);
      expect(session.longitude, isNull);

      container.dispose();
      await database.close();
    });
  });
}
