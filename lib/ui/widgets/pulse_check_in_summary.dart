// ===========================================================================
// file: lib/ui/widgets/pulse_check_in_summary.dart
// purpose: Compact summary card for a completed Pulse Check-In response.
//
// Displayed in:
//   - Chat transcript (journal_session_screen.dart) after check-in completes
//   - Session detail screen (session_detail_screen.dart) for historical view
//
// Shows composite score (if computed), individual item scores, and a
// "That's enough." closing confirmation per ADHD UX constraint (no evaluation).
//
// See: SPEC-20260302-ADHD Phase 1 Task 7, CLAUDE.md §Clinical UX Constraints.
// ===========================================================================

import 'package:flutter/material.dart';

import '../../database/app_database.dart';
import '../../database/daos/questionnaire_dao.dart';

/// Compact summary card for a completed Pulse Check-In.
///
/// Renders the composite score (if non-null) and a list of per-item
/// scores in a compact non-evaluative format.
class PulseCheckInSummary extends StatelessWidget {
  const PulseCheckInSummary({
    required this.responseWithAnswers,
    required this.items,
    super.key,
  });

  /// The check-in response with all answers.
  final CheckInResponseWithAnswers responseWithAnswers;

  /// The questionnaire items (needed for question text and isReversed flag).
  final List<QuestionnaireItem> items;

  @override
  Widget build(BuildContext context) {
    final response = responseWithAnswers.response;
    final answers = responseWithAnswers.answers;

    return Card(
      color: Theme.of(context).colorScheme.surfaceContainerLow,
      margin: const EdgeInsets.symmetric(vertical: 6),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            // Header
            Row(
              children: [
                Icon(
                  Icons.monitor_heart_outlined,
                  size: 18,
                  color: Theme.of(context).colorScheme.primary,
                ),
                const SizedBox(width: 8),
                Text(
                  'Pulse Check-In',
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                    color: Theme.of(context).colorScheme.primary,
                  ),
                ),
                const Spacer(),
                if (response.compositeScore != null)
                  Text(
                    '${response.compositeScore!.toStringAsFixed(0)}/100',
                    style: Theme.of(context).textTheme.labelLarge?.copyWith(
                      color: Theme.of(context).colorScheme.primary,
                    ),
                  ),
              ],
            ),
            const Divider(height: 16),

            // Per-item scores
            ...List.generate(items.length, (i) {
              final item = items[i];
              final answer = answers
                  .where((a) => a.itemId == item.id)
                  .firstOrNull;
              final value = answer?.value;

              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 3),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Text(
                        item.questionText,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Text(
                      value != null ? '$value' : '—',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: value != null
                            ? Theme.of(context).colorScheme.onSurface
                            : Theme.of(context).colorScheme.outline,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              );
            }),

            const SizedBox(height: 8),

            // ADHD UX closing confirmation — never evaluative
            Text(
              'Saved. That\'s enough.',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.outline,
                fontStyle: FontStyle.italic,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
