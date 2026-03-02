// ===========================================================================
// file: lib/providers/onboarding_providers.dart
// purpose: Manages first-launch detection for the onboarding flow.
//
// SharedPreferences (for the Python developer):
//   SharedPreferences is Android/iOS's equivalent of a simple key-value store
//   (like a persistent dict). It's backed by an XML file on Android and
//   NSUserDefaults on iOS. Good for small settings, NOT for structured data
//   (use drift/SQLite for that).
//
// Why not use drift for this?
//   The onboarding flag needs to be checked BEFORE the database is ready.
//   SharedPreferences is synchronous-ready (after initial async load),
//   while drift requires async initialization. Using SharedPreferences
//   avoids a chicken-and-egg problem where we'd need the DB to decide
//   whether to show onboarding, but the DB isn't ready yet.
//
// Single Source of Truth:
//   The onboardingNotifierProvider is the ONLY provider for onboarding state.
//   Do NOT create a separate Provider<bool> that reads from SharedPreferences
//   directly — that would cause widgets watching the separate provider to
//   miss updates when completeOnboarding() is called.
//
// Why Notifier (not StateNotifier)?
//   Riverpod 2.x recommends Notifier over the legacy StateNotifier API.
//   Notifier gives the notifier access to `ref` directly, which simplifies
//   dependency access. Phase 1's SessionNotifier still uses StateNotifier
//   and should be migrated in a future coordinated effort.
// ===========================================================================

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Key used in SharedPreferences to track onboarding completion.
const onboardingCompleteKey = 'onboarding_complete';

/// Provider for the SharedPreferences instance.
///
/// This must be overridden in main.dart with the actual instance
/// (SharedPreferences requires async initialization before runApp).
///
/// Pattern explanation (for the Python developer):
///   This is like creating a DI container entry that says "I exist but I'm
///   not ready yet." In main.dart, we load SharedPreferences, then pass
///   the real instance as an override to ProviderScope. If any code
///   accidentally accesses this without the override, it throws immediately
///   rather than silently using a null or default — fail-fast behavior.
final sharedPreferencesProvider = Provider<SharedPreferences>((ref) {
  throw UnimplementedError(
    'sharedPreferencesProvider must be overridden in ProviderScope. '
    'See main.dart for the correct override pattern.',
  );
});

/// Manages onboarding completion state.
///
/// This is the SINGLE SOURCE OF TRUTH for onboarding state. The notifier's
/// state (a bool) indicates whether the user has completed onboarding:
///   - `false` → first launch, show onboarding
///   - `true` → onboarding done, show session list
///
/// Uses Riverpod 2.x's [Notifier] (not legacy [StateNotifier]) for direct
/// access to `ref` inside the notifier.
class OnboardingNotifier extends Notifier<bool> {
  /// Reads the initial value from SharedPreferences on first access.
  @override
  bool build() {
    final prefs = ref.watch(sharedPreferencesProvider);
    return prefs.getBool(onboardingCompleteKey) ?? false;
  }

  /// Mark onboarding as complete. Persists to SharedPreferences.
  ///
  /// This is idempotent — calling it multiple times is safe and will
  /// not throw or change behavior after the first call.
  Future<void> completeOnboarding() async {
    final prefs = ref.read(sharedPreferencesProvider);
    await prefs.setBool(onboardingCompleteKey, true);
    state = true;
  }
}

/// Provider for the onboarding notifier.
///
/// The notifier's STATE (bool) is the onboarding completion status.
/// Widget code should watch this provider for the bool value:
///   ```dart
///   final hasOnboarded = ref.watch(onboardingNotifierProvider);
///   ```
///
/// **Exception**: At the `MaterialApp` root, use `ref.read` instead of
/// `ref.watch`. Using `ref.watch` on a provider that feeds `initialRoute`
/// triggers a full `MaterialApp` rebuild when the state changes, which
/// collapses the Navigator route stack. See ADR-0029.
///
/// To mark onboarding complete:
///   ```dart
///   ref.read(onboardingNotifierProvider.notifier).completeOnboarding();
///   ```
final onboardingNotifierProvider = NotifierProvider<OnboardingNotifier, bool>(
  OnboardingNotifier.new,
);
