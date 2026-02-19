// ===========================================================================
// file: lib/main.dart
// purpose: App entry point. Wraps the app in ProviderScope for Riverpod.
//
// ProviderScope is Riverpod's equivalent of a dependency injection container.
// It must wrap the entire app so all providers are accessible from any widget.
// ===========================================================================

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';

void main() {
  // Ensure Flutter bindings are initialized before any async work.
  // This is required when calling platform channels or async code before runApp.
  WidgetsFlutterBinding.ensureInitialized();

  runApp(
    // ProviderScope makes all Riverpod providers available to the widget tree.
    const ProviderScope(child: AgenticJournalApp()),
  );
}
