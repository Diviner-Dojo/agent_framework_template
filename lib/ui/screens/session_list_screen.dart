// ===========================================================================
// file: lib/ui/screens/session_list_screen.dart
// purpose: Home screen — displays a paginated list of past journal sessions
//          grouped by month-year with sticky headers.
//
// This is the first screen the user sees when opening the app.
// Sessions are sorted by date (newest first), grouped by month-year,
// with a "Load older entries" button at the bottom for pagination.
//
// Uses paginatedSessionsProvider (a StreamProvider) for reactive updates.
// ===========================================================================

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../database/app_database.dart';
import '../../database/daos/calendar_event_dao.dart';
import '../../providers/calendar_providers.dart';
import '../../providers/database_provider.dart';
import '../../providers/photo_providers.dart';
import '../../providers/search_providers.dart';
import '../../providers/questionnaire_providers.dart';
import '../../providers/reminder_providers.dart';
import '../../providers/resurfacing_providers.dart';
import '../../providers/session_providers.dart';
import '../../providers/weekly_digest_providers.dart';
import '../../services/reminder_service.dart';
import '../../services/weekly_digest_service.dart';
import '../../providers/task_providers.dart';
import '../../services/google_calendar_service.dart';
import '../../providers/last_capture_mode_provider.dart';
import '../../providers/voice_providers.dart';
import '../widgets/quick_capture_palette.dart';
import '../widgets/quick_mood_tap_sheet.dart';
import '../widgets/session_card.dart';

/// Home screen showing all past journal sessions with month-year grouping.
class SessionListScreen extends ConsumerStatefulWidget {
  const SessionListScreen({super.key});

  @override
  ConsumerState<SessionListScreen> createState() => _SessionListScreenState();
}

class _SessionListScreenState extends ConsumerState<SessionListScreen> {
  bool _isStarting = false;
  Map<String, int> _messageCounts = {};
  List<String>? _lastSessionIds;

