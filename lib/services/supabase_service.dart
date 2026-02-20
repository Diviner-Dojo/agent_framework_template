// ===========================================================================
// file: lib/services/supabase_service.dart
// purpose: Wraps supabase_flutter for auth and database operations.
//
// This service provides:
//   - Email+password authentication (sign up, sign in, sign out)
//   - Auth state stream for reactive UI updates
//   - JWT access token for Edge Function auth
//   - Supabase client access for database UPSERT operations (sync)
//
// Design:
//   - All methods are guarded by isConfigured — returns null/no-op when
//     Supabase is not configured (optional auth per ADR-0012)
//   - Token persistence is handled by supabase_flutter internally
//     (uses flutter_secure_storage under the hood)
//   - The service is a thin wrapper — no business logic, just delegation
//
// See: ADR-0012 (Optional Auth with Upload-Only Cloud Sync)
// ===========================================================================

import 'dart:async';

import 'package:supabase_flutter/supabase_flutter.dart';

import '../config/environment.dart';

// ---------------------------------------------------------------------------
// Typed exceptions
// ---------------------------------------------------------------------------

/// Base exception for Supabase service errors.
class SupabaseServiceException implements Exception {
  final String message;
  const SupabaseServiceException(this.message);

  @override
  String toString() => 'SupabaseServiceException: $message';
}

/// Auth operation failed (invalid credentials, network error, etc.)
class SupabaseAuthException extends SupabaseServiceException {
  const SupabaseAuthException(super.message);
}

// ---------------------------------------------------------------------------
// Service
// ---------------------------------------------------------------------------

/// Wraps supabase_flutter for auth and database operations.
///
/// All methods are guarded by [isConfigured]. When Supabase is not
/// configured (missing --dart-define values), methods return null or no-op.
/// This supports the optional auth model (ADR-0012).
class SupabaseService {
  final Environment _environment;

  /// Creates a SupabaseService with the given environment configuration.
  SupabaseService({required Environment environment})
    : _environment = environment;

  /// Whether Supabase is configured and ready for use.
  bool get isConfigured => _environment.isConfigured;

  /// The Supabase client instance. Only access when [isConfigured] is true.
  SupabaseClient get _client => Supabase.instance.client;

  // =========================================================================
  // Auth methods
  // =========================================================================

  /// Sign up a new user with email and password.
  ///
  /// Returns the [User] on success, or throws [SupabaseAuthException] on failure.
  /// Returns null if Supabase is not configured.
  Future<User?> signUp({
    required String email,
    required String password,
  }) async {
    if (!isConfigured) return null;

    try {
      final response = await _client.auth.signUp(
        email: email,
        password: password,
      );
      return response.user;
    } on AuthException catch (e) {
      throw SupabaseAuthException(e.message);
    }
  }

  /// Sign in an existing user with email and password.
  ///
  /// Returns the [User] on success, or throws [SupabaseAuthException] on failure.
  /// Returns null if Supabase is not configured.
  Future<User?> signIn({
    required String email,
    required String password,
  }) async {
    if (!isConfigured) return null;

    try {
      final response = await _client.auth.signInWithPassword(
        email: email,
        password: password,
      );
      return response.user;
    } on AuthException catch (e) {
      throw SupabaseAuthException(e.message);
    }
  }

  /// Sign out the current user.
  ///
  /// No-op if not configured or not signed in.
  Future<void> signOut() async {
    if (!isConfigured) return;

    try {
      await _client.auth.signOut();
    } on AuthException catch (e) {
      throw SupabaseAuthException(e.message);
    }
  }

  /// The currently signed-in user, or null if not authenticated.
  User? get currentUser {
    if (!isConfigured) return null;
    return _client.auth.currentUser;
  }

  /// Whether a user is currently signed in.
  bool get isAuthenticated => currentUser != null;

  /// Stream of auth state changes for reactive UI updates.
  ///
  /// Emits [AuthState] events when the user signs in, signs out, or
  /// the token is refreshed. Returns an empty stream if not configured.
  Stream<AuthState> get onAuthStateChange {
    if (!isConfigured) return const Stream.empty();
    return _client.auth.onAuthStateChange;
  }

  /// The current JWT access token, or null if not authenticated.
  ///
  /// Used by ClaudeApiService and SyncRepository to authenticate
  /// requests to Supabase Edge Functions and the database.
  String? get accessToken {
    if (!isConfigured) return null;
    return _client.auth.currentSession?.accessToken;
  }

  // =========================================================================
  // Database access (for sync)
  // =========================================================================

  /// The Supabase client for direct database operations.
  ///
  /// Used by SyncRepository to UPSERT sessions and messages.
  /// Returns null if not configured.
  SupabaseClient? get client {
    if (!isConfigured) return null;
    return _client;
  }
}
