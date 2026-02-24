// ===========================================================================
// file: lib/services/location_service.dart
// purpose: GPS location acquisition and reverse geocoding with injectable
//          seams for testability.
//
// Pattern: Injectable callables (same approach as PhotoService(picker:)).
//   Production code uses the default geolocator/geocoding implementations.
//   Tests inject fake callables that simulate permission denial, timeout,
//   offline geocoding, etc. without touching platform channels.
//
// Privacy: Coordinates are rounded to 2 decimal places (~1.1km) before
//   being returned. This is a deliberate privacy tradeoff per ADR-0019.
//
// See: ADR-0019 (Location Tracking)
// ===========================================================================

import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:geolocator/geolocator.dart';
import 'package:geocoding/geocoding.dart' as geocoding;

/// Result of a successful location acquisition.
///
/// Coordinates are already reduced to 2 decimal places.
class LocationResult {
  /// Latitude in degrees, rounded to 2 decimal places (~1.1km).
  final double latitude;

  /// Longitude in degrees, rounded to 2 decimal places (~1.1km).
  final double longitude;

  /// GPS accuracy in meters (from the platform, not rounded).
  final double accuracy;

  /// Human-readable place name from reverse geocoding, or null if
  /// geocoding failed (offline, no result, exception).
  final String? locationName;

  const LocationResult({
    required this.latitude,
    required this.longitude,
    required this.accuracy,
    this.locationName,
  });
}

/// Callback type for getting the last known GPS position.
typedef GetLastKnownPosition = Future<Position?> Function();

/// Callback type for getting the current GPS position.
typedef GetCurrentPosition =
    Future<Position> Function({
      LocationAccuracy desiredAccuracy,
      Duration? timeLimit,
    });

/// Callback type for checking location permission.
typedef CheckPermission = Future<LocationPermission> Function();

/// Callback type for requesting location permission.
typedef RequestPermission = Future<LocationPermission> Function();

/// Callback type for checking if location services are enabled.
typedef IsLocationServiceEnabled = Future<bool> Function();

/// Callback type for reverse geocoding coordinates to a place name.
typedef ReverseGeocode =
    Future<List<geocoding.Placemark>> Function(
      double latitude,
      double longitude,
    );

/// GPS location acquisition and reverse geocoding service.
///
/// Uses injectable callables for all platform interactions so tests
/// can substitute fakes without touching platform channels.
///
/// Usage:
///   final service = LocationService(); // production defaults
///   final result = await service.getLocation();
///   if (result != null) {
///     // result.latitude, result.longitude are already rounded
///   }
class LocationService {
  final GetLastKnownPosition _getLastKnownPosition;
  final GetCurrentPosition _getCurrentPosition;
  final CheckPermission _checkPermission;
  final RequestPermission _requestPermission;
  final IsLocationServiceEnabled _isLocationServiceEnabled;
  final ReverseGeocode _reverseGeocode;

  /// Timeout for [getCurrentPosition] fallback.
  static const positionTimeout = Duration(seconds: 2);

  /// Create a LocationService with injectable callables.
  ///
  /// All parameters default to the real geolocator/geocoding implementations.
  /// Override in tests with fakes.
  LocationService({
    GetLastKnownPosition? getLastKnownPosition,
    GetCurrentPosition? getCurrentPosition,
    CheckPermission? checkPermission,
    RequestPermission? requestPermission,
    IsLocationServiceEnabled? isLocationServiceEnabled,
    ReverseGeocode? reverseGeocode,
  }) : _getLastKnownPosition =
           getLastKnownPosition ?? Geolocator.getLastKnownPosition,
       _getCurrentPosition = getCurrentPosition ?? _defaultGetCurrentPosition,
       _checkPermission = checkPermission ?? Geolocator.checkPermission,
       _requestPermission = requestPermission ?? Geolocator.requestPermission,
       _isLocationServiceEnabled =
           isLocationServiceEnabled ?? Geolocator.isLocationServiceEnabled,
       _reverseGeocode = reverseGeocode ?? geocoding.placemarkFromCoordinates;

