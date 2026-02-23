// ===========================================================================
// file: test/services/audio_focus_service_test.dart
// purpose: Tests for AudioFocusService platform channel wrapper.
//
// Strategy:
//   Same pattern as assistant_registration_service_test.dart — mock the
//   MethodChannel and inject isAndroid: true to exercise channel calls.
//   Also test the focus event mapping from Android integer constants to
//   our AudioFocusEvent enum.
// ===========================================================================

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/services/audio_focus_service.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const channelName = 'com.divinerdojo.journal/audio';

  late AndroidAudioFocusService service;

  setUp(() {
    service = AndroidAudioFocusService(isAndroid: true);
  });

  tearDown(() {
    service.dispose();
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(const MethodChannel(channelName), null);
  });

  group('requestFocus', () {
    test('returns true when channel returns true', () async {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(const MethodChannel(channelName), (
            MethodCall methodCall,
          ) async {
            if (methodCall.method == 'requestAudioFocus') return true;
            return null;
          });

      final result = await service.requestFocus();
      expect(result, isTrue);
    });

    test('returns false when channel returns false', () async {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(const MethodChannel(channelName), (
            MethodCall methodCall,
          ) async {
            if (methodCall.method == 'requestAudioFocus') return false;
            return null;
          });

      final result = await service.requestFocus();
      expect(result, isFalse);
    });

    test('returns false on PlatformException', () async {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(const MethodChannel(channelName), (
            MethodCall methodCall,
          ) async {
            throw PlatformException(code: 'ERROR');
          });

      final result = await service.requestFocus();
      expect(result, isFalse);
    });

    test('returns true when isAndroid is false (no-op)', () async {
      final nonAndroidService = AndroidAudioFocusService(isAndroid: false);
      final result = await nonAndroidService.requestFocus();
      expect(result, isTrue);
      nonAndroidService.dispose();
    });
  });

  group('abandonFocus', () {
    test('calls channel method without error', () async {
      var wasCalled = false;
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(const MethodChannel(channelName), (
            MethodCall methodCall,
          ) async {
            if (methodCall.method == 'abandonAudioFocus') {
              wasCalled = true;
            }
            return null;
          });

      await service.abandonFocus();
      expect(wasCalled, isTrue);
    });

    test('does nothing when isAndroid is false', () async {
      var wasCalled = false;
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(const MethodChannel(channelName), (
            MethodCall methodCall,
          ) async {
            wasCalled = true;
            return null;
          });

      final nonAndroidService = AndroidAudioFocusService(isAndroid: false);
      await nonAndroidService.abandonFocus();
      expect(wasCalled, isFalse);
      nonAndroidService.dispose();
    });

    test('handles PlatformException silently', () async {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(const MethodChannel(channelName), (
            MethodCall methodCall,
          ) async {
            throw PlatformException(code: 'ERROR');
          });

      // Should not throw.
      await service.abandonFocus();
    });
  });

  group('onFocusChanged', () {
    test('emits gain event for focus change 1', () async {
      final events = <AudioFocusEvent>[];
      final sub = service.onFocusChanged.listen(events.add);

      // Simulate Kotlin sending a focus change event.
      await _simulateFocusChange(channelName, 1);
      await Future<void>.delayed(Duration.zero);

      expect(events, [AudioFocusEvent.gain]);
      await sub.cancel();
    });

    test('emits loss event for focus change -1', () async {
      final events = <AudioFocusEvent>[];
      final sub = service.onFocusChanged.listen(events.add);

      await _simulateFocusChange(channelName, -1);
      await Future<void>.delayed(Duration.zero);

      expect(events, [AudioFocusEvent.loss]);
      await sub.cancel();
    });

    test('emits lossTransient event for focus change -2', () async {
      final events = <AudioFocusEvent>[];
      final sub = service.onFocusChanged.listen(events.add);

      await _simulateFocusChange(channelName, -2);
      await Future<void>.delayed(Duration.zero);

      expect(events, [AudioFocusEvent.lossTransient]);
      await sub.cancel();
    });

    test('emits lossTransientCanDuck event for focus change -3', () async {
      final events = <AudioFocusEvent>[];
      final sub = service.onFocusChanged.listen(events.add);

      await _simulateFocusChange(channelName, -3);
      await Future<void>.delayed(Duration.zero);

      expect(events, [AudioFocusEvent.lossTransientCanDuck]);
      await sub.cancel();
    });

    test('ignores unknown focus change values', () async {
      final events = <AudioFocusEvent>[];
      final sub = service.onFocusChanged.listen(events.add);

      await _simulateFocusChange(channelName, 42);
      await Future<void>.delayed(Duration.zero);

      expect(events, isEmpty);
      await sub.cancel();
    });
  });

  group('AudioFocusEvent', () {
    test('has all expected values', () {
      expect(
        AudioFocusEvent.values,
        containsAll([
          AudioFocusEvent.gain,
          AudioFocusEvent.loss,
          AudioFocusEvent.lossTransient,
          AudioFocusEvent.lossTransientCanDuck,
        ]),
      );
    });
  });
}

/// Simulate the Kotlin side invoking 'onAudioFocusChange' on the channel.
Future<void> _simulateFocusChange(String channelName, int focusChange) async {
  // The service registers a method call handler on the channel.
  // To simulate an incoming call from Kotlin, we use the codec to encode
  // a method call and send it to the handler.
  final codec = const StandardMethodCodec();
  final data = codec.encodeMethodCall(
    MethodCall('onAudioFocusChange', focusChange),
  );
  await TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .handlePlatformMessage(channelName, data, (_) {});
}
