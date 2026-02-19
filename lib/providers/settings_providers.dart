// ===========================================================================
// file: lib/providers/settings_providers.dart
// purpose: Providers for app settings and derived data.
//
// Phase 1: Minimal — only lastSessionDateProvider is needed.
// Future phases will add providers for:
//   - Theme preference (light/dark/system)
//   - Notification settings
//   - Sync configuration
//   - Voice input settings
// ===========================================================================

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'database_provider.dart';

/// Provides the start time of the most recent journal session.
///
/// Used by SessionNotifier to determine the greeting:
///   - If null → first-time user, show time-of-day greeting
///   - If > 2 days ago → show "It's been a few days" greeting
///   - Otherwise → show normal time-of-day greeting
///
/// This is a FutureProvider because it performs an async database query.
/// It auto-refreshes whenever the session list changes (because the
/// SessionDao query is re-evaluated).
final lastSessionDateProvider = FutureProvider<DateTime?>((ref) async {
  final sessionDao = ref.watch(sessionDaoProvider);
  // getAllSessionsByDate returns newest first, so first element is most recent.
  final sessions = await sessionDao.getAllSessionsByDate();
  if (sessions.isEmpty) return null;
  return sessions.first.startTime;
});
