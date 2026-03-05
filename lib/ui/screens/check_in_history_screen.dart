// coverage:ignore-file — interactive UI screen; covered by widget tests.
// ===========================================================================
// file: lib/ui/screens/check_in_history_screen.dart
// purpose: Check-In History Dashboard — interactive trend chart + chronological
//          cards for all Pulse Check-In responses, plus Phase 4E Trend tab.
//
// Layout:
//   Two tabs (shown when entries exist):
//   - History: _CheckInTrendChart + scrollable _CheckInEntryCard list.
//   - Trends: _CheckInTrendTab — rolling averages, correlation tiles, insights.
//
// ADHD UX:
//   - No gap dates, no streak counters, no "last check-in" mentions.
//   - Neutral color palette (no red/green for scores).
//   - Chart is exploratory, not evaluative.
//   - Correlation framing: "possible relationship", never causal.
//
// Accessed via the insights icon (Icons.insights_outlined) in the home
// screen AppBar. The icon is hidden until at least one check-in exists.
//
// See: SPEC-20260302-adhd-informed-feature-roadmap.md Phase 3E + Phase 4E.
// ===========================================================================

import 'dart:math';

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../database/app_database.dart';
import '../../providers/check_in_trend_provider.dart';
import '../../providers/questionnaire_providers.dart';
import '../../services/correlation_service.dart';

/// Dashboard showing Pulse Check-In trend chart and history entries.
class CheckInHistoryScreen extends ConsumerWidget {
  const CheckInHistoryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final historyAsync = ref.watch(checkInHistoryProvider);
    final itemsAsync = ref.watch(activeCheckInItemsProvider);