  @override
  Widget build(BuildContext context) {
    // Watch the paginated stream of sessions for reactive updates.
    final sessionsAsync = ref.watch(paginatedSessionsProvider);

    // Phase 4B: Quick Capture widget launch — dispatch to the stored mode.
    // pendingWidgetLaunchModeProvider is set by app.dart when the app is
    // opened from the home screen widget. We consume it here (clear + dispatch)
    // so it only fires once even if the build method is called again.
    ref.listen(pendingWidgetLaunchModeProvider, (previous, next) {
      if (next == null) return;
      // Allowlist guard: reject unknown mode strings (Intent extra injection
      // protection — any on-device app can send a crafted Intent to the
      // exported MainActivity with an arbitrary mode value).
      const validWidgetModes = {
        'text',
        'voice',
        '__quick_mood_tap__',
        'pulse_check_in',
      };
      if (!validWidgetModes.contains(next)) {
        // Clear the invalid value so it does not linger in state.
        ref.read(pendingWidgetLaunchModeProvider.notifier).state = null;
        return;
      }
      // Clear before dispatching to prevent double-fire on rebuild.
      ref.read(pendingWidgetLaunchModeProvider.notifier).state = null;
      WidgetsBinding.instance.addPostFrameCallback((_) async {
        if (!mounted) return;
        await ref.read(lastCaptureModeProvider.notifier).setMode(next);
        if (!mounted) return;
        await _dispatchCaptureMode(context, next);
      });
    });

    return Scaffold(
      appBar: AppBar(
        title: const Text('Agentic Journal'),
        actions: [
          // Tasks icon — visible when tasks exist.
          _TasksIconButton(),
          // Gallery icon — visible when photos exist.
          _GalleryIconButton(),
          // Check-In History icon — visible after first completed check-in.
          _CheckInHistoryIconButton(),
          // Search icon — visible at 5+ sessions (progressive disclosure).
          _SearchIconButton(),
          // Settings gear icon — opens the settings screen.
          IconButton(
            icon: const Icon(Icons.settings),
            tooltip: 'Settings',
            onPressed: () => Navigator.of(context).pushNamed('/settings'),
          ),
        ],
      ),
      body: sessionsAsync.when(
        data: (sessions) {
          if (sessions.isEmpty) {
            return _buildEmptyState(context);
          }
          // Batch-load message counts when the session list changes.
          _refreshMessageCounts(sessions);

          // Phase 2B — Quick Check-In CTA: show a universally-visible card
          // offering the check-in as a session entry point.
          // ADHD UX: shown to ALL users with sessions (not conditioned on gap
          // duration) to avoid implicit gap-shaming. Dismissal is persisted
          // at app level (not widget-local) via quickCheckInBannerDismissedProvider
          // so Back navigation does not re-escalate the banner.
          // See: REV-20260303-142206 B1/B2.
          final bannerDismissed = ref.watch(
            quickCheckInBannerDismissedProvider,
          );

          // Phase 3C — resurfaced "Gift" card: show when a qualifying past
          // session exists in a spaced-repetition window. Hidden while the
          // FutureProvider loads (hasValue=false) and if none qualifies.
          final resurfacedAsync = ref.watch(resurfacedSessionProvider);

          // Phase 3D — weekly digest card: celebrates this week's captures.
          // Hidden while loading, if dismissed in the past 7 days, or if no
          // eligible sessions exist this week.
          final weeklyDigestAsync = ref.watch(weeklyDigestProvider);

          // Phase 4D — daily reminder card: gentle prompt to journal when the
          // user is in their configured time window and hasn't journaled today.
          final showReminder = ref.watch(dailyReminderVisibleProvider);

          // ADHD UX: show at most one passive-celebration card at a time.
          // Priority order: reminder > digest > gift.
          // The reminder card is action-oriented (start a session) and takes
          // priority. The weekly digest celebrates past captures. The gift
          // resurfaces a memory. Showing more than one violates the "one
          // entry at a time" ADHD spec principle.
          final showDigest =
              !showReminder &&
              weeklyDigestAsync.hasValue &&
              weeklyDigestAsync.value != null;
          final showGift =
              !showReminder &&
              !showDigest &&
              resurfacedAsync.hasValue &&
              resurfacedAsync.value != null;

          return Column(
            children: [
              if (!bannerDismissed) _buildRecoveryBanner(context),
              if (showReminder) _buildReminderCard(context),
              if (showDigest)
                _buildWeeklyDigestCard(context, weeklyDigestAsync.value!),
              if (showGift) _buildGiftCard(context, resurfacedAsync.value!),
              Expanded(child: _buildGroupedSessionList(context, ref, sessions)),
            ],
          );
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, stack) =>
            Center(child: Text('Error loading sessions: $error')),
      ),
      // FAB: tap to open the Quick Capture Palette (Phase 3A).
      // The palette presents five large mode tiles; the last-used mode is
      // pre-highlighted so repeat captures require zero mode-selection overhead.
      floatingActionButton: FloatingActionButton(
        onPressed: _isStarting ? null : () => _openQuickCapturePalette(context),
        tooltip: _isStarting ? 'Opening...' : 'New journal entry',
        child: _isStarting
            ? const SizedBox(
                width: 24,
                height: 24,
                child: CircularProgressIndicator(
                  strokeWidth: 2.5,
                  color: Colors.white,
                ),
              )
            : const Icon(Icons.add),
      ),
    );
  }

  /// Build the empty state shown when no sessions exist.
  Widget _buildEmptyState(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.book_outlined,
              size: 64,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
            const SizedBox(height: 16),
            Text(
              'No journal sessions yet',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Text(
              'Tap + to start your first entry.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Build the grouped session list with month-year headers.
  Widget _buildGroupedSessionList(
    BuildContext context,
    WidgetRef ref,
    List<JournalSession> sessions,
  ) {
    // Group sessions by month-year.
    final groups = _groupByMonth(sessions);
    final pageSize = ref.watch(sessionPageSizeProvider);

    return CustomScrollView(
      slivers: [
        // Pending calendar events banner (ADR-0020 §8 deferral).
        _PendingEventsBanner(),

        // Build a sliver per month group.
        for (final entry in groups.entries) ...[
          // Sticky month-year header.
          SliverPersistentHeader(
            pinned: true,
            delegate: _MonthHeaderDelegate(entry.key),
          ),
          // Session cards in this group.
          SliverList(
            delegate: SliverChildBuilderDelegate((context, index) {
              final session = entry.value[index];
              return SessionCard(
                session: session,
                messageCount: _messageCounts[session.sessionId] ?? 0,
                onTap: () {
                  Navigator.of(
                    context,
                  ).pushNamed('/session/detail', arguments: session.sessionId);
                },
                onDelete: () => deleteSessionCascade(
                  ref.read(sessionDaoProvider),
                  ref.read(messageDaoProvider),
                  session.sessionId,
                  photoDao: ref.read(photoDaoProvider),
                  photoService: ref.read(photoServiceProvider),
                ),
              );
            }, childCount: entry.value.length),
          ),
        ],

        // "Load older entries" button — only shown if the current page is full.
        if (sessions.length >= pageSize)
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 80),
              child: OutlinedButton(
                onPressed: () {
                  ref.read(sessionPageSizeProvider.notifier).state += 50;
                },
                child: const Text('Load older entries'),
              ),
            ),
          )
        else
          // Bottom padding so content doesn't hide behind the FAB.
          const SliverPadding(padding: EdgeInsets.only(bottom: 80)),
      ],
    );
  }

