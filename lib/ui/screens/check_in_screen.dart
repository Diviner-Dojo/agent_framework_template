// coverage:ignore-file — interactive stateful screen; covered by widget and integration tests.
// ===========================================================================
// file: lib/ui/screens/check_in_screen.dart
// purpose: Dedicated slider-based Pulse Check-In screen (text / non-voice mode).
//
// Shown when the user starts a pulse_check_in session with voice mode OFF.
// Voice mode check-ins continue to use JournalSessionScreen (existing path).
//
// Flow:
//   1. Screen opens with an active session already started by the caller.
//   2. CheckInNotifier.startCheckIn() is called in the first frame.
//   3. PulseCheckInWidget renders the slider questionnaire.
//   4. When isComplete=true, the session is closed via completeCheckInSession()
//      and a "Done" card is shown with an optional "Add journal note" CTA.
//   5. Back pressed while in-progress → discard confirmation dialog.
//
// ADHD UX: keeps focus on the sliders only (no chat chrome).
// See: SPEC-20260302-adhd-informed-feature-roadmap.md Phase 1 Task 10.
// ===========================================================================

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../providers/questionnaire_providers.dart';
import '../../providers/session_providers.dart';
import '../widgets/pulse_check_in_widget.dart';

/// Dedicated screen for the visual (slider-based) Pulse Check-In.
///
/// Reads the active session ID from [sessionNotifierProvider] — the caller
/// is responsible for starting the session before navigating here.
class CheckInScreen extends ConsumerStatefulWidget {
  const CheckInScreen({super.key});

  @override
  ConsumerState<CheckInScreen> createState() => _CheckInScreenState();
}

class _CheckInScreenState extends ConsumerState<CheckInScreen> {
  /// True after [completeCheckInSession] succeeds.
  bool _sessionComplete = false;

  @override
  void initState() {
    super.initState();
    // Start the check-in after the first frame so the provider tree is ready.
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      await ref.read(checkInProvider.notifier).startCheckIn();
    });
  }

  @override
  Widget build(BuildContext context) {
    final sessionState = ref.watch(sessionNotifierProvider);
    final checkInState = ref.watch(checkInProvider);
    final sessionId = sessionState.activeSessionId;

    // Watch for completion and close the session once.
    if (checkInState.isComplete && !_sessionComplete && sessionId != null) {
      _sessionComplete = true;
      // Schedule the session close after the current frame to avoid calling
      // setState/notifier during build.
      WidgetsBinding.instance.addPostFrameCallback((_) async {
        await ref
            .read(sessionNotifierProvider.notifier)
            .completeCheckInSession();
      });
    }

    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) async {
        if (didPop) return;
        await _handleBack(context, checkInState);
      },
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Pulse Check-In'),
          leading: IconButton(
            icon: const Icon(Icons.arrow_back),
            onPressed: () => _handleBack(context, checkInState),
          ),
        ),
        body: SafeArea(
          child: _sessionComplete || checkInState.isComplete
              ? _buildCompleteCard(context)
              : _buildCheckIn(sessionId),
        ),
      ),
    );
  }

  /// The slider questionnaire — shown while the check-in is in progress.
  Widget _buildCheckIn(String? sessionId) {
    if (sessionId == null) {
      return const Center(child: CircularProgressIndicator());
    }
    return SingleChildScrollView(
      child: PulseCheckInWidget(sessionId: sessionId),
    );
  }

  /// Completion card shown after the check-in is saved.
  Widget _buildCompleteCard(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.check_circle_outline,
              size: 64,
              color: theme.colorScheme.primary,
            ),
            const SizedBox(height: 16),
            Text('Check-in saved.', style: theme.textTheme.titleLarge),
            const SizedBox(height: 8),
            Text(
              "That's enough.",
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 32),
            FilledButton.tonal(
              onPressed: () {
                // Navigate back to home — session is already closed.
                Navigator.of(context).popUntil((route) => route.isFirst);
              },
              child: const Text('Done'),
            ),
            const SizedBox(height: 12),
            TextButton(
              onPressed: () async {
                // The check-in session is already closed. Start a new free-form
                // session and navigate directly — no intermediate SnackBar step.
                await ref.read(sessionNotifierProvider.notifier).startSession();
                if (context.mounted) {
                  // Replace the check-in route with the session screen so
                  // Back from /session goes directly to home (/).
                  Navigator.of(context).pushReplacementNamed('/session');
                }
              },
              child: const Text('Add a journal note'),
            ),
          ],
        ),
      ),
    );
  }

  /// Handle the back button — show a discard dialog if in progress.
  Future<void> _handleBack(
    BuildContext context,
    CheckInState checkInState,
  ) async {
    // If already complete (or not started), just pop.
    if (_sessionComplete || !checkInState.isActive) {
      Navigator.of(context).pop();
      return;
    }

    // Check-in is in progress — confirm discard.
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Discard check-in?'),
        content: const Text('Your answers will not be saved.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Keep going'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Discard'),
          ),
        ],
      ),
    );

    if (confirmed != true || !context.mounted) return;

    // Cancel the check-in state and discard the underlying session.
    ref.read(checkInProvider.notifier).cancelCheckIn();
    await ref.read(sessionNotifierProvider.notifier).discardSession();

    if (context.mounted) {
      Navigator.of(context).pop();
    }
  }
}
