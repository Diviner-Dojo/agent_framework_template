// coverage:ignore-file — interactive UI screen; covered by widget tests.
// ===========================================================================
// file: lib/ui/screens/check_in_history_screen.dart
// purpose: Check-In History Dashboard — interactive trend chart + chronological
//          cards for all Pulse Check-In responses.
//
// Layout:
//   - Top: _CheckInTrendChart — multi-line fl_chart with 6 series (one per
//     question), Last-5/Last-10/All filter toggle, horizontal scroll for
//     dense histories, tap-to-tooltip interaction.
//   - Bottom: scrollable list of _CheckInEntryCard (expandable detail cards).
//
// ADHD UX:
//   - No gap dates, no streak counters, no "last check-in" mentions.
//   - Neutral color palette (no red/green for scores).
//   - Chart is exploratory, not evaluative.
//
// Accessed via the insights icon (Icons.insights_outlined) in the home
// screen AppBar. The icon is hidden until at least one check-in exists.
//
// See: SPEC-20260302-adhd-informed-feature-roadmap.md Phase 3E.
// ===========================================================================

import 'dart:math';

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../database/app_database.dart';
import '../../providers/questionnaire_providers.dart';

/// Dashboard showing Pulse Check-In trend chart and history entries.
class CheckInHistoryScreen extends ConsumerWidget {
  const CheckInHistoryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final historyAsync = ref.watch(checkInHistoryProvider);
    final itemsAsync = ref.watch(activeCheckInItemsProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Check-In History')),
      body: historyAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('Error loading history: $e')),
        data: (entries) {
          if (entries.isEmpty) {
            return _buildEmpty(context);
          }
          final items = itemsAsync.valueOrNull ?? [];
          return Column(
            children: [
              _CheckInTrendChart(entries: entries, items: items),
              const Divider(height: 1),
              Expanded(
                child: ListView.builder(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  itemCount: entries.length,
                  itemBuilder: (context, index) {
                    return _CheckInEntryCard(entry: entries[index]);
                  },
                ),
              ),
            ],
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

// ---------------------------------------------------------------------------
// Trend Chart
// ---------------------------------------------------------------------------

/// Filter options for the trend chart time window.
enum _ChartFilter { last5, last10, all }

/// Interactive multi-line trend chart for Pulse Check-In history.
///
/// Renders one line per questionnaire item (up to 6), with a
/// Last-5 / Last-10 / All toggle and horizontal scrolling for
/// dense histories. Tap any data point for a full tooltip.
class _CheckInTrendChart extends StatefulWidget {
  /// All check-in history entries, newest-first (from [checkInHistoryProvider]).
  final List<CheckInHistoryEntry> entries;

  /// Active questionnaire items, sorted by sortOrder (for labels and order).
  final List<QuestionnaireItem> items;

  const _CheckInTrendChart({required this.entries, required this.items});

  @override
  State<_CheckInTrendChart> createState() => _CheckInTrendChartState();
}

class _CheckInTrendChartState extends State<_CheckInTrendChart> {
  _ChartFilter _filter = _ChartFilter.all;

  // Six perceptually-distinct hues derived from the app's teal-blue seed.
  // No red/green — ADHD clinical UX constraint (non-judgmental palette).
  static const _seriesColors = [
    Color(0xFF5B8A9A), // Teal-blue  — Mood
    Color(0xFF7A6E9E), // Muted violet — Energy
    Color(0xFF5E9E8A), // Sage green — Anxiety
    Color(0xFF9E8A5E), // Warm sand  — Focus
    Color(0xFF5E7A9E), // Slate blue — Emotion Reg.
    Color(0xFF9E6E7A), // Dusty rose — Sleep
  ];

  @override
  void didUpdateWidget(_CheckInTrendChart old) {
    super.didUpdateWidget(old);
    // Once 10+ check-ins accumulate, default the view to Last-10 so the
    // chart is dense enough to show patterns without being noisy.
    if (old.entries.length < 10 &&
        widget.entries.length >= 10 &&
        _filter == _ChartFilter.all) {
      _filter = _ChartFilter.last10;
    }
  }

  /// Chronologically ordered entries for the active filter.
  ///
  /// The provider emits newest-first; we reverse to oldest-first so the
  /// chart's X axis reads left = past, right = present.
  List<CheckInHistoryEntry> get _filteredEntries {
    final chrono = widget.entries.reversed.toList();
    final n = chrono.length;
    return switch (_filter) {
      _ChartFilter.last5 => n > 5 ? chrono.sublist(n - 5) : chrono,
      _ChartFilter.last10 => n > 10 ? chrono.sublist(n - 10) : chrono,
      _ChartFilter.all => chrono,
    };
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final entries = _filteredEntries;

    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          _buildHeader(theme),
          const SizedBox(height: 12),
          if (entries.length < 2)
            _buildSparseState(theme)
          else ...[
            _buildChart(context, theme, entries),
            const SizedBox(height: 8),
            _buildLegend(theme),
          ],
        ],
      ),
    );
  }