    return historyAsync.when(
      loading: () => Scaffold(
        appBar: AppBar(title: const Text('Check-In History')),
        body: const Center(child: CircularProgressIndicator()),
      ),
      error: (e, _) => Scaffold(
        appBar: AppBar(title: const Text('Check-In History')),
        body: Center(child: Text('Error loading history: $e')),
      ),
      data: (entries) {
        if (entries.isEmpty) {
          return Scaffold(
            appBar: AppBar(title: const Text('Check-In History')),
            body: _buildEmpty(context),
          );
        }
        final items = itemsAsync.valueOrNull ?? [];
        return DefaultTabController(
          length: 2,
          child: Scaffold(
            appBar: AppBar(
              title: const Text('Check-In History'),
              bottom: const TabBar(
                tabs: [
                  Tab(text: 'History'),
                  Tab(text: 'Trends'),
                ],
              ),
            ),
            body: TabBarView(
              children: [
                // History tab: existing chart + chronological list.
                Column(
                  children: [
                    _CheckInTrendChart(entries: entries, items: items),
                    const Divider(height: 1),
                    Expanded(
                      child: ListView.builder(
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        itemCount: entries.length,
                        itemBuilder: (context, index) =>
                            _CheckInEntryCard(entry: entries[index]),
                      ),
                    ),
                  ],
                ),
                // Trends tab: Phase 4E rolling averages + correlations.
                const _CheckInTrendTab(),
              ],
            ),
          ),
        );
      },
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

/// Filter options for the history chart time window.
enum _ChartFilter { last5, last10, all }

/// Window options for the Phase 4E rolling-averages chart.
enum _TrendWindow { days7, days14, days30 }

extension _TrendWindowX on _TrendWindow {
  int get days => switch (this) {
    _TrendWindow.days7 => 7,
    _TrendWindow.days14 => 14,
    _TrendWindow.days30 => 30,
  };

  String get label => switch (this) {
    _TrendWindow.days7 => '7 days',
    _TrendWindow.days14 => '14 days',
    _TrendWindow.days30 => '30 days',
  };
}

/// Shared perceptually-distinct hues (no red/green — ADHD non-judgmental palette).
const _kSeriesColors = [
  Color(0xFF5B8A9A), // Teal-blue    — Mood
  Color(0xFF7A6E9E), // Muted violet — Energy
  Color(0xFF5E9E8A), // Sage green   — Anxiety
  Color(0xFF9E8A5E), // Warm sand    — Focus
  Color(0xFF5E7A9E), // Slate blue   — Emotion Reg.
  Color(0xFF9E6E7A), // Dusty rose   — Sleep
];

/// One calendar day's averaged Pulse Check-In data.
///
/// When multiple check-ins fall on the same day, their per-item values and
/// composite scores are averaged so the chart shows exactly one point per day.
class _DayAverage {
  /// Representative local date for this day (from the first entry of the day).
  final DateTime date;

  /// Average answer value per item id. Null when all answers were skipped.
  final Map<int, double?> itemAverages;

  /// Average composite score across all check-ins on this day.
  final double? compositeScore;

  /// Number of check-ins merged into this day's average.
  final int entryCount;

  const _DayAverage({
    required this.date,
    required this.itemAverages,
    required this.compositeScore,
    required this.entryCount,
  });
}

/// Interactive multi-line trend chart for Pulse Check-In history.
///
/// Multiple check-ins on the same calendar day are averaged into a single
/// data point per day. Renders one line per questionnaire item (up to 6),
/// with a Last-5 / Last-10 / All toggle (in days) and horizontal scrolling
/// for dense histories. Tap any data point for a full tooltip.
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

  // Reuses module-level _kSeriesColors (ADHD non-judgmental palette).

  @override
  void didUpdateWidget(_CheckInTrendChart old) {
    super.didUpdateWidget(old);
    // Once 10+ unique days accumulate, default to Last-10 days.
    final oldDays = _computeDailyAverages(old.entries.reversed.toList()).length;
    final newDays = _computeDailyAverages(
      widget.entries.reversed.toList(),
    ).length;
    if (oldDays < 10 && newDays >= 10 && _filter == _ChartFilter.all) {
      _filter = _ChartFilter.last10;
    }
  }

  /// Aggregate all entries into one [_DayAverage] per calendar day.
  ///
  /// Entries must be in chronological order (oldest first).
  /// Groups by local "YYYY-MM-DD" key, then averages per-item values and
  /// composite scores within each group.
  List<_DayAverage> _computeDailyAverages(List<CheckInHistoryEntry> chrono) {
    final byDay = <String, List<CheckInHistoryEntry>>{};
    for (final e in chrono) {
      final local = e.response.completedAt.toLocal();
      final key =
          '${local.year}-'
          '${local.month.toString().padLeft(2, '0')}-'
          '${local.day.toString().padLeft(2, '0')}';
      byDay.putIfAbsent(key, () => []).add(e);
    }

    final sortedKeys = byDay.keys.toList()..sort();
    return sortedKeys.map((key) {
      final dayEntries = byDay[key]!;
      final date = dayEntries.first.response.completedAt.toLocal();

      // Collect all item ids seen on this day.
      final itemIds = <int>{};
      for (final e in dayEntries) {
        for (final a in e.answers) {
          itemIds.add(a.itemId);
        }
      }

      // Average the non-null values per item.
      final itemAverages = <int, double?>{};
      for (final itemId in itemIds) {
        final values = <int>[];
        for (final e in dayEntries) {
          for (final a in e.answers) {
            if (a.itemId == itemId && a.value != null) {
              values.add(a.value!);
            }
          }
        }
        itemAverages[itemId] = values.isEmpty
            ? null
            : values.reduce((a, b) => a + b) / values.length;
      }

      // Average composite scores.
      final scores = dayEntries
          .map((e) => e.response.compositeScore)
          .whereType<double>()
          .toList();
      final avgScore = scores.isEmpty
          ? null
          : scores.reduce((a, b) => a + b) / scores.length;

      return _DayAverage(
        date: date,
        itemAverages: itemAverages,
        compositeScore: avgScore,
        entryCount: dayEntries.length,
      );
    }).toList();
  }

  /// Daily averages for the active filter window.
  List<_DayAverage> get _filteredDays {
    final allDays = _computeDailyAverages(widget.entries.reversed.toList());
    final n = allDays.length;
    return switch (_filter) {
      _ChartFilter.last5 => n > 5 ? allDays.sublist(n - 5) : allDays,
      _ChartFilter.last10 => n > 10 ? allDays.sublist(n - 10) : allDays,
      _ChartFilter.all => allDays,
    };
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final days = _filteredDays;

    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          _buildHeader(theme),
          const SizedBox(height: 12),
          if (days.length < 2)
            _buildSparseState(theme)
          else ...[
            _buildChart(context, theme, days),
            const SizedBox(height: 8),
            _buildLegend(theme),
          ],
        ],
      ),
    );
  }

  /// Header row: "Trends" label + Last-5/Last-10/All toggle (in days).
  Widget _buildHeader(ThemeData theme) {
    final totalDays = _computeDailyAverages(
      widget.entries.reversed.toList(),
    ).length;
    final segments = <ButtonSegment<_ChartFilter>>[
      if (totalDays >= 5)
        const ButtonSegment(value: _ChartFilter.last5, label: Text('5 days')),
      if (totalDays >= 10)
        const ButtonSegment(value: _ChartFilter.last10, label: Text('10 days')),
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
              // tapTargetSize intentionally omitted to restore the default
              // MaterialTapTargetSize.padded (48dp minimum) per Material spec.
              // shrinkWrap was previously here but reduced tap targets below
              // accessible minimums (REV-20260304-015709-A5).
            ),
            segments: segments,
            selected: {_filter},
            onSelectionChanged: (s) => setState(() => _filter = s.first),
          ),
      ],
    );
  }

  /// Sparse-data state: shown when fewer than 2 distinct days exist.
  Widget _buildSparseState(ThemeData theme) {
    return SizedBox(
      height: 120,
      child: Center(
        child: Text(
          'Complete check-ins on 2 or more days to see trends.',
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
  /// Chart width = max(screen width, days × 56 dp).
  Widget _buildChart(
    BuildContext context,
    ThemeData theme,
    List<_DayAverage> days,
  ) {
    final screenWidth = MediaQuery.of(context).size.width - 32;
    final chartWidth = max(screenWidth, days.length * 56.0);

    return SizedBox(
      height: 200,
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: SizedBox(
          width: chartWidth,
          child: LineChart(
            _buildChartData(theme, days),
            duration: const Duration(milliseconds: 400),
            curve: Curves.easeInOut,
          ),
        ),
      ),
    );
  }

  /// Build [LineChartData] from daily-averaged data.
  LineChartData _buildChartData(ThemeData theme, List<_DayAverage> days) {
    final items = widget.items;

    // One line per questionnaire item, one point per day.
    final lineBars = items.asMap().entries.map((e) {
      final itemIdx = e.key;
      final item = e.value;
      final color = _kSeriesColors[itemIdx % _kSeriesColors.length];

      final spots = <FlSpot>[];
      for (var di = 0; di < days.length; di++) {
        final avg = days[di].itemAverages[item.id];
        if (avg != null) {
          spots.add(FlSpot(di.toDouble(), avg));
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
          show: days.length <= 6,
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
            // reservedSize: 36 accommodates 'High' (4 chars) at elevated text
            // scales; 24 would clip at 200% accessibility scale (REV-20260305-190054-A6-NEW).
            reservedSize: 36,
            interval: 3,
            getTitlesWidget: (value, meta) {
              // Two orientation anchors: Low(1) and High(10).
              // 'Mid' omitted — interval:3 places the nearest tick at 7/10
              // (67th percentile), which would misrepresent the scale midpoint
              // to users (REV-20260305-190054-A4-NEW; inline fix REV-20260305-192424).
              final label = switch (value.toInt()) {
                1 => 'Low',
                10 => 'High',
                _ => null,
              };
              if (label == null) return const SizedBox.shrink();
              return Text(
                label,
                style: theme.textTheme.labelSmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              );
            },
          ),
        ),
        bottomTitles: AxisTitles(
          sideTitles: SideTitles(
            showTitles: true,
            reservedSize: 36,
            getTitlesWidget: (value, meta) {
              final idx = value.toInt();
              if (idx < 0 || idx >= days.length) {
                return const SizedBox.shrink();
              }
              // Show a label every N days to avoid crowding.
              final step = max(1, (days.length / 5.0).ceil());
              if (idx % step != 0 && idx != days.length - 1) {
                return const SizedBox.shrink();
              }
              // Cap textScaler to noScaling so date labels don't overflow
              // reservedSize: 36 at 200% system text scale (UX-A3).
              return MediaQuery(
                data: MediaQuery.of(
                  context,
                ).copyWith(textScaler: TextScaler.noScaling),
                child: Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                    _formatDateShort(days[idx].date),
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
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
              final dayIdx = spot.x.toInt();
              if (dayIdx < 0 || dayIdx >= days.length) return null;

              final color = _kSeriesColors[barIdx % _kSeriesColors.length];
              final day = days[dayIdx];
              final label = barIdx < items.length
                  ? _shortLabel(items[barIdx].questionText)
                  : 'Q${barIdx + 1}';

              // Format value: integer for single entry, 1-decimal for averages.
              final valueStr = day.entryCount > 1
                  ? spot.y.toStringAsFixed(1)
                  : spot.y.toInt().toString();

              if (barIdx == 0) {
                // First bar: show date, avg composite score, entry count.
                final score = day.compositeScore;
                final scoreStr = score != null
                    ? ' · ${score.toStringAsFixed(0)}/100'
                    : '';
                final countStr = day.entryCount > 1
                    ? ' (${day.entryCount} check-ins)'
                    : '';
                return LineTooltipItem(
                  '${_formatDate(day.date)}$scoreStr$countStr\n',
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

  /// Colored legend: one swatch + short label per item.
  Widget _buildLegend(ThemeData theme) {
    return Wrap(
      spacing: 14,
      runSpacing: 4,
      children: widget.items.asMap().entries.map((e) {
        final color = _kSeriesColors[e.key % _kSeriesColors.length];
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
// Phase 4E: Trend Tab — rolling averages, correlations, insights
// ---------------------------------------------------------------------------

/// Full-screen trend analysis tab for Phase 4E.
///
/// Consumes [checkInTrendProvider] (rolling-averaged + correlated data) and
/// presents three sections:
///   1. Rolling averages line chart (configurable 7/14/30-day window).
///   2. Dimension correlations — pairs sorted by |r| with directional tint.
///   3. Plain-language narrative insights with epistemic humility framing.
///
/// ADHD UX: no "best/worst day" labelling; no causal claims;
/// "possible relationship" language; missing-data warnings.
class _CheckInTrendTab extends ConsumerStatefulWidget {
  const _CheckInTrendTab();

  @override
  ConsumerState<_CheckInTrendTab> createState() => _CheckInTrendTabState();
}

class _CheckInTrendTabState extends ConsumerState<_CheckInTrendTab> {
  _TrendWindow _window = _TrendWindow.days7;

  @override
  Widget build(BuildContext context) {
    final trendAsync = ref.watch(checkInTrendProvider);
    return trendAsync.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('Could not load trends: $e')),
      data: (data) {
        if (!data.hasSufficientData) {
          return _buildInsufficient(context);
        }
        final svc = ref.read(correlationServiceProvider);
        return SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildWindowToggle(context),
              const SizedBox(height: 16),
              _buildRollingSection(context, svc, data),
              const SizedBox(height: 20),
              _buildCorrelationSection(context, data),
              const SizedBox(height: 20),
              _buildInsightsSection(context, data),
            ],
          ),
        );
      },
    );
  }

  Widget _buildInsufficient(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Text(
          'Complete check-ins on 2 or more days to see trend analysis.',
          style: theme.textTheme.bodyMedium?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
          textAlign: TextAlign.center,
        ),
      ),
    );
  }

  // ---- Window toggle -------------------------------------------------------

  Widget _buildWindowToggle(BuildContext context) {
    final theme = Theme.of(context);
    return Row(
      children: [
        Text('Rolling window', style: theme.textTheme.titleSmall),
        const Spacer(),
        SegmentedButton<_TrendWindow>(
          style: SegmentedButton.styleFrom(
            padding: const EdgeInsets.symmetric(horizontal: 8),
            visualDensity: VisualDensity.compact,
          ),
          segments: _TrendWindow.values
              .map((w) => ButtonSegment(value: w, label: Text(w.label)))
              .toList(),
          selected: {_window},
          onSelectionChanged: (s) => setState(() => _window = s.first),
        ),
      ],
    );
  }

  // ---- Rolling averages chart ----------------------------------------------

  Widget _buildRollingSection(
    BuildContext context,
    CorrelationService svc,
    CheckInTrendData data,
  ) {
    final theme = Theme.of(context);

    // Compute rolling averages for each dimension.
    final rollingByItem = {
      for (final id in data.itemIds)
        id: svc.rollingAverages(
          days: data.days,
          itemId: id,
          windowDays: _window.days,
        ),
    };

    final hasValues = rollingByItem.values.any(
      (pts) => pts.any((p) => p.value != null),
    );

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Rolling averages', style: theme.textTheme.titleSmall),
        Text(
          'Chart scaled to your own range — top of chart is your personal highest',
          style: theme.textTheme.bodySmall?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 8),
        if (!hasValues)
          SizedBox(
            height: 80,
            child: Center(
              child: Text(
                'More check-ins needed for rolling averages.',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ),
          )
        else
          _buildRollingChart(theme, data, rollingByItem),
        const SizedBox(height: 6),
        _buildLegend(theme, data),
      ],
    );
  }

  Widget _buildRollingChart(
    ThemeData theme,
    CheckInTrendData data,
    Map<int, List<RollingPoint>> rollingByItem,
  ) {
    final outlineVariant = theme.colorScheme.outlineVariant;
    final days = data.days;

    final lineBars = data.itemIds.asMap().entries.map((e) {
      final idx = e.key;
      final itemId = e.value;
      final color = _kSeriesColors[idx % _kSeriesColors.length];
      final points = rollingByItem[itemId] ?? [];

      final spots = <FlSpot>[
        for (var i = 0; i < points.length; i++)
          if (points[i].value != null) FlSpot(i.toDouble(), points[i].value!),
      ];

      return LineChartBarData(
        spots: spots,
        isCurved: spots.length > 2,
        curveSmoothness: 0.3,
        preventCurveOverShooting: true,
        color: color,
        barWidth: 2.5,
        isStrokeCapRound: true,
        dotData: FlDotData(show: days.length <= 6),
        belowBarData: BarAreaData(show: false),
      );
    }).toList();

    return SizedBox(
      height: 180,
      child: LineChart(
        LineChartData(
          minY: 0,
          maxY: 1,
          lineBarsData: lineBars,
          titlesData: FlTitlesData(
            topTitles: const AxisTitles(
              sideTitles: SideTitles(showTitles: false),
            ),
            rightTitles: const AxisTitles(
              sideTitles: SideTitles(showTitles: false),
            ),
            leftTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                // reservedSize: 36 accommodates 'High' (4 chars) at elevated text
                // scales (REV-20260305-190054-A6-NEW).
                reservedSize: 36,
                interval: 0.5,
                getTitlesWidget: (v, _) {
                  final label = switch (v) {
                    0.0 => 'Low',
                    0.5 => 'Mid',
                    1.0 => 'High',
                    _ => null,
                  };
                  if (label == null) return const SizedBox.shrink();
                  return Text(
                    label,
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  );
                },
              ),
            ),
            bottomTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 36,
                getTitlesWidget: (value, _) {
                  final idx = value.toInt();
                  if (idx < 0 || idx >= days.length) {
                    return const SizedBox.shrink();
                  }
                  final step = max(1, (days.length / 5.0).ceil());
                  if (idx % step != 0 && idx != days.length - 1) {
                    return const SizedBox.shrink();
                  }
                  // Cap textScaler to noScaling so date labels don't overflow
                  // reservedSize: 36 at 200% system text scale (UX-A3).
                  return MediaQuery(
                    data: MediaQuery.of(
                      context,
                    ).copyWith(textScaler: TextScaler.noScaling),
                    child: Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Text(
                        _formatDateShort(days[idx].date),
                        style: theme.textTheme.labelSmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
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
            horizontalInterval: 0.5,
            getDrawingHorizontalLine: (v) => FlLine(
              color: outlineVariant.withValues(alpha: 0.35),
              strokeWidth: 0.8,
              dashArray: v == 0.5 ? null : [4, 6],
            ),
          ),
          borderData: FlBorderData(show: false),
        ),
        duration: const Duration(milliseconds: 400),
        curve: Curves.easeInOut,
      ),
    );
  }

  Widget _buildLegend(ThemeData theme, CheckInTrendData data) {
    return Wrap(
      spacing: 14,
      runSpacing: 4,
      children: data.itemIds.asMap().entries.map((e) {
        final color = _kSeriesColors[e.key % _kSeriesColors.length];
        final label = _shortLabel(data.itemText[e.value] ?? 'Q${e.value}');
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
              label,
              style: theme.textTheme.labelSmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        );
      }).toList(),
    );
  }

  // ---- Correlation tiles ---------------------------------------------------

  Widget _buildCorrelationSection(BuildContext context, CheckInTrendData data) {
    final theme = Theme.of(context);
    final withR = data.correlations.where((c) => c.r != null).toList()
      ..sort((a, b) => b.r!.abs().compareTo(a.r!.abs()));

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Dimension correlations', style: theme.textTheme.titleSmall),
        const SizedBox(height: 8),
        if (withR.isEmpty)
          Text(
            'Correlations appear after 5 or more days with data for the same dimensions.',
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          )
        else
          ...withR.map((c) => _buildCorrelationTile(theme, c, data.itemText)),
      ],
    );
  }

  Widget _buildCorrelationTile(
    ThemeData theme,
    DimensionCorrelation c,
    Map<int, String> itemText,
  ) {
    final r = c.r!;
    final absR = r.abs();
    final isPositive = r >= 0;

    // Warm sand for positive (move together), slate blue for negative (move
    // apart). Opacity scales with |r|. Avoids red/green (ADHD-safe).
    final tint = isPositive
        ? const Color(0xFF9E8A5E) // warm sand
        : const Color(0xFF5E7A9E); // slate blue
    final bg = tint.withValues(alpha: (absR * 0.3).clamp(0.05, 0.3));

    final labelA = _shortLabel(itemText[c.itemIdA] ?? 'A');
    final labelB = _shortLabel(itemText[c.itemIdB] ?? 'B');
    final strength = absR >= 0.7
        ? 'strong'
        : absR >= 0.4
        ? 'moderate'
        : 'weak';
    final direction = isPositive ? 'together' : 'opposite';

    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: tint.withValues(alpha: 0.3), width: 0.5),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '$labelA & $labelB',
                    style: theme.textTheme.bodySmall?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  Text(
                    '$strength, move $direction — ${c.pairedCount} days',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
            Icon(
              isPositive ? Icons.trending_up : Icons.trending_down,
              color: tint,
              size: 20,
            ),
          ],
        ),
      ),
    );
  }

  // ---- Narrative insights --------------------------------------------------

  Widget _buildInsightsSection(BuildContext context, CheckInTrendData data) {
    final theme = Theme.of(context);
    if (data.insights.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Insights', style: theme.textTheme.titleSmall),
        const SizedBox(height: 8),
        ...data.insights.map((i) => _buildInsightCard(theme, i)),
      ],
    );
  }

  Widget _buildInsightCard(ThemeData theme, TrendInsight insight) {
    final isWarning = insight.hasMissingDataWarning;
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: isWarning
            ? theme.colorScheme.tertiaryContainer.withValues(alpha: 0.5)
            : theme.colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            isWarning ? Icons.info_outline : Icons.bar_chart_outlined,
            size: 16,
            color: isWarning
                ? theme.colorScheme.tertiary
                : theme.colorScheme.onSurfaceVariant,
          ),
          const SizedBox(width: 8),
          Expanded(child: Text(insight.text, style: theme.textTheme.bodySmall)),
        ],
      ),
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
///
/// **Asymmetry with [CorrelationService.normalizeAnswer]**: This screen-side
/// function returns 0.0 for a degenerate range; `CorrelationService.normalizeAnswer`
/// returns 0.5 for the same case. This is intentional:
///   - 0.0 here prevents a chart point from appearing at the midpoint for
///     degenerate data (a bar at 50% would mislead the user into thinking a
///     real value was recorded).
///   - 0.5 in the service is neutral for Pearson r computation (placing the
///     degenerate dimension at the centre of the correlation space avoids
///     artificially inflating or deflating correlations).
/// Do not unify these — they serve different consumers (ADR-0033 §A7 note).
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
  if (lower.contains('emotion') || lower.contains('managing')) {
    return 'Emotions';
  }
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
