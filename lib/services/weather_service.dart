// ===========================================================================
// file: lib/services/weather_service.dart
// purpose: Fetch current weather from Open-Meteo API using known coordinates.
//
// Design:
//   Open-Meteo is free, no API key required, and GDPR-compliant. The API
//   returns WMO weather interpretation codes (weatherCode) alongside
//   temperature. This file maps those codes to human-readable labels.
//
//   The service follows the same injectable-callable pattern as LocationService:
//   production uses the real dio client; tests inject a fake fetcher.
//
//   Never throws — all failures return null. Session start is never blocked.
//
// Privacy: Only the already-rounded coordinates (2 d.p.) are sent. No
//   session ID or user identifier is included in the API request.
//
// See: SPEC-20260302 Phase 4C, ADR-0019 (coordinates are already rounded)
// ===========================================================================

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

/// Result of a successful weather fetch.
class WeatherResult {
  /// Temperature in degrees Celsius at the time of the API call.
  final double temperatureCelsius;

  /// WMO weather interpretation code (0 = clear sky, 95 = thunderstorm, etc.).
  final int weatherCode;

  /// Human-readable label derived from [weatherCode], e.g. "Partly cloudy".
  final String description;

  const WeatherResult({
    required this.temperatureCelsius,
    required this.weatherCode,
    required this.description,
  });
}

/// Callback type for making the Open-Meteo HTTP request.
///
/// Accepts the URL string and returns the parsed response body map.
/// Injected in tests to avoid real network calls.
typedef FetchWeather = Future<Map<String, dynamic>> Function(String url);

/// Fetches current weather conditions from Open-Meteo using GPS coordinates.
///
/// Follows the LocationService injectable-callable pattern for testability.
///
/// Usage:
///   final service = WeatherService();
///   final result = await service.getWeather(latitude: 37.77, longitude: -122.42);
///   if (result != null) {
///     print('${result.temperatureCelsius}°C — ${result.description}');
///   }
class WeatherService {
  final FetchWeather _fetch;

  /// Open-Meteo base URL.
  static const _baseUrl = 'https://api.open-meteo.com/v1/forecast';

  /// Timeout for the weather API call.
  static const _timeout = Duration(seconds: 5);

  /// Creates a WeatherService with an injectable fetch callback.
  ///
  /// Defaults to the real dio HTTP client. Override in tests.
  WeatherService({FetchWeather? fetch}) : _fetch = fetch ?? _defaultFetch;

  /// Fetch current weather at [latitude]/[longitude].
  ///
  /// Returns null if:
  /// - The network request fails or times out
  /// - The response is missing expected fields
  /// - Any exception is thrown during parsing
  ///
  /// Coordinates should already be privacy-reduced (2 d.p.) per ADR-0019.
  Future<WeatherResult?> getWeather({
    required double latitude,
    required double longitude,
  }) async {
    try {
      final url =
          '$_baseUrl'
          '?latitude=$latitude'
          '&longitude=$longitude'
          '&current=temperature_2m,weather_code';

      final body = await _fetch(url);

      final current = body['current'] as Map<String, dynamic>?;
      if (current == null) return null;

      final temp = (current['temperature_2m'] as num?)?.toDouble();
      final code = (current['weather_code'] as num?)?.toInt();
      if (temp == null || code == null) return null;

      return WeatherResult(
        temperatureCelsius: temp,
        weatherCode: code,
        description: describeWeatherCode(code),
      );
    } on Exception catch (e) {
      if (kDebugMode) {
        debugPrint('WeatherService.getWeather failed: $e');
      }
      return null;
    } on Error catch (e) {
      if (kDebugMode) {
        debugPrint('WeatherService.getWeather error: $e');
      }
      return null;
    }
  }

  /// Default HTTP fetch using dio.
  static Future<Map<String, dynamic>> _defaultFetch(String url) async {
    final dio = Dio();
    final response = await dio.get<Map<String, dynamic>>(
      url,
      options: Options(
        // Both timeouts required: connectTimeout caps the TCP handshake;
        // receiveTimeout caps the response body download after connection.
        // Without connectTimeout, a captive portal or stalled TCP can
        // hold the connection phase for the OS default (~75s on Android).
        connectTimeout: WeatherService._timeout,
        receiveTimeout: WeatherService._timeout,
      ),
    );
    if (response.data == null) throw StateError('Empty response from $url');
    return response.data!;
  }

  /// Map a WMO weather interpretation code to a human-readable label.
  ///
  /// Based on the WMO 306 Manual — Part I, Table 4677.
  /// Codes not in this list return 'Unknown'.
  static String describeWeatherCode(int code) {
    return switch (code) {
      0 => 'Clear sky',
      1 => 'Mainly clear',
      2 => 'Partly cloudy',
      3 => 'Overcast',
      45 || 48 => 'Foggy',
      51 || 53 || 55 => 'Drizzle',
      56 || 57 => 'Freezing drizzle',
      61 || 63 || 65 => 'Rain',
      66 || 67 => 'Freezing rain',
      71 || 73 || 75 => 'Snowfall',
      77 => 'Snow grains',
      80 || 81 || 82 => 'Rain showers',
      85 || 86 => 'Snow showers',
      95 => 'Thunderstorm',
      96 || 99 => 'Thunderstorm with hail',
      _ => 'Unknown',
    };
  }
}