  /// Header row: "Trends" label + Last-5/Last-10/All toggle.
  Widget _buildHeader(ThemeData theme) {
    final total = widget.entries.length;
    // Build only the segments that are relevant at the current count.
    final segments = <ButtonSegment<_ChartFilter>>[
      if (total >= 5)
        const ButtonSegment(value: _ChartFilter.last5, label: Text('5')),
      if (total >= 10)
        const ButtonSegment(value: _ChartFilter.last10, label: Text('10')),
      const ButtonSegment(value: _ChartFilter.all, label: Text('All')),
    ];

    return Row(
      children: [
        Text('Trends', style: theme.textTheme.titleSmall),
        const Spacer(),
        if (segments.length > 1)
          SegmentedButton<_ChartFilter>(
            style: SegmentedButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 10),
              visualDensity: VisualDensity.compact,
              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
            ),
            segments: segments,
            selected: {_filter},
            onSelectionChanged: (s) => setState(() => _filter = s.first),
          ),
      ],
    );
  }

  /// Sparse-data state shown when fewer than 2 check-ins exist.
  Widget _buildSparseState(ThemeData theme) {
    return SizedBox(
      height: 120,
      child: Center(
        child: Text(
          'Complete more check-ins to see trends.',
          style: theme.textTheme.bodySmall?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
          textAlign: TextAlign.center,
        ),
      ),
    );
  }

  /// The main LineChart inside a horizontally-scrollable container.
  ///
  /// Chart width = max(screen width, entries × 56 dp) so sparse histories
  /// fill the screen while dense ones can be scrolled.
  Widget _buildChart(
    BuildContext context,
    ThemeData theme,
    List<CheckInHistoryEntry> entries,
  ) {
    final screenWidth = MediaQuery.of(context).size.width - 32;
    final chartWidth = max(screenWidth, entries.length * 56.0);

    return SizedBox(
      height: 200,
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: SizedBox(
          width: chartWidth,
          child: LineChart(
            _buildChartData(theme, entries),
            duration: const Duration(milliseconds: 400),
            curve: Curves.easeInOut,
          ),
        ),
      ),
    );
  }

  /// Build the [LineChartData] from the filtered entries.
  LineChartData _buildChartData(
    ThemeData theme,
    List<CheckInHistoryEntry> entries,
  ) {
    final items = widget.items;

    // One LineChartBarData per questionnaire item.
    final lineBars = items.asMap().entries.map((e) {
      final itemIdx = e.key;
      final item = e.value;
      final color = _seriesColors[itemIdx % _seriesColors.length];

      final spots = <FlSpot>[];
      for (var ei = 0; ei < entries.length; ei++) {
        final answers = entries[ei].answers;
        for (final a in answers) {
          if (a.itemId == item.id && a.value != null) {
            spots.add(FlSpot(ei.toDouble(), a.value!.toDouble()));
            break;
          }
        }
      }

      return LineChartBarData(
        spots: spots,
        isCurved: spots.length > 2,
        curveSmoothness: 0.3,
        preventCurveOverShooting: true,
        color: color,
        barWidth: 2.5,
        isStrokeCapRound: true,
        dotData: FlDotData(
          show: entries.length <= 6,
          getDotPainter: (spot, percent, bar, index) => FlDotCirclePainter(
            radius: 4,
            color: color,
            strokeWidth: 1.5,
            strokeColor: Colors.white,
          ),
        ),
        belowBarData: BarAreaData(show: false),
      );
    }).toList();

    final outlineVariant = theme.colorScheme.outlineVariant;

    return LineChartData(
      minY: 1,
      maxY: 10,
      lineBarsData: lineBars,
      titlesData: FlTitlesData(
        topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
        rightTitles: const AxisTitles(
          sideTitles: SideTitles(showTitles: false),
        ),
        leftTitles: AxisTitles(
          sideTitles: SideTitles(
            showTitles: true,
            reservedSize: 24,
            interval: 3,
            getTitlesWidget: (value, meta) {
              final v = value.toInt();
              if (v == 1 || v == 4 || v == 7 || v == 10) {
                return Text(
                  v.toString(),
                  style: theme.textTheme.labelSmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                );
              }
              return const SizedBox.shrink();
            },
          ),
        ),
        bottomTitles: AxisTitles(
          sideTitles: SideTitles(
            showTitles: true,
            reservedSize: 28,
            getTitlesWidget: (value, meta) {
              final idx = value.toInt();
              if (idx < 0 || idx >= entries.length) {
                return const SizedBox.shrink();
              }
              // Show a label every N entries to avoid crowding.
              final step = max(1, (entries.length / 5.0).ceil());
              if (idx % step != 0 && idx != entries.length - 1) {
                return const SizedBox.shrink();
              }
              final dt = entries[idx].response.completedAt.toLocal();
              return Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  _formatDateShort(dt),
                  style: theme.textTheme.labelSmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              );
            },
          ),
        ),
      ),
      gridData: FlGridData(
        show: true,
        drawVerticalLine: false,
        horizontalInterval: 1,
        getDrawingHorizontalLine: (value) => FlLine(
          color: outlineVariant.withValues(alpha: 0.35),
          strokeWidth: 0.8,
          // Solid midline at 5; dashed for all others.
          dashArray: value == 5 ? null : [4, 6],
        ),
      ),
      borderData: FlBorderData(show: false),
      lineTouchData: LineTouchData(
        handleBuiltInTouches: true,
        touchTooltipData: LineTouchTooltipData(
          getTooltipColor: (_) => theme.colorScheme.inverseSurface,
          getTooltipItems: (touchedSpots) {
            return touchedSpots.map((spot) {
              final barIdx = spot.barIndex;
              final entryIdx = spot.x.toInt();
              if (entryIdx < 0 || entryIdx >= entries.length) return null;

              final color = _seriesColors[barIdx % _seriesColors.length];
              final entry = entries[entryIdx];
              final valueStr = spot.y.toInt().toString();
              final label = barIdx < items.length
                  ? _shortLabel(items[barIdx].questionText)
                  : 'Q${barIdx + 1}';

              if (barIdx == 0) {
                // First bar: prepend date + composite score.
                final dt = entry.response.completedAt.toLocal();
                final score = entry.response.compositeScore;
                final scoreStr = score != null
                    ? ' · ${score.toStringAsFixed(0)}/100'
                    : '';
                return LineTooltipItem(
                  '${_formatDate(dt)}$scoreStr\n',
                  TextStyle(
                    color: theme.colorScheme.onInverseSurface,
                    fontWeight: FontWeight.bold,
                    fontSize: 11,
                  ),
                  children: [
                    TextSpan(
                      text: '$label: $valueStr',
                      style: TextStyle(
                        color: color,
                        fontWeight: FontWeight.normal,
                        fontSize: 11,
                      ),
                    ),
                  ],
                );
              }

              return LineTooltipItem(
                '$label: $valueStr',
                TextStyle(color: color, fontSize: 11),
              );
            }).toList();
          },
        ),
      ),
    );
  }

  /// Colored legend row: one swatch + short label per item.
  Widget _buildLegend(ThemeData theme) {
    return Wrap(
      spacing: 14,
      runSpacing: 4,
      children: widget.items.asMap().entries.map((e) {
        final color = _seriesColors[e.key % _seriesColors.length];
        return Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 14,
              height: 3,
              decoration: BoxDecoration(
                color: color,
                borderRadius: BorderRadius.circular(1.5),
              ),
            ),
            const SizedBox(width: 4),
            Text(
              _shortLabel(e.value.questionText),
              style: theme.textTheme.labelSmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        );
      }).toList(),
    );
  }
}

// ---------------------------------------------------------------------------
// History Cards
// ---------------------------------------------------------------------------

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
// Short label extraction (for chart legend and tooltips)
// ---------------------------------------------------------------------------

/// Extract a short human-readable label from a question text.
///
/// Maps known keyword patterns to concise labels. Falls back to truncation.
String _shortLabel(String questionText) {
  final lower = questionText.toLowerCase();
  if (lower.contains('mood')) return 'Mood';
  if (lower.contains('energy')) return 'Energy';
  if (lower.contains('anxi') || lower.contains('worr')) return 'Anxiety';
  if (lower.contains('focus') || lower.contains('concentrat')) return 'Focus';
  if (lower.contains('emotion') || lower.contains('managing'))
    return 'Emotions';
  if (lower.contains('sleep')) return 'Sleep';
  // Fallback: first 10 chars.
  return questionText.length > 10
      ? '${questionText.substring(0, 10)}…'
      : questionText;
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

/// Format a local DateTime as "Mar 4" (short, for chart X axis).
String _formatDateShort(DateTime local) =>
    '${_months[local.month - 1]} ${local.day}';

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
