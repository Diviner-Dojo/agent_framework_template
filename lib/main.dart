// ===========================================================================
// file: lib/main.dart
// purpose: App entry point. Initializes services and wraps the app
//          in ProviderScope for Riverpod.
//
// ProviderScope is Riverpod's equivalent of a dependency injection container.
// It must wrap the entire app so all providers are accessible from any widget.
//
// Initialization order:
//   1. Flutter bindings (required for async before runApp)
//   2. SharedPreferences (onboarding state)
//   3. ConnectivityService (network monitoring for Layer B)
//   4. runApp with ProviderScope overrides
// ===========================================================================

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'app.dart';
import 'providers/onboarding_providers.dart';
import 'providers/session_providers.dart';
import 'services/connectivity_service.dart';

void main() async {
  // Ensure Flutter bindings are initialized before any async work.
  // This is required when calling platform channels or async code before runApp.
  WidgetsFlutterBinding.ensureInitialized();

  // Load SharedPreferences before the app starts.
  // This is needed for synchronous onboarding state checks in the widget tree.
  final prefs = await SharedPreferences.getInstance();

  // Initialize connectivity monitoring for Layer B (Claude API) support.
  // This checks current network state and subscribes to changes.
  // If initialization fails (e.g., platform plugin unavailable), the app
  // continues without connectivity monitoring — Layer A works regardless.
  final connectivityService = ConnectivityService();
  try {
    await connectivityService.initialize();
  } on Exception {
    // Connectivity plugin unavailable — Layer A fallback is always available.
  }

  runApp(
    // ProviderScope makes all Riverpod providers available to the widget tree.
    // Overrides inject pre-initialized instances that need async setup:
    //   - SharedPreferences for onboarding state
    //   - ConnectivityService for network monitoring (pre-initialized)
    ProviderScope(
      overrides: [
        sharedPreferencesProvider.overrideWithValue(prefs),
        connectivityServiceProvider.overrideWithValue(connectivityService),
      ],
      child: const AgenticJournalApp(),
    ),
  );
}