  /// Group sessions by month-year string from startTime.
  ///
  /// Returns a LinkedHashMap to preserve insertion order (newest first).
  Map<String, List<JournalSession>> _groupByMonth(
    List<JournalSession> sessions,
  ) {
    final months = [
      'January',
      'February',
      'March',
      'April',
      'May',
      'June',
      'July',
      'August',
      'September',
      'October',
      'November',
      'December',
    ];

    final groups = <String, List<JournalSession>>{};
    for (final session in sessions) {
      final local = session.startTime.toLocal();
      final key = '${months[local.month - 1]} ${local.year}';
      groups.putIfAbsent(key, () => []).add(session);
    }
    return groups;
  }

  /// Batch-load message counts for all visible sessions.
  ///
  /// Only re-fetches when the session ID list changes, avoiding redundant
  /// queries on every stream emission. Replaces the N+1 per-card pattern.
  void _refreshMessageCounts(List<JournalSession> sessions) {
    final sessionIds = sessions.map((s) => s.sessionId).toList();
    // Only reload if the set of session IDs has changed.
    if (_lastSessionIds != null &&
        sessionIds.length == _lastSessionIds!.length &&
        sessionIds.every((id) => _lastSessionIds!.contains(id))) {
      return;
    }
    _lastSessionIds = sessionIds;
    final messageDao = ref.read(messageDaoProvider);
    messageDao.getMessageCountsForSessions(sessionIds).then((counts) {
      if (mounted) {
        setState(() => _messageCounts = counts);
      }
    });
  }

