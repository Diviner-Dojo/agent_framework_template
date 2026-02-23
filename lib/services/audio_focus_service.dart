// ===========================================================================
// file: lib/services/audio_focus_service.dart
// purpose: Platform channel wrapper for Android audio focus management.
//
// Architecture (ADR-0015):
//   Audio focus management tells Android that our app is using audio,
//   allowing the system to coordinate with other audio apps (music players,
//   phone calls, navigation). Without it, multiple apps may try to use
//   the microphone simultaneously, or our STT may run during a phone call.
//
// Platform Channel Pattern:
//   Follows the same pattern as AssistantRegistrationService —
//   injectable MethodChannel and isAndroid flag for testing.
//   Events FROM Kotlin are received via setMethodCallHandler on
//   an EventChannel-like pattern using the same MethodChannel.
//
// See: ADR-0015 (Voice Mode Architecture)
// ===========================================================================

import 'dart:async';
import 'dart:io' show Platform;

import 'package:flutter/services.dart';

/// Audio focus change events from the Android AudioManager.
enum AudioFocusEvent {
  /// Full audio focus gained — resume recording and TTS.
  gain,

  /// Audio focus lost permanently (e.g., user started music player).
  /// Pause recording and abandon focus.
  loss,

  /// Audio focus lost temporarily (e.g., notification sound).
  /// Pause recording; will regain shortly.
  lossTransient,

  /// Audio focus lost but we can "duck" (lower volume).
  /// Continue STT, reduce TTS volume.
  lossTransientCanDuck,
}

/// Abstract interface for audio focus management.
///
/// Implementations handle platform-specific audio focus requests and
/// events. On Android, this wraps AudioManager. On iOS, this would
/// wrap AVAudioSession (not yet implemented).
abstract class AudioFocusService {
  /// Request audio focus for recording.
  ///
  /// Returns true if focus was granted, false if another app has priority.
  Future<bool> requestFocus();

  /// Abandon audio focus when recording is done.
  Future<void> abandonFocus();

  /// Stream of audio focus change events.
  ///
  /// Listen to this stream to pause/resume recording when other apps
  /// (phone calls, music, navigation) take audio focus.
  Stream<AudioFocusEvent> get onFocusChanged;

  /// Release resources.
  void dispose();
}

/// Android implementation of [AudioFocusService] via MethodChannel.
///
/// Communicates with Kotlin code in MainActivity.kt to request/abandon
/// audio focus via Android's AudioManager API.
class AndroidAudioFocusService implements AudioFocusService {
  final MethodChannel _channel;
  final bool _isAndroid;
  final StreamController<AudioFocusEvent> _focusController =
      StreamController<AudioFocusEvent>.broadcast();

  /// Creates the audio focus service.
  ///
  /// [channel] defaults to the production channel. Override in tests.
  /// [isAndroid] defaults to Platform.isAndroid. Set to `true` in tests.
  AndroidAudioFocusService({MethodChannel? channel, bool? isAndroid})
    : _channel =
          channel ?? const MethodChannel('com.divinerdojo.journal/audio'),
      _isAndroid = isAndroid ?? Platform.isAndroid {
    // Listen for focus change events from Kotlin.
    _channel.setMethodCallHandler(_handlePlatformCall);
  }

  /// Handle incoming method calls from the Kotlin side.
  Future<dynamic> _handlePlatformCall(MethodCall call) async {
    if (call.method == 'onAudioFocusChange') {
      final focusChange = call.arguments as int;
      final event = _mapFocusChange(focusChange);
      if (event != null) {
        _focusController.add(event);
      }
    }
  }

  /// Map Android AudioManager focus change constants to our enum.
  AudioFocusEvent? _mapFocusChange(int focusChange) {
    // Android AudioManager constants:
    // AUDIOFOCUS_GAIN = 1
    // AUDIOFOCUS_LOSS = -1
    // AUDIOFOCUS_LOSS_TRANSIENT = -2
    // AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK = -3
    return switch (focusChange) {
      1 => AudioFocusEvent.gain,
      -1 => AudioFocusEvent.loss,
      -2 => AudioFocusEvent.lossTransient,
      -3 => AudioFocusEvent.lossTransientCanDuck,
      _ => null,
    };
  }

  @override
  Future<bool> requestFocus() async {
    if (!_isAndroid) return true; // No-op on non-Android.
    try {
      final result = await _channel.invokeMethod<bool>('requestAudioFocus');
      return result ?? false;
    } on PlatformException {
      return false;
    }
  }

  @override
  Future<void> abandonFocus() async {
    if (!_isAndroid) return;
    try {
      await _channel.invokeMethod<void>('abandonAudioFocus');
    } on PlatformException {
      // Best-effort — failing to abandon focus is not critical.
    }
  }

  @override
  Stream<AudioFocusEvent> get onFocusChanged => _focusController.stream;

  @override
  void dispose() {
    _focusController.close();
    // Remove the method call handler.
    _channel.setMethodCallHandler(null);
  }
}
