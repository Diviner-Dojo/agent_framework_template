// ===========================================================================
// file: lib/app.dart
// purpose: Root MaterialApp widget with theme, navigation, and intent routing.
//
// Navigation Strategy:
//   Using string-based named routes for simplicity. Before Phase 5 adds
//   search screens, migrate to go_router for type-safe routing. This is
//   a known upgrade path, not technical debt.
//
// Routes:
//   '/'               → SessionListScreen (home — list of past sessions)
//   '/session'        → JournalSessionScreen (active conversation)
//   '/session/detail' → SessionDetailScreen (read-only transcript view)
//   '/search'         → SearchScreen (keyword search + filter UI)
//   '/settings'       → SettingsScreen (assistant status, app info)
//   '/auth'           → AuthScreen (optional sign in/up for cloud sync)
//   '/onboarding'     → ConversationalOnboardingScreen (first-launch session)
//
// Intent Routing (Phase 2):
//   When the app is launched via Android's assistant gesture (long-press Home),
//   the Kotlin side sets a flag that we check ONCE in initState(). If set,
//   we auto-start a new journal session after the first frame renders.
//   The _assistantLaunchChecked guard prevents double-fire on hot reload.
//
// Onboarding Redirect:
//   On first launch (onboardingNotifierProvider == false), the initial route
//   is '/onboarding'. After the user completes onboarding, subsequent
//   launches go to '/' (session list).
// ===========================================================================

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'providers/llm_providers.dart';
import 'providers/onboarding_providers.dart';
import 'providers/session_providers.dart';
import 'providers/settings_providers.dart';
import 'providers/voice_providers.dart';
import 'ui/screens/journal_session_screen.dart';
import 'ui/screens/conversational_onboarding_screen.dart';
import 'ui/screens/session_detail_screen.dart';
import 'ui/screens/auth_screen.dart';
import 'ui/screens/photo_gallery_screen.dart';
import 'ui/screens/search_screen.dart';
import 'ui/screens/session_list_screen.dart';
import 'ui/screens/settings_screen.dart';
import 'ui/screens/tasks_screen.dart';
import 'ui/theme/app_theme.dart';

/// The root widget of the app.
///
/// This is a ConsumerStatefulWidget (Riverpod-aware + stateful) because:
/// 1. We need initState() to check the assistant-launch flag exactly once
/// 2. We need ref access for providers (onboarding state, assistant service)
class AgenticJournalApp extends ConsumerStatefulWidget {
  const AgenticJournalApp({super.key});

  @override
  ConsumerState<AgenticJournalApp> createState() => _AgenticJournalAppState();
}

