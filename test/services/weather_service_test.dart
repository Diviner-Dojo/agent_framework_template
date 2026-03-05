// ===========================================================================
// file: test/services/weather_service_test.dart
// purpose: Unit tests for WeatherService (Phase 4C — passive weather metadata).
//
// Tests verify:
//   - Happy-path: valid Open-Meteo response parses into WeatherResult
//   - Null return on network exception
//   - Null return on missing 'current' field
//   - Null return on missing temperature_2m field
//   - Null return on missing weather_code field
//   - describeWeatherCode() coverage (all bucket boundaries)
// ===========================================================================

import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/services/weather_service.dart';

void main() {
  group('WeatherService', () {
    test('returns WeatherResult on valid response', () async {
      final service = WeatherService(
        fetch: (_) async => {
          'current': {'temperature_2m': 18.5, 'weather_code': 2},
        },
      );

      final result = await service.getWeather(
        latitude: 37.77,
        longitude: -122.42,
      );

      expect(result, isNotNull);
      expect(result!.temperatureCelsius, equals(18.5));
      expect(result.weatherCode, equals(2));
      expect(result.description, equals('Partly cloudy'));
    });

    test('returns null when fetch throws', () async {
      final service = WeatherService(
        fetch: (_) async => throw Exception('network error'),
      );

      final result = await service.getWeather(
        latitude: 37.77,
        longitude: -122.42,
      );

      expect(result, isNull);
    });

    test('returns null when current field is missing', () async {
      final service = WeatherService(fetch: (_) async => {'latitude': 37.77});

      final result = await service.getWeather(
        latitude: 37.77,
        longitude: -122.42,
      );

      expect(result, isNull);
    });

    test('returns null when temperature_2m is missing', () async {
      final service = WeatherService(
        fetch: (_) async => {
          'current': {'weather_code': 1},
        },
      );

      final result = await service.getWeather(
        latitude: 37.77,
        longitude: -122.42,
      );

      expect(result, isNull);
    });

    test('returns null when weather_code is missing', () async {
      final service = WeatherService(
        fetch: (_) async => {
          'current': {'temperature_2m': 22.0},
        },
      );

      final result = await service.getWeather(
        latitude: 37.77,
        longitude: -122.42,
      );

      expect(result, isNull);
    });

    test('URL includes latitude and longitude', () async {
      String? capturedUrl;
      final service = WeatherService(
        fetch: (url) async {
          capturedUrl = url;
          return {
            'current': {'temperature_2m': 10.0, 'weather_code': 0},
          };
        },
      );

      await service.getWeather(latitude: 51.50, longitude: -0.12);

      expect(capturedUrl, contains('latitude=51.5'));
      expect(capturedUrl, contains('longitude=-0.12'));
      expect(capturedUrl, contains('current=temperature_2m,weather_code'));
    });
  });

  group('WeatherService.describeWeatherCode', () {
    test('clear sky', () {
      expect(WeatherService.describeWeatherCode(0), equals('Clear sky'));
    });

    test('mainly clear', () {
      expect(WeatherService.describeWeatherCode(1), equals('Mainly clear'));
    });

    test('partly cloudy', () {
      expect(WeatherService.describeWeatherCode(2), equals('Partly cloudy'));
    });

    test('overcast', () {
      expect(WeatherService.describeWeatherCode(3), equals('Overcast'));
    });

    test('fog (45 and 48)', () {
      expect(WeatherService.describeWeatherCode(45), equals('Foggy'));
      expect(WeatherService.describeWeatherCode(48), equals('Foggy'));
    });

    test('drizzle (51, 53, 55)', () {
      for (final code in [51, 53, 55]) {
        expect(
          WeatherService.describeWeatherCode(code),
          equals('Drizzle'),
          reason: 'code $code',
        );
      }
    });

    test('rain (61, 63, 65)', () {
      for (final code in [61, 63, 65]) {
        expect(
          WeatherService.describeWeatherCode(code),
          equals('Rain'),
          reason: 'code $code',
        );
      }
    });

    test('snowfall (71, 73, 75)', () {
      for (final code in [71, 73, 75]) {
        expect(
          WeatherService.describeWeatherCode(code),
          equals('Snowfall'),
          reason: 'code $code',
        );
      }
    });

    test('rain showers (80, 81, 82)', () {
      for (final code in [80, 81, 82]) {
        expect(
          WeatherService.describeWeatherCode(code),
          equals('Rain showers'),
          reason: 'code $code',
        );
      }
    });

    test('thunderstorm (95)', () {
      expect(WeatherService.describeWeatherCode(95), equals('Thunderstorm'));
    });

    test('thunderstorm with hail (96, 99)', () {
      expect(
        WeatherService.describeWeatherCode(96),
        equals('Thunderstorm with hail'),
      );
      expect(
        WeatherService.describeWeatherCode(99),
        equals('Thunderstorm with hail'),
      );
    });

    test('unknown code returns Unknown', () {
      expect(WeatherService.describeWeatherCode(999), equals('Unknown'));
    });
  });
}
