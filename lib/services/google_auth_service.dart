// ===========================================================================
// file: lib/services/google_auth_service.dart
// purpose: Google OAuth2 sign-in for Calendar API access.
//
// Pattern: Injectable callables (same approach as LocationService,
//   PhotoService). Production code uses the default google_sign_in
//   implementation. Tests inject fakes without touching platform channels.
//
// Token storage: OAuth tokens are managed by the google_sign_in SDK,
//   which stores them in flutter_secure_storage (Android Keystore-backed
//   on non-rooted devices). Per ADR-0020 §6, tokens are never stored in
//   SharedPreferences or SQLite.
//
// Scope: calendar.events (create/edit events). Google does not offer a
//   narrower scope for create-only access. The app only calls
//   events.insert() — never update, delete, or list (ADR-0020 §2).
//
// See: ADR-0020 (Google Calendar Integration)
// ===========================================================================

import 'package:flutter/foundation.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:extension_google_sign_in_as_googleapis_auth/extension_google_sign_in_as_googleapis_auth.dart';
import 'package:googleapis_auth/googleapis_auth.dart' as googleapis_auth;

/// Callback type for signing in with Google.
typedef GoogleSignInFn = Future<GoogleSignInAccount?> Function();

/// Callback type for signing out of Google.
typedef GoogleSignOutFn = Future<GoogleSignInAccount?> Function();

/// Callback type for disconnecting (revoking tokens).
typedef GoogleDisconnectFn = Future<GoogleSignInAccount?> Function();

/// Callback type for checking if already signed in.
typedef GoogleIsSignedInFn = Future<bool> Function();

/// Callback type for getting the authenticated HTTP client.
typedef GoogleAuthClientFn = Future<googleapis_auth.AuthClient?> Function();

/// Callback type for silently refreshing the sign-in.
typedef GoogleSignInSilentlyFn = Future<GoogleSignInAccount?> Function();

/// Google Calendar API scope — create and edit events.
const _calendarEventsScope = 'https://www.googleapis.com/auth/calendar.events';

/// Google OAuth2 authentication service for Calendar API access.
///
/// Manages the sign-in/sign-out lifecycle and provides an authenticated
/// HTTP client for Google API calls. All token management is delegated
/// to the google_sign_in SDK.
///
/// Usage:
///   final service = GoogleAuthService(); // production defaults
///   await service.signIn();
///   final client = await service.getAuthClient();
///   // Use client with googleapis CalendarApi
class GoogleAuthService {
  final GoogleSignInFn _signIn;
  final GoogleSignOutFn _signOut;
  final GoogleDisconnectFn _disconnect;
  final GoogleIsSignedInFn _isSignedIn;
  final GoogleAuthClientFn _getAuthClient;
  final GoogleSignInSilentlyFn _signInSilently;

  /// Create a GoogleAuthService with injectable callables.
  ///
  /// All parameters default to the real google_sign_in implementation.
  /// Override in tests with fakes.
  GoogleAuthService({
    GoogleSignInFn? signIn,
    GoogleSignOutFn? signOut,
    GoogleDisconnectFn? disconnect,
    GoogleIsSignedInFn? isSignedIn,
    GoogleAuthClientFn? getAuthClient,
    GoogleSignInSilentlyFn? signInSilently,
  }) : _signIn = signIn ?? _defaultGoogleSignIn.signIn,
       _signOut = signOut ?? _defaultGoogleSignIn.signOut,
       _disconnect = disconnect ?? _defaultGoogleSignIn.disconnect,
       _isSignedIn = isSignedIn ?? _defaultGoogleSignIn.isSignedIn,
       _getAuthClient =
           getAuthClient ?? _defaultGoogleSignIn.authenticatedClient,
       _signInSilently = signInSilently ?? _defaultGoogleSignIn.signInSilently;

  /// The shared GoogleSignIn instance with calendar.events scope.
  static final _defaultGoogleSignIn = GoogleSignIn(
    scopes: [_calendarEventsScope],
  );

  /// Trigger the Google OAuth2 consent flow.
  ///
  /// Returns the signed-in account, or null if the user cancelled.
  /// Throws on network errors or configuration issues.
  Future<GoogleSignInAccount?> signIn() async {
    try {
      return await _signIn();
    } on Exception catch (e) {
      if (kDebugMode) {
        debugPrint('GoogleAuthService.signIn failed: $e');
      }
      return null;
    }
  }

  /// Sign out and clear local tokens.
  ///
  /// The google_sign_in SDK clears tokens from secure storage.
  Future<void> signOut() async {
    try {
      await _signOut();
    } on Exception catch (e) {
      if (kDebugMode) {
        debugPrint('GoogleAuthService.signOut failed: $e');
      }
    }
  }

  /// Disconnect: revoke tokens on Google's server AND clear locally.
  ///
  /// This fully removes the app's access. The user will need to
  /// re-consent on next signIn(). Use for "Disconnect" in settings.
  Future<void> disconnect() async {
    try {
      await _disconnect();
    } on Exception catch (e) {
      if (kDebugMode) {
        debugPrint('GoogleAuthService.disconnect failed: $e');
      }
    }
  }

  /// Check if the user is currently signed in to Google.
  Future<bool> isSignedIn() async {
    try {
      return await _isSignedIn();
    } on Exception {
      return false;
    }
  }

  /// Try to silently restore a previous sign-in.
  ///
  /// Returns the account if tokens are still valid, null if re-consent
  /// is needed. Call this at app startup to restore state.
  Future<GoogleSignInAccount?> trySilentSignIn() async {
    try {
      return await _signInSilently();
    } on Exception catch (e) {
      if (kDebugMode) {
        debugPrint('GoogleAuthService.trySilentSignIn failed: $e');
      }
      return null;
    }
  }

  /// Get an authenticated HTTP client for Google API calls.
  ///
  /// Returns null if the user is not signed in or if the token
  /// cannot be refreshed. The google_sign_in SDK handles token
  /// refresh automatically.
  Future<googleapis_auth.AuthClient?> getAuthClient() async {
    try {
      return await _getAuthClient();
    } on Exception catch (e) {
      if (kDebugMode) {
        debugPrint('GoogleAuthService.getAuthClient failed: $e');
      }
      return null;
    }
  }
}
