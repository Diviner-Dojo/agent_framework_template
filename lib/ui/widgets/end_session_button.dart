// ===========================================================================
// file: lib/ui/widgets/end_session_button.dart
// purpose: Button that triggers the end of a journaling session.
//
// Shows a confirmation dialog before actually ending the session,
// to prevent accidental taps from losing conversation state.
// ===========================================================================

import 'package:flutter/material.dart';

/// An icon button that ends the current journaling session.
///
/// [onEndSession] is called when the user confirms they want to end.
/// Typically placed in the app bar of the journal session screen.
class EndSessionButton extends StatelessWidget {
  final VoidCallback onEndSession;

  const EndSessionButton({super.key, required this.onEndSession});

  @override
  Widget build(BuildContext context) {
    return IconButton(
      icon: const Icon(Icons.stop_circle_outlined),
      tooltip: 'End session',
      onPressed: () => _showConfirmationDialog(context),
    );
  }

  /// Show a dialog asking the user to confirm ending the session.
  void _showConfirmationDialog(BuildContext context) {
    showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('End session?'),
        content: const Text(
          'This will save your journal entry and generate a summary.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () {
              Navigator.of(context).pop(true);
              onEndSession();
            },
            child: const Text('End'),
          ),
        ],
      ),
    );
  }
}