  /// Quick Check-In CTA card (Phase 2B).
  ///
  /// Shown universally until dismissed. Two options: start a quick check-in
  /// or browse the journal. No gap duration is referenced — ADHD UX compliant.
  Widget _buildRecoveryBanner(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      margin: const EdgeInsets.fromLTRB(12, 12, 12, 0),
      color: theme.colorScheme.primaryContainer,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    'Good to see you. What would you like to do?',
                    style: theme.textTheme.bodyLarge?.copyWith(
                      color: theme.colorScheme.onPrimaryContainer,
                    ),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close, size: 18),
                  color: theme.colorScheme.onPrimaryContainer,
                  onPressed: () =>
                      ref
                              .read(
                                quickCheckInBannerDismissedProvider.notifier,
                              )
                              .state =
                          true,
                  tooltip: 'Dismiss',
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                FilledButton(
                  onPressed: _isStarting
                      ? null
                      : () => _startNewSession(
                          context,
                          journalingMode: 'pulse_check_in',
                        ),
                  child: const Text('Quick check-in'),
                ),
                const SizedBox(width: 12),
                OutlinedButton(
                  onPressed: () =>
                      ref
                              .read(
                                quickCheckInBannerDismissedProvider.notifier,
                              )
                              .state =
                          true,
                  child: const Text('Just browse'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  /// Weekly celebratory digest card (Phase 3D).
  ///
  /// Shows a congratulatory card once per week celebrating the sessions the
  /// user captured. ADHD-safe framing: only what WAS captured is mentioned —
  /// no gaps, no missed days, no streaks.
  ///
  /// Tap ✕ → dismissed for 7 days (stored in SharedPreferences).
  Widget _buildWeeklyDigestCard(BuildContext context, WeeklyDigest digest) {
    final theme = Theme.of(context);
    final count = digest.sessionCount;
    final momentWord = count == 1 ? 'moment' : 'moments';
    final headline = 'This week you captured $count $momentWord — nice.';

    return Card(
      margin: const EdgeInsets.fromLTRB(12, 12, 12, 0),
      color: theme.colorScheme.tertiaryContainer,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 8, 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                Icon(
                  Icons.star_outline,
                  size: 16,
                  color: theme.colorScheme.tertiary,
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    headline,
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: theme.colorScheme.onTertiaryContainer,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close, size: 18),
                  color: theme.colorScheme.onTertiaryContainer,
                  tooltip: 'Dismiss until next week',
                  onPressed: () async {
                    try {
                      await ref
                          .read(weeklyDigestServiceProvider)
                          .dismissDigest();
                      if (context.mounted) {
                        ref.invalidate(weeklyDigestProvider);
                      }
                    } on Exception {
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text("Couldn't dismiss. Try again."),
                          ),
                        );
                      }
                    }
                  },
                ),
              ],
            ),
            if (digest.highlightSession?.summary != null &&
                digest.highlightSession!.summary!.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(
                digest.highlightSession!.summary!,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onTertiaryContainer,
                  fontStyle: FontStyle.italic,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ],
        ),
      ),
    );
  }

  /// Daily journal reminder card (Phase 4D).
  ///
  /// Shown in the user's configured time window when they haven't journaled
  /// today. Follows ADHD non-escalating contract:
  ///   - "Start Entry" → acknowledges the reminder + starts a new session.
  ///   - "Dismiss" → records one dismissal; auto-disables after 3 in a row.
  ///   - "Don't remind me" → permanently disables (snooze forever).
  ///
  /// No gap language, no streak pressure — just a gentle nudge.
  Widget _buildReminderCard(BuildContext context) {
    final theme = Theme.of(context);
    final service = ref.read(reminderServiceProvider);
    final window = service.getWindow(ReminderType.dailyJournal);

    final windowLabel = switch (window) {
      ReminderWindow.morning => 'morning',
      ReminderWindow.afternoon => 'afternoon',
      ReminderWindow.evening => 'evening',
    };

    return Card(
      margin: const EdgeInsets.fromLTRB(12, 12, 12, 0),
      color: theme.colorScheme.primaryContainer,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 8, 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                Icon(
                  Icons.edit_note_outlined,
                  size: 16,
                  color: theme.colorScheme.primary,
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    'Good $windowLabel — ready to capture a thought?',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: theme.colorScheme.onPrimaryContainer,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton(
                  onPressed: () async {
                    try {
                      await service.snoozeForever(ReminderType.dailyJournal);
                      if (context.mounted) {
                        ref.invalidate(dailyReminderVisibleProvider);
                      }
                    } on Exception {
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text(
                              "Couldn't update reminder. Try again.",
                            ),
                          ),
                        );
                      }
                    }
                  },
                  style: TextButton.styleFrom(
                    foregroundColor: theme.colorScheme.onPrimaryContainer
                        .withValues(alpha: 0.7),
                  ),
                  child: const Text("Don't remind me"),
                ),
                TextButton(
                  onPressed: () async {
                    try {
                      await service.dismiss(ReminderType.dailyJournal);
                      if (context.mounted) {
                        ref.invalidate(dailyReminderVisibleProvider);
                      }
                    } on Exception {
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text(
                              "Couldn't dismiss reminder. Try again.",
                            ),
                          ),
                        );
                      }
                    }
                  },
                  style: TextButton.styleFrom(
                    foregroundColor: theme.colorScheme.onPrimaryContainer
                        .withValues(alpha: 0.85),
                  ),
                  child: const Text('Dismiss'),
                ),
                FilledButton.tonal(
                  onPressed: _isStarting
                      ? null
                      : () async {
                          await service.acknowledge(ReminderType.dailyJournal);
                          if (context.mounted) {
                            ref.invalidate(dailyReminderVisibleProvider);
                            await _startNewSession(context);
                          }
                        },
                  child: const Text('Start Entry'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  /// "Gift" resurfacing card (Phase 3C).
  ///
  /// Shows a past session from a spaced-repetition window (~7d, ~30d, or ~90d
  /// ago). ADHD-safe framing: "A moment from last week" — no gap references,
  /// no evaluation of frequency or consistency.
  ///
  /// "Skip" → excludes the session from future resurfacing (persisted).
  /// "Reflect on this" → opens session detail (card refreshes on return).
  Widget _buildGiftCard(BuildContext context, JournalSession session) {
    final theme = Theme.of(context);
    final timeAgo = _formatTimeAgo(session.startTime);

    return Card(
      margin: const EdgeInsets.fromLTRB(12, 12, 12, 0),
      color: theme.colorScheme.secondaryContainer,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 8, 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                Icon(
                  Icons.auto_awesome_outlined,
                  size: 16,
                  color: theme.colorScheme.secondary,
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    'A moment from $timeAgo',
                    style: theme.textTheme.labelMedium?.copyWith(
                      color: theme.colorScheme.onSecondaryContainer,
                    ),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close, size: 18),
                  color: theme.colorScheme.onSecondaryContainer,
                  tooltip: 'Never resurface this memory',
                  onPressed: () async {
                    try {
                      await ref
                          .read(resurfacingServiceProvider)
                          .skipSession(session.sessionId);
                      if (context.mounted) {
                        ref.invalidate(resurfacedSessionProvider);
                      }
                    } on Exception {
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text("Couldn't skip. Try again."),
                          ),
                        );
                      }
                    }
                  },
                ),
              ],
            ),
            if (session.summary != null && session.summary!.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(
                session.summary!,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSecondaryContainer,
                ),
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
              ),
            ],
            const SizedBox(height: 4),
            Align(
              alignment: Alignment.centerRight,
              child: TextButton(
                onPressed: () async {
                  await Navigator.of(
                    context,
                  ).pushNamed('/session/detail', arguments: session.sessionId);
                  // Invalidate AFTER the user returns, not before — prevents
                  // the card from reloading while the user is in the detail screen.
                  if (context.mounted) {
                    ref.invalidate(resurfacedSessionProvider);
                  }
                },
                style: TextButton.styleFrom(
                  foregroundColor: theme.colorScheme.secondary,
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 8,
                  ),
                ),
                child: const Text('Reflect on this →'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Format a past timestamp as a human-friendly relative phrase.
  ///
  /// ADHD UX: keeps framing positive ("a moment from…") without implying
  /// anything about the user's activity frequency.
  ///
  /// Note: the spaced-repetition windows reach at most ~93 days (90d ± 3d
  /// radius). Branches beyond 120 days are unreachable in production but kept
  /// as a safe defensive fallback.
  String _formatTimeAgo(DateTime sessionTime) {
    final days = DateTime.now().difference(sessionTime).inDays;
    if (days < 14) return 'last week';
    if (days < 50) return 'last month';
    if (days < 120) return 'three months ago';
    if (days < 200) return 'several months ago';
    return 'a while back';
  }

  /// Start a new journaling session and navigate to it.
  ///
  /// Pulse Check-In sessions always route to [CheckInScreen] (/check_in) —
  /// the slider UI is always more appropriate than chat chrome for a
  /// structured questionnaire. Voice check-in (Phase 3A) will be added
  /// inside CheckInScreen, not by routing to the chat interface.
  Future<void> _startNewSession(
    BuildContext context, {
    String? journalingMode,
  }) async {
    setState(() => _isStarting = true);
    try {
      await ref
          .read(sessionNotifierProvider.notifier)
          .startSession(journalingMode: journalingMode);
      if (context.mounted) {
        final route = journalingMode == 'pulse_check_in'
            ? '/check_in'
            : '/session';
        Navigator.of(context).pushNamed(route);
      }
    } finally {
      if (mounted) {
        setState(() => _isStarting = false);
      }
    }
  }

  /// Open the Quick Capture Palette and dispatch to the selected mode.
  ///
  /// Reads the last-used mode from [lastCaptureModeProvider] to pre-highlight
  /// the matching tile. After the user selects a mode, persists it and
  /// dispatches:
  ///   - 'text'               → free-form text session
  ///   - 'voice'              → text session with voice mode pre-enabled
  ///   - '__quick_mood_tap__' → Quick Mood Tap overlay (no full session)
  ///   - 'pulse_check_in'     → Pulse Check-In slider session
  Future<void> _openQuickCapturePalette(BuildContext context) async {
    final lastMode = ref.read(lastCaptureModeProvider);

    final selected = await showQuickCapturePalette(context, lastMode: lastMode);
    if (selected == null || !context.mounted) return;

    // Persist the chosen mode so it is pre-highlighted on the next open.
    await ref.read(lastCaptureModeProvider.notifier).setMode(selected);
    if (!context.mounted) return;

    await _dispatchCaptureMode(context, selected);
  }

  /// Dispatch directly to a capture mode without showing the palette.
  ///
  /// Called by both [_openQuickCapturePalette] (after palette selection) and
  /// the widget launch listener (Phase 4B — Quick Capture widget).
  ///   - 'text'               → start a regular journal session
  ///   - 'voice'              → start a session with voice mode pre-enabled
  ///   - '__quick_mood_tap__' → open Quick Mood Tap overlay (no session)
  ///   - 'pulse_check_in'     → start a Pulse Check-In session
  Future<void> _dispatchCaptureMode(BuildContext context, String mode) async {
    // Quick Mood Tap: open the emoji overlay — no LLM, no session navigation.
    if (mode == '__quick_mood_tap__') {
      await showQuickMoodTapSheet(context);
      return;
    }

    // Voice mode: pre-enable the mic BEFORE navigating so session_providers
    // reads voiceModeEnabledProvider as true synchronously when the session
    // is created. If setEnabled were called after navigation, the session
    // screen's initState would already have read the old (false) value.
    if (mode == 'voice') {
      await ref.read(voiceModeEnabledProvider.notifier).setEnabled(true);
      if (!context.mounted) return;
    }

    // All session-based modes route through _startNewSession.
    // 'pulse_check_in' → /check_in (slider UI); all others → /session (chat).
    final journalingMode = mode == 'pulse_check_in' ? 'pulse_check_in' : null;
    await _startNewSession(context, journalingMode: journalingMode);
  }
}

/// Sliver persistent header delegate for month-year group headers.
class _MonthHeaderDelegate extends SliverPersistentHeaderDelegate {
  final String title;

  _MonthHeaderDelegate(this.title);

  @override
  double get minExtent => 40;

  @override
  double get maxExtent => 40;

  @override
  Widget build(
    BuildContext context,
    double shrinkOffset,
    bool overlapsContent,
  ) {
    return Container(
      height: 40,
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      alignment: Alignment.centerLeft,
      child: Text(
        title,
        style: Theme.of(context).textTheme.titleSmall?.copyWith(
          fontWeight: FontWeight.w600,
          color: Theme.of(context).colorScheme.onSurfaceVariant,
        ),
      ),
    );
  }

  @override
  bool shouldRebuild(covariant _MonthHeaderDelegate oldDelegate) {
    return title != oldDelegate.title;
  }
}

/// Gallery icon button with progressive disclosure.
///
/// Only visible when the user has at least one photo.
class _GalleryIconButton extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final countAsync = ref.watch(photoCountProvider);

    return countAsync.when(
      data: (count) {
        if (count < 1) return const SizedBox.shrink();
        return IconButton(
          icon: const Icon(Icons.photo_library_outlined),
          tooltip: 'Photo gallery',
          onPressed: () => Navigator.of(context).pushNamed('/gallery'),
        );
      },
      loading: () => const SizedBox.shrink(),
      error: (_, _) => const SizedBox.shrink(),
    );
  }
}

