// ===========================================================================
// file: lib/main.dart
// purpose: App entry point. Initializes SharedPreferences and wraps the app
//          in ProviderScope for Riverpod.
//
// ProviderScope is Riverpod's equivalent of a dependency injection container.
// It must wrap the entire app so all providers are accessible from any widget.
//
// SharedPreferences is loaded before runApp because:
//   1. The onboarding check needs it synchronously to decide the initial route
//   2. SharedPreferences.getInstance() is async, so we await it here
//   3. We pass it as a ProviderScope override so providers can use it
// ===========================================================================

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'app.dart';
import 'providers/onboarding_providers.dart';

void main() async {
  // Ensure Flutter bindings are initialized before any async work.
  // This is required when calling platform channels or async code before runApp.
  WidgetsFlutterBinding.ensureInitialized();

  // Load SharedPreferences before the app starts.
  // This is needed for synchronous onboarding state checks in the widget tree.
  final prefs = await SharedPreferences.getInstance();

  runApp(
    // ProviderScope makes all Riverpod providers available to the widget tree.
    // The override passes the loaded SharedPreferences instance to the
    // sharedPreferencesProvider, which would otherwise throw UnimplementedError.
    ProviderScope(
      overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      child: const AgenticJournalApp(),
    ),
  );
}
