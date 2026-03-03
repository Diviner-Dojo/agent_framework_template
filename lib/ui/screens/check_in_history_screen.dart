// coverage:ignore-file — interactive UI screen; covered by widget tests.
// ===========================================================================
// file: lib/ui/screens/check_in_history_screen.dart
// purpose: Check-In History Dashboard — a chronological view of all Pulse
//          Check-In responses with composite scores and per-question answers.
//
// UI design (ADHD UX):
//   - No gap dates, no streak counters, no "last check-in" mentions.
//   - Each entry shows date + composite score + expandable answer list.
//   - Score chip uses a neutral palette (not red/green to avoid judgement).
//   - Visible after the user's first completed check-in.
//
// Accessed via the insights icon (Icons.insights_outlined) in the home
// screen AppBar. The icon is hidden until at least one check-in exists.
//
// See: SPEC-20260302-adhd-informed-feature-roadmap.md Phase 3E.
// ===========================================================================

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../database/app_database.dart';
import '../../providers/questionnaire_providers.dart';

/// Dashboard showing all Pulse Check-In history entries.
class CheckInHistoryScreen extends ConsumerWidget {
  const CheckInHistoryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final historyAsync = ref.watch(checkInHistoryProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Check-In History')),
      body: historyAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('Error loading history: $e')),
        data: (entries) {
          if (entries.isEmpty) {
            return _buildEmpty(context);
          }
          return ListView.builder(
            padding: const EdgeInsets.symmetric(vertical: 8),
            itemCount: entries.length,
            itemBuilder: (context, index) {
              return _CheckInEntryCard(entry: entries[index]);
            },
          );
        },
      ),
    );
  }

  Widget _buildEmpty(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.insights_outlined,
              size: 64,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
            const SizedBox(height: 16),
            Text(
              'No check-ins yet',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Text(
              'Complete a Quick Check-In to see your history here.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}

/// A card for a single check-in entry with expandable answer detail.
class _CheckInEntryCard extends StatefulWidget {
  final CheckInHistoryEntry entry;

  const _CheckInEntryCard({required this.entry});

  @override
  State<_CheckInEntryCard> createState() => _CheckInEntryCardState();
}

class _CheckInEntryCardState extends State<_CheckInEntryCard> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final response = widget.entry.response;
    final answers = widget.entry.answers;
    final itemText = widget.entry.itemText;

    final local = response.completedAt.toLocal();
    final date = _formatDate(local);
    final timeStr = _formatTime(local);
    final score = response.compositeScore;

    // Sort answers by itemId for consistent ordering.
    final sortedAnswers = List<CheckInAnswer>.from(answers)
      ..sort((a, b) => a.itemId.compareTo(b.itemId));

    final scoreLabel = score != null
        ? ', score ${score.toStringAsFixed(0)} out of 100'
        : '';
    final expandLabel = _expanded ? 'expanded' : 'collapsed';

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      child: Semantics(
        button: true,
        label: '$date$scoreLabel, $expandLabel. Tap to toggle.',
        child: InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: () => setState(() => _expanded = !_expanded),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Header row: date + score chip.
                Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(date, style: theme.textTheme.titleSmall),
                          Text(
                            timeStr,
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: theme.colorScheme.onSurfaceVariant,
                            ),
                          ),
                        ],
                      ),
                    ),
                    if (score != null)
                      Chip(
                        label: Text(
                          '${score.toStringAsFixed(0)} / 100',
                          style: theme.textTheme.labelMedium?.copyWith(
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        backgroundColor: theme.colorScheme.secondaryContainer,
                        side: BorderSide.none,
                      ),
                    const SizedBox(width: 4),
                    Icon(
                      _expanded
                          ? Icons.keyboard_arrow_up
                          : Icons.keyboard_arrow_down,
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ],
                ),

                // Expandable answer list.
                if (_expanded) ...[
                  const SizedBox(height: 12),
                  const Divider(height: 1),
                  const SizedBox(height: 8),
                  if (sortedAnswers.isEmpty)
                    Text(
                      'No answers recorded.',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    )
                  else
                    ...sortedAnswers.map(
                      (a) => _AnswerRow(
                        question: itemText[a.itemId] ?? 'Question ${a.itemId}',
                        value: a.value,
                        scaleMin: widget.entry.scaleMin,
                        scaleMax: widget.entry.scaleMax,
                      ),
                    ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// A single answer row: question text + value bar.
class _AnswerRow extends StatelessWidget {
  final String question;
  final int? value;
  final int scaleMin;
  final int scaleMax;

  const _AnswerRow({
    required this.question,
    required this.value,
    required this.scaleMin,
    required this.scaleMax,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final skipped = value == null;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            question,
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 4),
          if (skipped)
            Text(
              'Skipped',
              style: theme.textTheme.bodySmall?.copyWith(
                fontStyle: FontStyle.italic,
                color: theme.colorScheme.outline,
              ),
            )
          else
            Semantics(
              label: '$question: $value',
              excludeSemantics: true,
              child: Row(
                children: [
                  Expanded(
                    child: LinearProgressIndicator(
                      value: _normalizeValue(value!, scaleMin, scaleMax),
                      backgroundColor:
                          theme.colorScheme.surfaceContainerHighest,
                      minHeight: 6,
                      borderRadius: BorderRadius.circular(3),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    value.toString(),
                    style: theme.textTheme.bodyMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                      color: theme.colorScheme.primary,
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Scale normalization
// ---------------------------------------------------------------------------

/// Normalize a raw answer [value] to 0.0–1.0 within [scaleMin]..[scaleMax].
///
/// Guards against a degenerate template where [scaleMin] == [scaleMax] —
/// returns 0.0 rather than dividing by zero.
double _normalizeValue(int value, int scaleMin, int scaleMax) {
  final range = scaleMax - scaleMin;
  if (range <= 0) return 0.0;
  return (value - scaleMin) / range;
}

// ---------------------------------------------------------------------------
// Date / time formatting helpers (no intl dependency)
// ---------------------------------------------------------------------------

const _months = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
];

const _weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

/// Format a local DateTime as "Wed, Mar 4, 2026".
String _formatDate(DateTime local) {
  final wd = _weekdays[local.weekday - 1];
  final mo = _months[local.month - 1];
  return '$wd, $mo ${local.day}, ${local.year}';
}

/// Format a local DateTime as "2:30 PM".
String _formatTime(DateTime local) {
  final hour = local.hour == 0
      ? 12
      : local.hour > 12
      ? local.hour - 12
      : local.hour;
  final min = local.minute.toString().padLeft(2, '0');
  final period = local.hour < 12 ? 'AM' : 'PM';
  return '$hour:$min $period';
}
