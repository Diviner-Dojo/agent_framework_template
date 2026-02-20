// ===========================================================================
// file: lib/services/assistant_registration_service.dart
// purpose: Platform channel wrapper for Android assistant registration.
//
// Platform Channels (for the Python developer):
//   This is the Dart side of a Kotlin<->Dart bridge. When you call
//   _channel.invokeMethod('isDefaultAssistant'), Flutter sends a message
//   to the Kotlin code in MainActivity.kt, which calls Android APIs and
//   returns the result. On iOS, these methods will throw PlatformException
//   (no iOS assistant concept), so we catch and return safe defaults.
//
// Why a Service class (not a repository)?
//   Services wrap external platform APIs. Repositories wrap data storage.
//   This class wraps Android's RoleManager API via a platform channel —
//   it's a platform service, not a data repository.
//
// Testability:
//   The [isAndroid] and [channel] parameters are injectable so that tests
//   can bypass the Platform.isAndroid guard and mock the channel. In
//   production, the defaults are used (Platform.isAndroid and the real
//   channel).
// ===========================================================================

import 'dart:io' show Platform;

import 'package:flutter/services.dart';

/// Provides access to Android's default assistant registration system.
///
/// On Android: checks if this app is the default assistant and opens
/// the system settings where the user can change it.
/// On iOS: all methods return safe defaults (no assistant concept on iOS).
///
/// Constructor parameters [isAndroid] and [channel] are injectable for
/// testing — in production, use the default constructor.
class AssistantRegistrationService {
  final MethodChannel _channel;
  final bool _isAndroid;

  /// Creates the service.
  ///
  /// [channel] defaults to the production channel. Override in tests to use
  /// a mock channel via TestDefaultBinaryMessengerBinding.
  /// [isAndroid] defaults to Platform.isAndroid. Set to `true` in tests
  /// to exercise the channel code path.
  AssistantRegistrationService({MethodChannel? channel, bool? isAndroid})
    : _channel =
          channel ?? const MethodChannel('com.divinerdojo.journal/assistant'),
      _isAndroid = isAndroid ?? Platform.isAndroid;

  /// Check if this app is currently set as the default digital assistant.
  ///
  /// Returns `true` only on Android 10+ when the app holds ROLE_ASSISTANT.
  /// Returns `false` on iOS, older Android, or if the check fails.
  Future<bool> isDefaultAssistant() async {
    if (!_isAndroid) return false;
    try {
      final result = await _channel.invokeMethod<bool>('isDefaultAssistant');
      return result ?? false;
    } on PlatformException {
      return false;
    }
  }

  /// Open the system settings screen where the user can set the default
  /// digital assistant app.
  ///
  /// On Android 10+: opens Default Apps settings.
  /// On older Android: opens Voice Input settings.
  /// On iOS: no-op.
  Future<void> openAssistantSettings() async {
    if (!_isAndroid) return;
    try {
      await _channel.invokeMethod<void>('openAssistantSettings');
    } on PlatformException {
      // If we can't open assistant settings, fail silently.
      // The UI already shows manual instructions as a fallback.
    }
  }

  /// Check if the app was launched via the assistant gesture (long-press Home).
  ///
  /// Returns `true` exactly once after an assistant-gesture launch, then
  /// the Kotlin side clears the flag. This prevents re-triggering on hot
  /// reload or navigation rebuilds.
  ///
  /// Returns `false` on iOS or if the check fails.
  Future<bool> wasLaunchedAsAssistant() async {
    if (!_isAndroid) return false;
    try {
      final result = await _channel.invokeMethod<bool>(
        'wasLaunchedAsAssistant',
      );
      return result ?? false;
    } on PlatformException {
      return false;
    }
  }
}
