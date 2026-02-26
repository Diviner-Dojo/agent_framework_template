// ===========================================================================
// file: lib/ui/screens/conversational_onboarding_screen.dart
// purpose: First-launch conversational onboarding screen.
//
// Instead of a static wizard, this screen auto-starts a real journal
// session with journalingMode 'onboarding' and immediately navigates
// to the session screen. The onboarding IS the first journal entry.
//
// When the session ends normally, endSession() checks the journaling
// mode and marks onboarding complete so subsequent launches go straight
// to the session list.
//
// See: ADR-0026 (Conversational Onboarding)
// ===========================================================================

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../providers/session_providers.dart';

/// Conversational onboarding screen — starts a real session and navigates
/// to the journal session screen.
///
/// This is a thin wrapper that shows a loading state during the brief
/// async gap while the session is being created. On error, it falls back
/// to the session list with an error message.
class ConversationalOnboardingScreen extends ConsumerStatefulWidget {
  const ConversationalOnboardingScreen({super.key});

  @override
  ConsumerState<ConversationalOnboardingScreen> createState() =>
      _ConversationalOnboardingScreenState();
}

class _ConversationalOnboardingScreenState
    extends ConsumerState<ConversationalOnboardingScreen> {
  bool _isStarting = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _startOnboardingSession();
    });
  }

  /// Start the onboarding session and navigate to the session screen.
  Future<void> _startOnboardingSession() async {
    if (_isStarting) return;
    setState(() => _isStarting = true);

    try {
      await ref
          .read(sessionNotifierProvider.notifier)
          .startSession(journalingMode: 'onboarding');

      if (mounted) {
        Navigator.of(context).pushReplacementNamed('/session');
      }
    } on Exception {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Could not start journal. Restart the app to try again.',
            ),
          ),
        );
        // Fall back to session list so the user isn't stuck.
        Navigator.of(context).pushReplacementNamed('/');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.book_outlined,
              size: 64,
              color: Theme.of(context).colorScheme.primary,
            ),
            const SizedBox(height: 24),
            Text(
              'Setting up your journal...',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 16),
            const CircularProgressIndicator(),
          ],
        ),
      ),
    );
  }
}
