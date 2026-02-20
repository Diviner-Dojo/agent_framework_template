// ===========================================================================
// file: test/services/assistant_registration_service_test.dart
// purpose: Tests for the AssistantRegistrationService platform channel wrapper.
//
// Testability approach:
//   Platform.isAndroid is always false in flutter test (runs on host machine).
//   The service accepts an injectable [isAndroid] parameter so we can
//   set it to true in tests and exercise the channel code path.
//   The MethodChannel is mocked via TestDefaultBinaryMessengerBinding.
// ===========================================================================

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/services/assistant_registration_service.dart';

void main() {
  // Initialize the binding so TestDefaultBinaryMessengerBinding.instance works.
  TestWidgetsFlutterBinding.ensureInitialized();

  // The channel name must match what the service uses.
  const channelName = 'com.divinerdojo.journal/assistant';

  late AssistantRegistrationService service;

  setUp(() {
    // Create the service with isAndroid: true to bypass the Platform guard.
    service = AssistantRegistrationService(isAndroid: true);
  });

  tearDown(() {
    // Clear any mock handlers after each test.
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(const MethodChannel(channelName), null);
  });

  group('isDefaultAssistant', () {
    test('returns true when channel returns true', () async {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(const MethodChannel(channelName), (
            MethodCall methodCall,
          ) async {
            if (methodCall.method == 'isDefaultAssistant') return true;
            return null;
          });

      final result = await service.isDefaultAssistant();
      expect(result, isTrue);
    });

    test('returns false when channel returns false', () async {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(const MethodChannel(channelName), (
            MethodCall methodCall,
          ) async {
            if (methodCall.method == 'isDefaultAssistant') return false;
            return null;
          });

      final result = await service.isDefaultAssistant();
      expect(result, isFalse);
    });

    test('returns false on PlatformException', () async {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(const MethodChannel(channelName), (
            MethodCall methodCall,
          ) async {
            throw PlatformException(code: 'ERROR', message: 'test error');
          });

      final result = await service.isDefaultAssistant();
      expect(result, isFalse);
    });

    test('returns false when isAndroid is false (iOS path)', () async {
      // Create a service with isAndroid: false to test the iOS no-op path.
      final iosService = AssistantRegistrationService(isAndroid: false);
      final result = await iosService.isDefaultAssistant();
      expect(result, isFalse);
    });
  });

  group('openAssistantSettings', () {
    test('calls the channel method without error', () async {
      var wasCalled = false;
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(const MethodChannel(channelName), (
            MethodCall methodCall,
          ) async {
            if (methodCall.method == 'openAssistantSettings') {
              wasCalled = true;
            }
            return null;
          });

      await service.openAssistantSettings();
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

      final iosService = AssistantRegistrationService(isAndroid: false);
      await iosService.openAssistantSettings();
      expect(wasCalled, isFalse);
    });

    test('handles PlatformException silently', () async {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(const MethodChannel(channelName), (
            MethodCall methodCall,
          ) async {
            throw PlatformException(code: 'ERROR');
          });

      // Should not throw.
      await service.openAssistantSettings();
    });
  });

  group('wasLaunchedAsAssistant', () {
    test('returns true when channel returns true', () async {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(const MethodChannel(channelName), (
            MethodCall methodCall,
          ) async {
            if (methodCall.method == 'wasLaunchedAsAssistant') return true;
            return null;
          });

      final result = await service.wasLaunchedAsAssistant();
      expect(result, isTrue);
    });

    test('returns false when channel returns false', () async {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(const MethodChannel(channelName), (
            MethodCall methodCall,
          ) async {
            if (methodCall.method == 'wasLaunchedAsAssistant') return false;
            return null;
          });

      final result = await service.wasLaunchedAsAssistant();
      expect(result, isFalse);
    });

    test('returns false on PlatformException', () async {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(const MethodChannel(channelName), (
            MethodCall methodCall,
          ) async {
            throw PlatformException(code: 'ERROR');
          });

      final result = await service.wasLaunchedAsAssistant();
      expect(result, isFalse);
    });

    test('returns false when isAndroid is false', () async {
      final iosService = AssistantRegistrationService(isAndroid: false);
      final result = await iosService.wasLaunchedAsAssistant();
      expect(result, isFalse);
    });
  });
}
