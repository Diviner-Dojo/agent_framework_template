import 'package:flutter_test/flutter_test.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:agentic_journal/services/google_auth_service.dart';

void main() {
  group('GoogleAuthService', () {
    test('signIn returns account on success', () async {
      final fakeAccount = _FakeGoogleSignInAccount();
      final service = GoogleAuthService(
        signIn: () async => fakeAccount,
        signOut: () async => null,
        disconnect: () async => null,
        isSignedIn: () async => true,
        getAuthClient: () async => null,
        signInSilently: () async => null,
      );

      final result = await service.signIn();
      expect(result, isNotNull);
    });

    test('signIn returns null when user cancels', () async {
      final service = GoogleAuthService(
        signIn: () async => null,
        signOut: () async => null,
        disconnect: () async => null,
        isSignedIn: () async => false,
        getAuthClient: () async => null,
        signInSilently: () async => null,
      );

      final result = await service.signIn();
      expect(result, isNull);
    });

    test('signIn throws GoogleAuthException on exception', () async {
      final service = GoogleAuthService(
        signIn: () async => throw Exception('network error'),
        signOut: () async => null,
        disconnect: () async => null,
        isSignedIn: () async => false,
        getAuthClient: () async => null,
        signInSilently: () async => null,
      );

      expect(() => service.signIn(), throwsA(isA<GoogleAuthException>()));
    });

    test('signOut completes without error', () async {
      var signOutCalled = false;
      final service = GoogleAuthService(
        signIn: () async => null,
        signOut: () async {
          signOutCalled = true;
          return null;
        },
        disconnect: () async => null,
        isSignedIn: () async => false,
        getAuthClient: () async => null,
        signInSilently: () async => null,
      );

      await service.signOut();
      expect(signOutCalled, isTrue);
    });

    test('signOut swallows exceptions (never throws)', () async {
      final service = GoogleAuthService(
        signIn: () async => null,
        signOut: () async => throw Exception('sign out failed'),
        disconnect: () async => null,
        isSignedIn: () async => false,
        getAuthClient: () async => null,
        signInSilently: () async => null,
      );

      // Should not throw.
      await service.signOut();
    });

    test('disconnect revokes tokens', () async {
      var disconnectCalled = false;
      final service = GoogleAuthService(
        signIn: () async => null,
        signOut: () async => null,
        disconnect: () async {
          disconnectCalled = true;
          return null;
        },
        isSignedIn: () async => false,
        getAuthClient: () async => null,
        signInSilently: () async => null,
      );

      await service.disconnect();
      expect(disconnectCalled, isTrue);
    });

    test('disconnect swallows exceptions (never throws)', () async {
      final service = GoogleAuthService(
        signIn: () async => null,
        signOut: () async => null,
        disconnect: () async => throw Exception('revoke failed'),
        isSignedIn: () async => false,
        getAuthClient: () async => null,
        signInSilently: () async => null,
      );

      await service.disconnect();
    });

    test('isSignedIn returns true when signed in', () async {
      final service = GoogleAuthService(
        signIn: () async => null,
        signOut: () async => null,
        disconnect: () async => null,
        isSignedIn: () async => true,
        getAuthClient: () async => null,
        signInSilently: () async => null,
      );

      final result = await service.isSignedIn();
      expect(result, isTrue);
    });

    test('isSignedIn returns false when not signed in', () async {
      final service = GoogleAuthService(
        signIn: () async => null,
        signOut: () async => null,
        disconnect: () async => null,
        isSignedIn: () async => false,
        getAuthClient: () async => null,
        signInSilently: () async => null,
      );

      final result = await service.isSignedIn();
      expect(result, isFalse);
    });

    test('isSignedIn returns false on exception', () async {
      final service = GoogleAuthService(
        signIn: () async => null,
        signOut: () async => null,
        disconnect: () async => null,
        isSignedIn: () async => throw Exception('check failed'),
        getAuthClient: () async => null,
        signInSilently: () async => null,
      );

      final result = await service.isSignedIn();
      expect(result, isFalse);
    });

    test('trySilentSignIn returns account when tokens valid', () async {
      final fakeAccount = _FakeGoogleSignInAccount();
      final service = GoogleAuthService(
        signIn: () async => null,
        signOut: () async => null,
        disconnect: () async => null,
        isSignedIn: () async => true,
        getAuthClient: () async => null,
        signInSilently: () async => fakeAccount,
      );

      final result = await service.trySilentSignIn();
      expect(result, isNotNull);
    });

    test('trySilentSignIn returns null when re-consent needed', () async {
      final service = GoogleAuthService(
        signIn: () async => null,
        signOut: () async => null,
        disconnect: () async => null,
        isSignedIn: () async => false,
        getAuthClient: () async => null,
        signInSilently: () async => null,
      );

      final result = await service.trySilentSignIn();
      expect(result, isNull);
    });

    test('trySilentSignIn returns null on exception', () async {
      final service = GoogleAuthService(
        signIn: () async => null,
        signOut: () async => null,
        disconnect: () async => null,
        isSignedIn: () async => false,
        getAuthClient: () async => null,
        signInSilently: () async => throw Exception('silent failed'),
      );

      final result = await service.trySilentSignIn();
      expect(result, isNull);
    });

    test('getAuthClient returns null when not signed in', () async {
      final service = GoogleAuthService(
        signIn: () async => null,
        signOut: () async => null,
        disconnect: () async => null,
        isSignedIn: () async => false,
        getAuthClient: () async => null,
        signInSilently: () async => null,
      );

      final result = await service.getAuthClient();
      expect(result, isNull);
    });

    test('getAuthClient returns null on exception', () async {
      final service = GoogleAuthService(
        signIn: () async => null,
        signOut: () async => null,
        disconnect: () async => null,
        isSignedIn: () async => false,
        getAuthClient: () async => throw Exception('auth failed'),
        signInSilently: () async => null,
      );

      final result = await service.getAuthClient();
      expect(result, isNull);
    });
  });
}

/// Minimal fake for GoogleSignInAccount (only used for null/non-null checks).
class _FakeGoogleSignInAccount implements GoogleSignInAccount {
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
