// ===========================================================================
// file: lib/app.dart
// purpose: Root MaterialApp widget with theme and navigation setup.
//
// Navigation Strategy (intentional for Phase 1):
//   Using string-based named routes for simplicity with only 3 screens.
//   Before Phase 5 adds search and onboarding screens, migrate to go_router
//   for type-safe, declarative routing. This is a known upgrade path, not
//   technical debt.
//
// Routes:
//   '/'               → SessionListScreen (home — list of past sessions)
//   '/session'        → JournalSessionScreen (active conversation)
//   '/session/detail' → SessionDetailScreen (read-only transcript view)
// ===========================================================================

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'ui/theme/app_theme.dart';
import 'ui/screens/session_list_screen.dart';
import 'ui/screens/journal_session_screen.dart';
import 'ui/screens/session_detail_screen.dart';

/// The root widget of the app.
///
/// This is a ConsumerWidget (Riverpod-aware) so that child screens
/// can access providers without additional setup.
class AgenticJournalApp extends ConsumerWidget {
  const AgenticJournalApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp(
      title: 'Agentic Journal',
      debugShowCheckedModeBanner: false,

      // Theme configuration — follows device light/dark setting.
      theme: AppTheme.light,
      darkTheme: AppTheme.dark,
      themeMode: ThemeMode.system,

      // Named routes for navigation.
      initialRoute: '/',
      routes: {
        '/': (context) => const SessionListScreen(),
        '/session': (context) => const JournalSessionScreen(),
      },

      // onGenerateRoute handles routes that need arguments (like session ID).
      // The '/session/detail' route receives a session ID as an argument.
      onGenerateRoute: (settings) {
        if (settings.name == '/session/detail') {
          // The session ID is passed as an argument when navigating.
          final sessionId = settings.arguments as String;
          return MaterialPageRoute(
            builder: (context) => SessionDetailScreen(sessionId: sessionId),
          );
        }
        return null;
      },
    );
  }
}
