// ===========================================================================
// file: lib/providers/settings_providers.dart
// purpose: Providers for app settings and derived data.
//
// Phase 1: lastSessionDateProvider for greeting gap detection.
// Phase 2: Assistant registration service + default assistant status.
// Future phases will add providers for:
//   - Theme preference (light/dark/system)
//   - Notification settings
//   - Sync configuration
// ===========================================================================

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:package_info_plus/package_info_plus.dart';

import '../services/assistant_registration_service.dart';
import 'database_provider.dart';

/// Provides the app version string from the platform package info.
///
/// Returns the semantic version (e.g. '0.14.0') from pubspec.yaml via
/// the package_info_plus plugin. Falls back to 'Unknown' on error.
final appVersionProvider = FutureProvider<String>((ref) async {
  try {
    final info = await PackageInfo.fromPlatform();
    return info.version;
  } on Exception {
    return 'Unknown';
  }
});

/// Provider for the assistant registration service.
///
/// Returns a default instance in production. Override in tests with a mock
/// or an instance configured with `isAndroid: true` to test channel calls.
final assistantServiceProvider = Provider<AssistantRegistrationService>((ref) {
  return AssistantRegistrationService(); // coverage:ignore-line
});

/// Provides the current default assistant status.
///
/// Returns `true` if this app is set as the default digital assistant on
/// Android 10+. Returns `false` on iOS, older Android, or on error.
///
/// Invalidate this provider to re-check (e.g., after returning from
/// system settings via `ref.invalidate(isDefaultAssistantProvider)`).
final isDefaultAssistantProvider = FutureProvider<bool>((ref) async {
  final service = ref.watch(assistantServiceProvider);
  return service.isDefaultAssistant();
});

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
