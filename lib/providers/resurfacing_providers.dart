// ===========================================================================
// file: lib/providers/resurfacing_providers.dart
// purpose: Providers for home-screen memory resurfacing (Phase 3C).
//
// resurfacingServiceProvider — assembles the service with its dependencies.
// resurfacedSessionProvider  — FutureProvider that picks the session to show.
//
// Invalidate resurfacedSessionProvider after a Skip or Reflect action to
// refresh the card (either a new session surfaces, or the card disappears).
//
// See: lib/services/resurfacing_service.dart
//      SPEC-20260302-adhd-informed-feature-roadmap § Phase 3C
// ===========================================================================

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../database/app_database.dart';
import '../services/resurfacing_service.dart';
import 'database_provider.dart';
import 'onboarding_providers.dart';

/// Provider for [ResurfacingService].
final resurfacingServiceProvider = Provider<ResurfacingService>((ref) {
  return ResurfacingService(
    ref.watch(sessionDaoProvider),
    ref.watch(sharedPreferencesProvider),
  );
});

/// The past session to resurface on the home screen, or null if none qualifies.
///
/// Invalidate after the user taps Skip or Reflect to trigger a fresh pick:
/// ```dart
/// ref.invalidate(resurfacedSessionProvider);
/// ```
final resurfacedSessionProvider = FutureProvider<JournalSession?>((ref) {
  return ref.watch(resurfacingServiceProvider).pickResurfacedSession();
});