/// Search icon button with progressive disclosure.
///
/// Only visible when the user has 5+ sessions.
class _SearchIconButton extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final countAsync = ref.watch(sessionCountProvider);

    return countAsync.when(
      data: (count) {
        if (count < 5) return const SizedBox.shrink();
        return IconButton(
          icon: const Icon(Icons.search),
          tooltip: 'Search journal',
          onPressed: () => Navigator.of(context).pushNamed('/search'),
        );
      },
      loading: () => const SizedBox.shrink(),
      error: (_, _) => const SizedBox.shrink(),
    );
  }
}

/// Tasks icon button with progressive disclosure.
///
/// Only visible when the user has at least one active task.
class _TasksIconButton extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final countAsync = ref.watch(taskCountProvider);

    return countAsync.when(
      data: (count) {
        if (count < 1) return const SizedBox.shrink();
        return IconButton(
          icon: const Icon(Icons.task_alt_outlined),
          tooltip: 'Tasks',
          onPressed: () => Navigator.of(context).pushNamed('/tasks'),
        );
      },
      loading: () => const SizedBox.shrink(),
      error: (_, _) => const SizedBox.shrink(),
    );
  }
}

/// Check-In History icon with progressive disclosure.
///
/// Visible only after the user has completed at least one Pulse Check-In.
/// Routes to [CheckInHistoryScreen] (/check_in_history).
class _CheckInHistoryIconButton extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final countAsync = ref.watch(checkInCountProvider);

    return countAsync.when(
      data: (count) {
        if (count < 1) return const SizedBox.shrink();
        return IconButton(
          icon: const Icon(Icons.insights_outlined),
          tooltip: 'Check-in history',
          onPressed: () => Navigator.of(context).pushNamed('/check_in_history'),
        );
      },
      loading: () => const SizedBox.shrink(),
      error: (_, _) => const SizedBox.shrink(),
    );
  }
}

