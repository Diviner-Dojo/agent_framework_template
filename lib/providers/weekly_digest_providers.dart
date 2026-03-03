// ===========================================================================
// file: lib/providers/weekly_digest_providers.dart
// purpose: Providers for the home-screen weekly celebratory digest (Phase 3D).
//
// weeklyDigestServiceProvider — assembles the service with its dependencies.
// weeklyDigestProvider        — FutureProvider that builds the digest to show.
//
// Invalidate weeklyDigestProvider after the user dismisses the card:
// ```dart
// ref.invalidate(weeklyDigestProvider);
// ```
//
// See: lib/services/weekly_digest_service.dart
//      SPEC-20260302-adhd-informed-feature-roadmap § Phase 3D
// ===========================================================================

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/weekly_digest_service.dart';
import 'database_provider.dart';
import 'onboarding_providers.dart';

/// Provider for [WeeklyDigestService].
final weeklyDigestServiceProvider = Provider<WeeklyDigestService>((ref) {
  return WeeklyDigestService(
    ref.watch(sessionDaoProvider),
    ref.watch(sharedPreferencesProvider),
  );
});

/// The weekly digest to display on the home screen, or null if not applicable.
///
/// Returns null when:
///   - The digest was dismissed within the past 7 days.
///   - There are no eligible sessions this week.
///
/// Invalidate after the user dismisses the card to hide it immediately.
final weeklyDigestProvider = FutureProvider<WeeklyDigest?>((ref) {
  return ref.watch(weeklyDigestServiceProvider).getDigest();
});
