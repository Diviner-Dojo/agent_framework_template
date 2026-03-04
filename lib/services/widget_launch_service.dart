// ===========================================================================
// file: lib/services/widget_launch_service.dart
// purpose: Reads the Quick Capture widget launch mode from the Android
//          platform channel (Phase 4B).
//
// Pattern: Same single-method service as AssistantRegistrationService.
//   Production uses the real MethodChannel. Tests inject a fake getter.
//
// The flag is cleared by Kotlin after the first Flutter read, so calling
// getWidgetLaunchMode() more than once in the same cold start returns null
// on the second call. The check is guarded in app.dart by a bool flag.
// ===========================================================================

import 'package:flutter/services.dart';

/// Callback type for the platform channel call.
///
/// Injected in tests to avoid real MethodChannel invocation.
typedef GetWidgetLaunchMode = Future<String?> Function();

/// Reads the quick capture mode sent by the Android home screen widget.
///
/// The Kotlin side writes the mode to the "com.divinerdojo.journal/widget"
/// channel when MainActivity receives the widget launch Intent. After Flutter
/// reads it, the flag is cleared — subsequent calls return null.
class WidgetLaunchService {
  final GetWidgetLaunchMode _get;

  static const _channel = MethodChannel('com.divinerdojo.journal/widget');

  WidgetLaunchService({GetWidgetLaunchMode? get}) : _get = get ?? _defaultGet;

  /// Returns the capture mode string from the widget launch, or null.
  ///
  /// Returns null on iOS (no widget) or if the app was not launched from
  /// the Quick Capture widget (normal launch or assistant launch).
  Future<String?> getWidgetLaunchMode() async {
    try {
      return await _get();
    } on PlatformException {
      return null;
    }
  }

  static Future<String?> _defaultGet() async {
    return _channel.invokeMethod<String>('getWidgetLaunchMode');
  }
}
