// coverage:ignore-file — interactive stateful widget; covered by integration tests.
// ===========================================================================
// file: lib/ui/widgets/pulse_check_in_widget.dart
// purpose: Visual (text mode) Pulse Check-In UI — slider-based questionnaire.
//
// Displays the current check-in question with a 1-10 slider and endpoint
// labels. Shows progress ("3 of 6") and handles the full item sequence.
// After the last item, shows the summary card via PulseCheckInSummary.
//
// Voice mode uses CheckInNotifier directly — this widget is text mode only.
//
// See: SPEC-20260302-ADHD Phase 1 Task 5.
// ===========================================================================

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../providers/questionnaire_providers.dart';

/// Slider-based Pulse Check-In widget for text (non-voice) mode.
///
/// Renders the current question with:
/// - A Material 3 Slider (scaleMin to scaleMax)
/// - Endpoint labels (minLabel / maxLabel)
/// - Progress indicator ("3 of 6")
/// - Save/Next button that advances to the next question
class PulseCheckInWidget extends ConsumerStatefulWidget {
  const PulseCheckInWidget({required this.sessionId, super.key});

  /// The active session ID — passed through to [CheckInNotifier.recordAnswer].
  final String sessionId;

  @override
  ConsumerState<PulseCheckInWidget> createState() => _PulseCheckInWidgetState();
}

class _PulseCheckInWidgetState extends ConsumerState<PulseCheckInWidget> {
  double _sliderValue = 5.0;
  bool _hasInteracted = false;

  @override
  Widget build(BuildContext context) {
    final checkInState = ref.watch(checkInProvider);

    if (!checkInState.isActive) {
      return const SizedBox.shrink();
    }

    if (checkInState.isComplete) {
      return _buildComplete(context, checkInState);
    }

    final item = checkInState.currentItem!;
    final template = checkInState.template;
    final scaleMin = (template?.scaleMin ?? 1).toDouble();
    final scaleMax = (template?.scaleMax ?? 10).toDouble();

    return Card(
      margin: const EdgeInsets.all(12),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            // Progress indicator
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Pulse Check-In',
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                    color: Theme.of(context).colorScheme.primary,
                  ),
                ),
                Text(
                  checkInState.progressLabel,
                  style: Theme.of(context).textTheme.labelMedium?.copyWith(
                    color: Theme.of(context).colorScheme.outline,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            LinearProgressIndicator(
              value: checkInState.currentStepIndex / checkInState.items.length,
              backgroundColor: Theme.of(
                context,
              ).colorScheme.surfaceContainerHighest,
            ),
            const SizedBox(height: 20),

            // Question text
            Text(
              item.questionText,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 24),

            // Slider
            Slider(
              value: _sliderValue.clamp(scaleMin, scaleMax),
              min: scaleMin,
              max: scaleMax,
              divisions: (scaleMax - scaleMin).toInt(),
              label: _sliderValue.round().toString(),
              semanticFormatterCallback: (v) =>
                  '${v.round()} out of ${scaleMax.toInt()}',
              onChanged: (v) {
                setState(() {
                  _sliderValue = v;
                  _hasInteracted = true;
                });
              },
            ),

            // Endpoint labels
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                if (item.minLabel != null)
                  Flexible(
                    child: Text(
                      item.minLabel!,
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: Theme.of(context).colorScheme.outline,
                      ),
                      textAlign: TextAlign.left,
                    ),
                  ),
                if (item.maxLabel != null)
                  Flexible(
                    child: Text(
                      item.maxLabel!,
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: Theme.of(context).colorScheme.outline,
                      ),
                      textAlign: TextAlign.right,
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 8),

            // Current value display
            Center(
              child: Text(
                _hasInteracted ? _sliderValue.round().toString() : '—',
                style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                  color: Theme.of(context).colorScheme.primary,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            const SizedBox(height: 20),

            // Action buttons
            Row(
              children: [
                TextButton(onPressed: () => _skip(), child: const Text('Skip')),
                const Spacer(),
                FilledButton(
                  onPressed: _hasInteracted ? () => _submit() : null,
                  child: Text(
                    checkInState.currentStepIndex <
                            checkInState.items.length - 1
                        ? 'Next'
                        : 'Finish',
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildComplete(BuildContext context, CheckInState state) {
    return Card(
      margin: const EdgeInsets.all(12),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.check_circle_outline, size: 48),
            const SizedBox(height: 12),
            Text(
              'Check-in saved.',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            if (state.compositeScore != null) ...[
              const SizedBox(height: 8),
              Text(
                'Score: ${state.compositeScore!.toStringAsFixed(0)} / 100',
                style: Theme.of(context).textTheme.bodyLarge,
              ),
            ],
            const SizedBox(height: 8),
            Text(
              'That\'s enough.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.outline,
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _submit() {
    if (!_hasInteracted) return;
    final value = _sliderValue.round();
    ref
        .read(checkInProvider.notifier)
        .recordAnswer(sessionId: widget.sessionId, value: value);
    setState(() {
      _sliderValue = 5.0;
      _hasInteracted = false;
    });
  }

  void _skip() {
    ref
        .read(checkInProvider.notifier)
        .recordAnswer(sessionId: widget.sessionId, value: null);
    setState(() {
      _sliderValue = 5.0;
      _hasInteracted = false;
    });
  }
}