/// Banner shown when pending calendar events exist from voice-mode deferral.
///
/// When a calendar intent fires during voice mode but Google is not
/// connected, the event is saved locally. This banner prompts the user
/// to connect and create the deferred events (ADR-0020 §8).
class _PendingEventsBanner extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final countAsync = ref.watch(pendingCalendarEventsCountProvider);

    return countAsync.when(
      data: (count) {
        if (count < 1) {
          return const SliverToBoxAdapter(child: SizedBox.shrink());
        }
        return SliverToBoxAdapter(
          child: _PendingEventsBannerCard(count: count),
        );
      },
      loading: () => const SliverToBoxAdapter(child: SizedBox.shrink()),
      error: (_, _) => const SliverToBoxAdapter(child: SizedBox.shrink()),
    );
  }
}

/// The Material card content for the pending events banner.
class _PendingEventsBannerCard extends ConsumerWidget {
  final int count;

  const _PendingEventsBannerCard({required this.count});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Card(
      margin: const EdgeInsets.fromLTRB(12, 8, 12, 4),
      elevation: 1,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: colorScheme.primary.withValues(alpha: 0.3)),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => _connectAndCreateEvents(context, ref),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              Icon(Icons.event_note, color: colorScheme.primary, size: 24),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      count == 1
                          ? '1 pending calendar event'
                          : '$count pending calendar events',
                      style: theme.textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      'Tap to connect Google Calendar',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
              Icon(Icons.chevron_right, color: colorScheme.onSurfaceVariant),
            ],
          ),
        ),
      ),
    );
  }

  /// Connect to Google Calendar and create all pending events.
  Future<void> _connectAndCreateEvents(
    BuildContext context,
    WidgetRef ref,
  ) async {
    // Check if already connected.
    var isConnected = ref.read(isGoogleConnectedProvider);
    if (!isConnected) {
      isConnected = await ref
          .read(isGoogleConnectedProvider.notifier)
          .connect();
    }

    if (!isConnected || !context.mounted) return;

    // Get all pending events and create them in Google Calendar.
    final calendarEventDao = ref.read(calendarEventDaoProvider);
    final authService = ref.read(googleAuthServiceProvider);
    final pending = await calendarEventDao.getPendingEvents();

    final authClient = await authService.getAuthClient();
    if (authClient == null) return;

    final calendarService = GoogleCalendarService.withClient(authClient);
    var successCount = 0;

    for (final event in pending) {
      try {
        final result = await calendarService.createEvent(
          title: event.title,
          startTime: event.startTime,
          endTime: event.endTime,
        );
        await calendarEventDao.updateGoogleEventId(
          event.eventId,
          result.googleEventId,
        );
        successCount++;
      } on CalendarServiceException {
        await calendarEventDao.updateStatus(event.eventId, EventStatus.failed);
      } on Exception {
        await calendarEventDao.updateStatus(event.eventId, EventStatus.failed);
      }
    }

    // Refresh the pending count.
    ref.invalidate(pendingCalendarEventsCountProvider);

    if (!context.mounted) return;

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          successCount == pending.length
              ? 'Added $successCount ${successCount == 1 ? 'event' : 'events'} to Google Calendar.'
              : 'Added $successCount of ${pending.length} events. Some failed.',
        ),
      ),
    );
  }
}
