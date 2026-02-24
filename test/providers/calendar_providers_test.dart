import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:agentic_journal/providers/calendar_providers.dart';
import 'package:agentic_journal/services/google_auth_service.dart';
import 'package:google_sign_in/google_sign_in.dart';

void main() {
  group('GoogleConnectionNotifier', () {
    test('starts as false (not connected)', () {
      final service = _fakeAuthService();
      final notifier = GoogleConnectionNotifier(service);
      expect(notifier.state, isFalse);
    });

    test('connect() sets state to true on success', () async {
      final service = _fakeAuthService(signIn: () async => _FakeAccount());
      final notifier = GoogleConnectionNotifier(service);

      final result = await notifier.connect();
      expect(result, isTrue);
      expect(notifier.state, isTrue);
    });

    test('connect() stays false when user cancels', () async {
      final service = _fakeAuthService(signIn: () async => null);
      final notifier = GoogleConnectionNotifier(service);

      final result = await notifier.connect();
      expect(result, isFalse);
      expect(notifier.state, isFalse);
    });

    test('disconnect() sets state to false', () async {
      var disconnectCalled = false;
      final service = _fakeAuthService(
        signIn: () async => _FakeAccount(),
        disconnect: () async {
          disconnectCalled = true;
          return null;
        },
      );
      final notifier = GoogleConnectionNotifier(service);

      // Connect first.
      await notifier.connect();
      expect(notifier.state, isTrue);

      // Disconnect.
      await notifier.disconnect();
      expect(notifier.state, isFalse);
      expect(disconnectCalled, isTrue);
    });
  });

  group('CalendarAutoSuggestNotifier', () {
    test('defaults to true', () async {
      SharedPreferences.setMockInitialValues({});
      final notifier = CalendarAutoSuggestNotifier();
      // State is set asynchronously in constructor, check after pump.
      await Future<void>.delayed(Duration.zero);
      expect(notifier.state, isTrue);
    });

    test('persists preference to SharedPreferences', () async {
      SharedPreferences.setMockInitialValues({});
      final notifier = CalendarAutoSuggestNotifier();
      await Future<void>.delayed(Duration.zero);

      await notifier.setEnabled(false);
      expect(notifier.state, isFalse);

      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getBool('calendar_auto_suggest'), isFalse);
    });

    test('reads persisted preference on creation', () async {
      SharedPreferences.setMockInitialValues({'calendar_auto_suggest': false});
      final notifier = CalendarAutoSuggestNotifier();
      await Future<void>.delayed(Duration.zero);
      expect(notifier.state, isFalse);
    });
  });

  group('CalendarConfirmationNotifier', () {
    test('defaults to true (always confirm)', () async {
      SharedPreferences.setMockInitialValues({});
      final notifier = CalendarConfirmationNotifier();
      await Future<void>.delayed(Duration.zero);
      expect(notifier.state, isTrue);
    });

    test('persists preference to SharedPreferences', () async {
      SharedPreferences.setMockInitialValues({});
      final notifier = CalendarConfirmationNotifier();
      await Future<void>.delayed(Duration.zero);

      await notifier.setEnabled(false);
      expect(notifier.state, isFalse);

      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getBool('calendar_require_confirmation'), isFalse);
    });
  });

  group('calendar providers', () {
    test('googleAuthServiceProvider provides GoogleAuthService', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      final service = container.read(googleAuthServiceProvider);
      expect(service, isA<GoogleAuthService>());
    });

    test('isGoogleConnectedProvider starts as false', () {
      final container = ProviderContainer(
        overrides: [
          googleAuthServiceProvider.overrideWithValue(_fakeAuthService()),
        ],
      );
      addTearDown(container.dispose);

      final connected = container.read(isGoogleConnectedProvider);
      expect(connected, isFalse);
    });
  });
}

GoogleAuthService _fakeAuthService({
  GoogleSignInFn? signIn,
  GoogleSignOutFn? signOut,
  GoogleDisconnectFn? disconnect,
  GoogleIsSignedInFn? isSignedIn,
}) {
  return GoogleAuthService(
    signIn: signIn ?? () async => null,
    signOut: signOut ?? () async => null,
    disconnect: disconnect ?? () async => null,
    isSignedIn: isSignedIn ?? () async => false,
    getAuthClient: () async => null,
    signInSilently: () async => null,
  );
}

class _FakeAccount implements GoogleSignInAccount {
  @override
  String get displayName => 'Test User';
  @override
  String get email => 'test@example.com';
  @override
  String get id => 'test-id';
  @override
  String? get photoUrl => null;
  @override
  String? get serverAuthCode => null;
  @override
  Future<GoogleSignInAuthentication> get authentication =>
      throw UnimplementedError();
  @override
  Future<Map<String, String>> get authHeaders => throw UnimplementedError();
  @override
  Future<void> clearAuthCache() => Future.value();
}
