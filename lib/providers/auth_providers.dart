// ===========================================================================
// file: lib/providers/auth_providers.dart
// purpose: Riverpod providers for authentication state.
//
// These providers wrap SupabaseService's auth methods and expose reactive
// state for the UI. The auth state is optional — when Supabase is not
// configured, all providers return "not authenticated" defaults.
//
// See: ADR-0012 (Optional Auth with Upload-Only Cloud Sync)
// ===========================================================================

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../services/supabase_service.dart';
import 'session_providers.dart';

/// Provides the singleton SupabaseService.
///
/// Depends on the environment provider for configuration.
/// When not configured, the service's methods return null/no-op.
final supabaseServiceProvider = Provider<SupabaseService>((ref) {
  final environment = ref.watch(environmentProvider);
  return SupabaseService(environment: environment);
});

/// Streams auth state changes from Supabase.
///
/// Emits [AuthState] events when the user signs in, signs out, or
/// the token is refreshed. When not configured, emits nothing.
final authStateProvider = StreamProvider<AuthState>((ref) {
  final service = ref.watch(supabaseServiceProvider);
  return service.onAuthStateChange;
});

/// Whether a user is currently authenticated.
///
/// Derived from [authStateProvider]. Returns false when:
///   - Supabase is not configured
///   - Auth state is loading
///   - No user is signed in
final isAuthenticatedProvider = Provider<bool>((ref) {
  final service = ref.watch(supabaseServiceProvider);
  // Watch authStateProvider to reactively update when auth changes
  ref.watch(authStateProvider);
  return service.isAuthenticated;
});

/// The currently signed-in user, or null.
///
/// Derived from [authStateProvider]. Returns null when not authenticated.
final currentUserProvider = Provider<User?>((ref) {
  final service = ref.watch(supabaseServiceProvider);
  // Watch authStateProvider to reactively update when auth changes
  ref.watch(authStateProvider);
  return service.currentUser;
});
