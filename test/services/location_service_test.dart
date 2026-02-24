import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:geolocator/geolocator.dart';
import 'package:geocoding/geocoding.dart' as geocoding;
import 'package:agentic_journal/services/location_service.dart';

/// Creates a Position with the given coordinates for testing.
Position _makePosition(double lat, double lng, {double accuracy = 10.0}) {
  return Position(
    latitude: lat,
    longitude: lng,
    timestamp: DateTime.utc(2026, 2, 25),
    accuracy: accuracy,
    altitude: 0.0,
    altitudeAccuracy: 0.0,
    heading: 0.0,
    headingAccuracy: 0.0,
    speed: 0.0,
    speedAccuracy: 0.0,
  );
}

/// Creates a Placemark for testing reverse geocoding.
geocoding.Placemark _makePlacemark({
  String? locality,
  String? administrativeArea,
  String? country,
}) {
  return geocoding.Placemark(
    locality: locality,
    administrativeArea: administrativeArea,
    country: country,
  );
}

void main() {
  group('LocationService.roundCoordinate', () {
    test('rounds to 2 decimal places', () {
      expect(LocationService.roundCoordinate(39.7392), 39.74);
      expect(LocationService.roundCoordinate(-104.9903), -104.99);
    });

    test('uses IEEE 754 round-half-to-even (banker rounding)', () {
      // 39.745 * 100 = 3974.5 → rounds to 3974 (even) → 39.74
      expect(LocationService.roundCoordinate(39.745), 39.74);
      // 39.755 * 100 = 3975.5 → rounds to 3976 (even) → 39.76
      expect(LocationService.roundCoordinate(39.755), 39.76);
    });

    test('handles zero', () {
      expect(LocationService.roundCoordinate(0.0), 0.0);
    });

    test('handles negative coordinates', () {
      expect(LocationService.roundCoordinate(-33.8688), -33.87);
      expect(LocationService.roundCoordinate(-0.005), -0.01);
    });

    test('handles max latitude/longitude', () {
      expect(LocationService.roundCoordinate(90.0), 90.0);
      expect(LocationService.roundCoordinate(-90.0), -90.0);
      expect(LocationService.roundCoordinate(180.0), 180.0);
      expect(LocationService.roundCoordinate(-180.0), -180.0);
    });

    test('already-rounded values pass through unchanged', () {
      expect(LocationService.roundCoordinate(39.74), 39.74);
      expect(LocationService.roundCoordinate(-105.0), -105.0);
    });
  });

  group('LocationService.getLocation', () {
    test('returns null when location service is disabled', () async {
      final service = LocationService(
        isLocationServiceEnabled: () async => false,
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

      final result = await service.getLocation();
      expect(result, isNull);
    });

    test('returns null when permission is denied', () async {
      final service = LocationService(
        isLocationServiceEnabled: () async => true,
        checkPermission: () async => LocationPermission.denied,
        requestPermission: () async => LocationPermission.denied,
        getLastKnownPosition: () async => _makePosition(39.7392, -104.9903),
        getCurrentPosition:
            ({
              LocationAccuracy desiredAccuracy = LocationAccuracy.low,
              Duration? timeLimit,
            }) async => _makePosition(39.7392, -104.9903),
        reverseGeocode: (lat, lng) async => [],
      );

      final result = await service.getLocation();
      expect(result, isNull);
    });

    test('returns null when permission is deniedForever', () async {
      final service = LocationService(
        isLocationServiceEnabled: () async => true,
        checkPermission: () async => LocationPermission.deniedForever,
        requestPermission: () async => LocationPermission.deniedForever,
        getLastKnownPosition: () async => _makePosition(39.7392, -104.9903),
        getCurrentPosition:
            ({
              LocationAccuracy desiredAccuracy = LocationAccuracy.low,
              Duration? timeLimit,
            }) async => _makePosition(39.7392, -104.9903),
        reverseGeocode: (lat, lng) async => [],
      );

      final result = await service.getLocation();
      expect(result, isNull);
    });

    test(
      'requests permission when initially denied, succeeds on grant',
      () async {
        final service = LocationService(
          isLocationServiceEnabled: () async => true,
          checkPermission: () async => LocationPermission.denied,
          requestPermission: () async => LocationPermission.whileInUse,
          getLastKnownPosition: () async => _makePosition(39.7392, -104.9903),
          getCurrentPosition:
              ({
                LocationAccuracy desiredAccuracy = LocationAccuracy.low,
                Duration? timeLimit,
              }) async => _makePosition(39.7392, -104.9903),
          reverseGeocode: (lat, lng) async => [
            _makePlacemark(locality: 'Denver', administrativeArea: 'Colorado'),
          ],
        );

        final result = await service.getLocation();
        expect(result, isNotNull);
        expect(result!.latitude, 39.74);
        expect(result.longitude, -104.99);
      },
    );

    test('uses lastKnownPosition when available', () async {
      bool getCurrentPositionCalled = false;

      final service = LocationService(
        isLocationServiceEnabled: () async => true,
        checkPermission: () async => LocationPermission.always,
        requestPermission: () async => LocationPermission.always,
        getLastKnownPosition: () async =>
            _makePosition(39.7392, -104.9903, accuracy: 15.0),
        getCurrentPosition:
            ({
              LocationAccuracy desiredAccuracy = LocationAccuracy.low,
              Duration? timeLimit,
            }) async {
              getCurrentPositionCalled = true;
              return _makePosition(39.7392, -104.9903);
            },
        reverseGeocode: (lat, lng) async => [],
      );

      final result = await service.getLocation();
      expect(result, isNotNull);
      expect(getCurrentPositionCalled, false);
      expect(result!.accuracy, 15.0);
    });

    test('falls back to getCurrentPosition when lastKnown is null', () async {
      final service = LocationService(
        isLocationServiceEnabled: () async => true,
        checkPermission: () async => LocationPermission.always,
        requestPermission: () async => LocationPermission.always,
        getLastKnownPosition: () async => null,
        getCurrentPosition:
            ({
              LocationAccuracy desiredAccuracy = LocationAccuracy.low,
              Duration? timeLimit,
            }) async => _makePosition(40.7128, -74.0060, accuracy: 20.0),
        reverseGeocode: (lat, lng) async => [
          _makePlacemark(locality: 'New York', administrativeArea: 'New York'),
        ],
      );

      final result = await service.getLocation();
      expect(result, isNotNull);
      expect(result!.latitude, 40.71);
      expect(result.longitude, -74.01);
      expect(result.accuracy, 20.0);
      expect(result.locationName, 'New York, New York');
    });

    test('rounds coordinates to 2 decimal places', () async {
      final service = LocationService(
        isLocationServiceEnabled: () async => true,
        checkPermission: () async => LocationPermission.always,
        requestPermission: () async => LocationPermission.always,
        getLastKnownPosition: () async =>
            _makePosition(39.73921234, -104.99034567),
        getCurrentPosition:
            ({
              LocationAccuracy desiredAccuracy = LocationAccuracy.low,
              Duration? timeLimit,
            }) async => _makePosition(39.73921234, -104.99034567),
        reverseGeocode: (lat, lng) async => [],
      );

      final result = await service.getLocation();
      expect(result, isNotNull);
      expect(result!.latitude, 39.74);
      expect(result.longitude, -104.99);
    });

    test(
      'returns null locationName when geocoding returns empty list',
      () async {
        final service = LocationService(
          isLocationServiceEnabled: () async => true,
          checkPermission: () async => LocationPermission.always,
          requestPermission: () async => LocationPermission.always,
          getLastKnownPosition: () async => _makePosition(39.74, -104.99),
          getCurrentPosition:
              ({
                LocationAccuracy desiredAccuracy = LocationAccuracy.low,
                Duration? timeLimit,
              }) async => _makePosition(39.74, -104.99),
          reverseGeocode: (lat, lng) async => [],
        );

        final result = await service.getLocation();
        expect(result, isNotNull);
        expect(result!.locationName, isNull);
      },
    );

    test('returns null locationName when geocoding throws', () async {
      final service = LocationService(
        isLocationServiceEnabled: () async => true,
        checkPermission: () async => LocationPermission.always,
        requestPermission: () async => LocationPermission.always,
        getLastKnownPosition: () async => _makePosition(39.74, -104.99),
        getCurrentPosition:
            ({
              LocationAccuracy desiredAccuracy = LocationAccuracy.low,
              Duration? timeLimit,
            }) async => _makePosition(39.74, -104.99),
        reverseGeocode: (lat, lng) async => throw Exception('Network error'),
      );

      final result = await service.getLocation();
      expect(result, isNotNull);
      expect(result!.locationName, isNull);
      // Coordinates should still be returned despite geocoding failure.
      expect(result.latitude, 39.74);
      expect(result.longitude, -104.99);
    });

    test(
      'returns null when getCurrentPosition throws (and no cached)',
      () async {
        final service = LocationService(
          isLocationServiceEnabled: () async => true,
          checkPermission: () async => LocationPermission.always,
          requestPermission: () async => LocationPermission.always,
          getLastKnownPosition: () async => null,
          getCurrentPosition:
              ({
                LocationAccuracy desiredAccuracy = LocationAccuracy.low,
                Duration? timeLimit,
              }) async => throw TimeoutException('GPS timeout'),
          reverseGeocode: (lat, lng) async => [],
        );

        final result = await service.getLocation();
        expect(result, isNull);
      },
    );

    test('never throws — returns null on any exception', () async {
      final service = LocationService(
        isLocationServiceEnabled: () async =>
            throw Exception('Service check failed'),
        checkPermission: () async => LocationPermission.always,
        requestPermission: () async => LocationPermission.always,
        getLastKnownPosition: () async => _makePosition(0, 0),
        getCurrentPosition:
            ({
              LocationAccuracy desiredAccuracy = LocationAccuracy.low,
              Duration? timeLimit,
            }) async => _makePosition(0, 0),
        reverseGeocode: (lat, lng) async => [],
      );

      // Should NOT throw — returns null per "never throws" contract.
      final result = await service.getLocation();
      expect(result, isNull);
    });

    test('never throws — returns null on Error (not just Exception)', () async {
      final service = LocationService(
        isLocationServiceEnabled: () async => throw StateError('binding error'),
        checkPermission: () async => LocationPermission.always,
        requestPermission: () async => LocationPermission.always,
        getLastKnownPosition: () async => _makePosition(0, 0),
        getCurrentPosition:
            ({
              LocationAccuracy desiredAccuracy = LocationAccuracy.low,
              Duration? timeLimit,
            }) async => _makePosition(0, 0),
        reverseGeocode: (lat, lng) async => [],
      );

      // The on Error catch clause handles non-Exception throwables.
      final result = await service.getLocation();
      expect(result, isNull);
    });
  });

  group('Reverse geocoding format', () {
    LocationService serviceWithPlacemark(geocoding.Placemark placemark) {
      return LocationService(
        isLocationServiceEnabled: () async => true,
        checkPermission: () async => LocationPermission.always,
        requestPermission: () async => LocationPermission.always,
        getLastKnownPosition: () async => _makePosition(39.74, -104.99),
        getCurrentPosition:
            ({
              LocationAccuracy desiredAccuracy = LocationAccuracy.low,
              Duration? timeLimit,
            }) async => _makePosition(39.74, -104.99),
        reverseGeocode: (lat, lng) async => [placemark],
      );
    }

    test('formats as "City, State" when both available', () async {
      final service = serviceWithPlacemark(
        _makePlacemark(
          locality: 'Denver',
          administrativeArea: 'Colorado',
          country: 'United States',
        ),
      );

      final result = await service.getLocation();
      expect(result!.locationName, 'Denver, Colorado');
    });

    test('formats as "City, Country" when no state', () async {
      final service = serviceWithPlacemark(
        _makePlacemark(locality: 'Paris', country: 'France'),
      );

      final result = await service.getLocation();
      expect(result!.locationName, 'Paris, France');
    });

    test('returns just city when no state or country', () async {
      final service = serviceWithPlacemark(_makePlacemark(locality: 'Tokyo'));

      final result = await service.getLocation();
      expect(result!.locationName, 'Tokyo');
    });

    test('falls back to state when no city', () async {
      final service = serviceWithPlacemark(
        _makePlacemark(administrativeArea: 'Colorado', country: 'US'),
      );

      final result = await service.getLocation();
      expect(result!.locationName, 'Colorado');
    });

    test('falls back to country when no city or state', () async {
      final service = serviceWithPlacemark(_makePlacemark(country: 'Japan'));

      final result = await service.getLocation();
      expect(result!.locationName, 'Japan');
    });

    test('returns null when all placemark fields are null', () async {
      final service = serviceWithPlacemark(_makePlacemark());

      final result = await service.getLocation();
      expect(result!.locationName, isNull);
    });

    test('returns null when placemark fields are empty strings', () async {
      final service = serviceWithPlacemark(
        _makePlacemark(locality: '', administrativeArea: '', country: ''),
      );

      final result = await service.getLocation();
      expect(result!.locationName, isNull);
    });

    test('returns null locationName when geocoding throws Error', () async {
      final service = LocationService(
        isLocationServiceEnabled: () async => true,
        checkPermission: () async => LocationPermission.always,
        requestPermission: () async => LocationPermission.always,
        getLastKnownPosition: () async => _makePosition(39.74, -104.99),
        getCurrentPosition:
            ({
              LocationAccuracy desiredAccuracy = LocationAccuracy.low,
              Duration? timeLimit,
            }) async => _makePosition(39.74, -104.99),
        reverseGeocode: (lat, lng) async => throw StateError('platform error'),
      );

      final result = await service.getLocation();
      expect(result, isNotNull);
      expect(result!.locationName, isNull);
      expect(result.latitude, 39.74);
    });
  });

  group('LocationResult', () {
    test('stores already-rounded coordinates', () {
      const result = LocationResult(
        latitude: 39.74,
        longitude: -104.99,
        accuracy: 10.0,
        locationName: 'Denver, Colorado',
      );

      expect(result.latitude, 39.74);
      expect(result.longitude, -104.99);
      expect(result.accuracy, 10.0);
      expect(result.locationName, 'Denver, Colorado');
    });

    test('locationName is optional', () {
      const result = LocationResult(
        latitude: 39.74,
        longitude: -104.99,
        accuracy: 10.0,
      );

      expect(result.locationName, isNull);
    });
  });

  group('LocationService.checkAndRequestPermission', () {
    test('returns granted when already whileInUse', () async {
      final service = LocationService(
        checkPermission: () async => LocationPermission.whileInUse,
        requestPermission: () async => LocationPermission.whileInUse,
        isLocationServiceEnabled: () async => true,
        getLastKnownPosition: () async => null,
        getCurrentPosition:
            ({desiredAccuracy = LocationAccuracy.low, timeLimit}) async =>
                _makePosition(0, 0),
        reverseGeocode: (lat, lng) async => [],
      );

      final result = await service.checkAndRequestPermission();
      expect(result, LocationPermission.whileInUse);
    });

    test('requests permission when denied and returns result', () async {
      final service = LocationService(
        checkPermission: () async => LocationPermission.denied,
        requestPermission: () async => LocationPermission.whileInUse,
        isLocationServiceEnabled: () async => true,
        getLastKnownPosition: () async => null,
        getCurrentPosition:
            ({desiredAccuracy = LocationAccuracy.low, timeLimit}) async =>
                _makePosition(0, 0),
        reverseGeocode: (lat, lng) async => [],
      );

      final result = await service.checkAndRequestPermission();
      expect(result, LocationPermission.whileInUse);
    });

    test('returns deniedForever when permanently denied', () async {
      final service = LocationService(
        checkPermission: () async => LocationPermission.deniedForever,
        requestPermission: () async => LocationPermission.deniedForever,
        isLocationServiceEnabled: () async => true,
        getLastKnownPosition: () async => null,
        getCurrentPosition:
            ({desiredAccuracy = LocationAccuracy.low, timeLimit}) async =>
                _makePosition(0, 0),
        reverseGeocode: (lat, lng) async => [],
      );

      final result = await service.checkAndRequestPermission();
      expect(result, LocationPermission.deniedForever);
    });

    test('returns denied when user dismisses request', () async {
      final service = LocationService(
        checkPermission: () async => LocationPermission.denied,
        requestPermission: () async => LocationPermission.denied,
        isLocationServiceEnabled: () async => true,
        getLastKnownPosition: () async => null,
        getCurrentPosition:
            ({desiredAccuracy = LocationAccuracy.low, timeLimit}) async =>
                _makePosition(0, 0),
        reverseGeocode: (lat, lng) async => [],
      );

      final result = await service.checkAndRequestPermission();
      expect(result, LocationPermission.denied);
    });
  });
}