class _AgenticJournalAppState extends ConsumerState<AgenticJournalApp>
    with WidgetsBindingObserver {
  /// Guard to ensure wasLaunchedAsAssistant() is called exactly once
  /// per cold start. Without this, hot-reload or widget tree rebuilds
  /// could re-trigger the assistant launch detection.
  bool _assistantLaunchChecked = false;

  /// GlobalKey for the navigator so we can push routes from initState's
  /// post-frame callback, where we don't have a BuildContext from the
  /// MaterialApp's navigator.
  final _navigatorKey = GlobalKey<NavigatorState>();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _checkAssistantLaunch();
    // Non-blocking: load local LLM model in the background if downloaded.
    // App renders immediately; model ready in ~1-3s.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(llmAutoLoadProvider.future);
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  // coverage:ignore-start
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // When the app resumes, re-check if it was brought to foreground
    // via an assistant gesture (onNewIntent sets the flag in Kotlin).
    if (state == AppLifecycleState.resumed) {
      _checkAssistantRelaunch();
    }
  }

  /// Re-check assistant launch flags when the app is already running
  /// and brought to foreground via the assistant gesture.
  Future<void> _checkAssistantRelaunch() async {
    final service = ref.read(assistantServiceProvider);
    final wasVoiceAssistant = await service.wasLaunchedAsVoiceAssistant();
    final wasAssistant =
        wasVoiceAssistant || await service.wasLaunchedAsAssistant();
    if (!wasAssistant || !mounted) return;

    final hasOnboarded = ref.read(onboardingNotifierProvider);
    if (!hasOnboarded) return;

    if (wasVoiceAssistant) {
      ref.read(voiceModeEnabledProvider.notifier).setEnabled(true);
    }

    // Start a new session and navigate to it.
    try {
      await ref.read(sessionNotifierProvider.notifier).startSession();
      _navigatorKey.currentState?.pushNamed('/session');
    } catch (_) {
      // startSession failed — stay on current screen.
    }
  }
  // coverage:ignore-end

  /// Check if the app was launched via the assistant gesture.
  ///
  /// This is called exactly once in initState(). If the app was launched
  /// via ACTION_ASSIST, we auto-start a new journal session and navigate
  /// to the session screen. If specifically via VOICE_ASSIST, we also
  /// enable voice mode so the session starts in continuous voice mode.
  ///
  /// Why addPostFrameCallback?
  ///   We can't navigate until the MaterialApp's navigator is built.
  ///   addPostFrameCallback runs after the first frame, when the
  ///   navigator is ready.
  Future<void> _checkAssistantLaunch() async {
    if (_assistantLaunchChecked) return;
    _assistantLaunchChecked = true;

    final service = ref.read(assistantServiceProvider);
    // Check voice-specific launch BEFORE generic (both clear flags).
    final wasVoiceAssistant = await service.wasLaunchedAsVoiceAssistant();
    if (!mounted) return;
    final wasAssistant =
        wasVoiceAssistant || await service.wasLaunchedAsAssistant();
    if (!mounted) return;
    // Only auto-start a session if onboarding is already complete.
    // On first-ever launch via assistant gesture, onboarding must finish
    // first — otherwise /session gets pushed on top of /onboarding,
    // creating a broken back-stack.
    final hasOnboarded = ref.read(onboardingNotifierProvider);
    if (wasAssistant && hasOnboarded) {
      // If launched via VOICE_ASSIST, enable voice mode so the session
      // screen starts in continuous mode.
      if (wasVoiceAssistant) {
        ref.read(voiceModeEnabledProvider.notifier).setEnabled(true);
      }
      WidgetsBinding.instance.addPostFrameCallback((_) async {
        try {
          await ref.read(sessionNotifierProvider.notifier).startSession();
          _navigatorKey.currentState?.pushNamed('/session');
        } catch (_) {
          // startSession failed — stay on the initial route rather than
          // navigating to /session with no active session.
        }
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    // Read onboarding state once to determine the initial route.
    // IMPORTANT: Use ref.read, NOT ref.watch. Watching this provider causes
    // the MaterialApp to rebuild when onboarding completes, which changes
    // initialRoute on an already-mounted Navigator. This collapses the
    // Navigator's route stack (the new initialRoute conflicts with the
    // active navigation stack). The onboarding → session list transition
    // is handled by Navigator.pushReplacement/pop, not by initialRoute.
    final hasCompletedOnboarding = ref.read(onboardingNotifierProvider);

    return MaterialApp(
      title: 'Agentic Journal',
      debugShowCheckedModeBanner: false,
      navigatorKey: _navigatorKey,

      // Theme configuration — follows device light/dark setting.
      theme: AppTheme.light,
      darkTheme: AppTheme.dark,
      themeMode: ThemeMode.system,

      // Initial route depends on onboarding state.
      initialRoute: hasCompletedOnboarding ? '/' : '/onboarding',
      routes: {
        '/': (context) => const SessionListScreen(),
        '/session': (context) => const JournalSessionScreen(),
        '/search': (context) => const SearchScreen(),
        '/gallery': (context) => const PhotoGalleryScreen(),
        '/tasks': (context) => const TasksScreen(),
        '/settings': (context) => const SettingsScreen(),
        '/auth': (context) => const AuthScreen(),
        '/onboarding': (context) => const ConversationalOnboardingScreen(),
      },

      // onGenerateRoute handles routes that need arguments (like session ID).
      onGenerateRoute: (settings) {
        if (settings.name == '/session/detail') {
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