  /// Check and request location permission, returning the resulting status.
  ///
  /// Returns the [LocationPermission] after checking (and optionally
  /// requesting). Use this to gate the location toggle in settings —
  /// the toggle should only enable if permission is granted.
  ///
  /// Returns [LocationPermission.deniedForever] if the user has permanently
  /// denied permission (the caller should direct them to app settings).
  Future<LocationPermission> checkAndRequestPermission() async {
    var permission = await _checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await _requestPermission();
    }
    return permission;
  }

  /// Get the current location with privacy-reduced precision.
  ///
  /// Returns null if:
  /// - Location services are disabled
  /// - Permission is denied (or denied forever)
  /// - Both getLastKnownPosition and getCurrentPosition fail/timeout
  ///
  /// Never throws — all exceptions are caught and result in null.
  /// This is the "never throws" contract specified in AC2.
  Future<LocationResult?> getLocation() async {
    try {
      // Check if location services are enabled.
      final serviceEnabled = await _isLocationServiceEnabled();
      if (!serviceEnabled) return null;

      // Check and request permission if needed.
      var permission = await _checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await _requestPermission();
        if (permission == LocationPermission.denied ||
            permission == LocationPermission.deniedForever) {
          return null;
        }
      }
      if (permission == LocationPermission.deniedForever) return null;

      // Try last known position first (returns immediately if cached).
      Position? position = await _getLastKnownPosition();

      // Fall back to current position with timeout.
      position ??= await _getCurrentPosition(
        desiredAccuracy: LocationAccuracy.low,
        timeLimit: positionTimeout,
      );

      // Round coordinates to 2 decimal places (ADR-0019 §2).
      final roundedLat = roundCoordinate(position.latitude);
      final roundedLng = roundCoordinate(position.longitude);

      // Attempt reverse geocoding (best-effort, null on failure).
      final locationName = await _reverseGeocodeSafe(roundedLat, roundedLng);

      return LocationResult(
        latitude: roundedLat,
        longitude: roundedLng,
        accuracy: position.accuracy,
        locationName: locationName,
      );
    } on Exception catch (e) {
      // Catch all exceptions (permission denied, timeout, etc.).
      if (kDebugMode) {
        debugPrint('LocationService.getLocation failed: $e');
      }
      return null;
    } on Error catch (e) {
      // Catch errors (FlutterError from missing bindings, etc.).
      if (kDebugMode) {
        debugPrint('LocationService.getLocation error: $e');
      }
      return null;
    }
  }

  /// Round a coordinate to 2 decimal places (~1.1km precision).
  ///
  /// This is a deliberate privacy tradeoff per ADR-0019 — not a display
  /// formatting choice. The reduced precision prevents pinpointing a
  /// home address or workplace from stored coordinates.
  ///
  /// Uses multiply-round-divide to avoid floating point string parsing.
  static double roundCoordinate(double value) {
    return (value * 100).roundToDouble() / 100;
  }

  /// Attempt reverse geocoding, returning null on any failure.
  ///
  /// Per ADR-0019 §7: if geocoding fails (offline, no result, exception),
  /// locationName stays null permanently for that session. No retry.
  Future<String?> _reverseGeocodeSafe(double latitude, double longitude) async {
    try {
      final placemarks = await _reverseGeocode(latitude, longitude);
      if (placemarks.isEmpty) return null;

      final place = placemarks.first;
      return _formatPlaceName(place);
    } on Exception {
      // Offline, network error, no result — null is a valid final state.
      return null;
    } on Error {
      // Platform binding errors — null is a valid final state.
      return null;
    }
  }

  /// Format a placemark into "City, State" or "City, Country".
  static String? _formatPlaceName(geocoding.Placemark place) {
    final city = place.locality;
    final state = place.administrativeArea;
    final country = place.country;

    if (city != null && city.isNotEmpty) {
      if (state != null && state.isNotEmpty) {
        return '$city, $state';
      }
      if (country != null && country.isNotEmpty) {
        return '$city, $country';
      }
      return city;
    }

    // No city — fall back to state or country.
    if (state != null && state.isNotEmpty) return state;
    if (country != null && country.isNotEmpty) return country;

    return null;
  }

  /// Default getCurrentPosition wrapper matching the callback signature.
  static Future<Position> _defaultGetCurrentPosition({
    LocationAccuracy desiredAccuracy = LocationAccuracy.low,
    Duration? timeLimit,
  }) {
    return Geolocator.getCurrentPosition(
      locationSettings: LocationSettings(accuracy: desiredAccuracy),
      timeLimit: timeLimit,
    );
  }
}
