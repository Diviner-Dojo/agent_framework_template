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
import 'providers/notification_providers.dart';
import 'providers/onboarding_providers.dart';
import 'providers/session_providers.dart';
import 'providers/last_capture_mode_provider.dart';
import 'providers/settings_providers.dart';
import 'providers/theme_providers.dart';
import 'providers/voice_providers.dart';
import 'ui/screens/check_in_history_screen.dart';
import 'ui/screens/check_in_screen.dart';
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

  /// Guard to ensure getWidgetLaunchMode() is called exactly once per
  /// cold start (Phase 4B — Quick Capture widget).
  bool _widgetLaunchChecked = false;

  /// Guard to prevent double-fire within a single resume event (Phase 4B).
  /// Resets to false on each resume so subsequent widget taps are handled.
  /// Distinct from [_widgetLaunchChecked] which is a one-time cold-start guard.
  bool _widgetRelaunchChecked = false;

  /// GlobalKey for the navigator so we can push routes from initState's
  /// post-frame callback, where we don't have a BuildContext from the
  /// MaterialApp's navigator.
  final _navigatorKey = GlobalKey<NavigatorState>();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _checkAssistantLaunch();
    _checkWidgetLaunch();
    // Non-blocking: load local LLM model in the background if downloaded.
    // App renders immediately; model ready in ~1-3s.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(llmAutoLoadProvider.future);
      // Restore OS notification alarms cleared by device reboot (ADR-0033).
      // Non-blocking: runs in background and silently skips past-due tasks.
      ref.read(notificationBootRestoreProvider.future);
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
    // via an assistant gesture or widget tap (onNewIntent sets the flag
    // in Kotlin for both paths).
    if (state == AppLifecycleState.resumed) {
      _checkAssistantRelaunch();
      _checkWidgetRelaunch();
      // Reset the resume guard so the next resume event is not skipped.
      _widgetRelaunchChecked = false;
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

  /// Check if the app was launched from the Quick Capture home screen widget.
  ///
  /// Called exactly once in initState(). If the widget passed a capture mode,
  /// we store it in [pendingWidgetLaunchModeProvider] so [SessionListScreen]
  /// can dispatch it via [ref.listen] on the first rendered frame.
  // coverage:ignore-start
  Future<void> _checkWidgetLaunch() async {
    if (_widgetLaunchChecked) return;
    _widgetLaunchChecked = true;

    final service = ref.read(widgetLaunchServiceProvider);
    final mode = await service.getWidgetLaunchMode();
    if (mode == null || !mounted) return;

    final hasOnboarded = ref.read(onboardingNotifierProvider);
    if (!hasOnboarded) return;

    ref.read(pendingWidgetLaunchModeProvider.notifier).state = mode;
  }

  /// Re-check widget launch when the app is already running and brought to
  /// foreground by tapping the home screen widget (onNewIntent path).
  ///
  /// Without this, [_checkWidgetLaunch]'s one-time cold-start guard prevents
  /// the channel from being read again, so warm-start widget taps are dropped
  /// silently — the most common real-world usage pattern.
  ///
  /// [_widgetRelaunchChecked] prevents double-fire within a single resume
  /// event and is reset by [didChangeAppLifecycleState] on the next resume.
  Future<void> _checkWidgetRelaunch() async {
    if (_widgetRelaunchChecked) return;
    _widgetRelaunchChecked = true;

    final service = ref.read(widgetLaunchServiceProvider);
    final mode = await service.getWidgetLaunchMode();
    if (mode == null || !mounted) return;

    final hasOnboarded = ref.read(onboardingNotifierProvider);
    if (!hasOnboarded) return;

    ref.read(pendingWidgetLaunchModeProvider.notifier).state = mode;
  }
  // coverage:ignore-end

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

    // Theme configuration — driven by user preference via themeProvider.
    // ADR-0029 evaluated: ref.watch() is safe here because theme changes
    // trigger animated transitions, not Navigator stack collapses (unlike
    // initialRoute). See theme_providers.dart for full rationale.
    final themeState = ref.watch(themeProvider);
    final palette = themeState.palette;
    final lightTheme = AppTheme.withCardStyle(
      AppTheme.fromPalette(palette, Brightness.light),
      themeState.cardStyle,
    );
    final darkTheme = AppTheme.withCardStyle(
      AppTheme.fromPalette(palette, Brightness.dark),
      themeState.cardStyle,
    );

    return MaterialApp(
      title: 'Agentic Journal',
      debugShowCheckedModeBanner: false,
      navigatorKey: _navigatorKey,

      // Dynamic theme from user's palette and card style preferences.
      theme: lightTheme,
      darkTheme: darkTheme,
      themeMode: themeState.themeMode,

      // Apply user's font scale preference as an additive offset on the
      // system text scale, clamped at 0.8–2.0 effective scale.
      builder: (context, child) {
        final systemScale = MediaQuery.of(context).textScaler.scale(1.0);
        final effectiveScale = themeState.fontScaleFactor(systemScale);
        return MediaQuery(
          data: MediaQuery.of(
            context,
          ).copyWith(textScaler: TextScaler.linear(effectiveScale)),
          child: child!,
        );
      },

      // Initial route depends on onboarding state.
      initialRoute: hasCompletedOnboarding ? '/' : '/onboarding',
      routes: {
        '/': (context) => const SessionListScreen(),
        '/session': (context) => const JournalSessionScreen(),
        '/check_in': (context) => const CheckInScreen(),
        '/check_in_history': (context) => const CheckInHistoryScreen(),
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
