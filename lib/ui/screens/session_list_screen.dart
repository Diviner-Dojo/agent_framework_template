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
import '../../providers/session_providers.dart';
import '../../providers/task_providers.dart';
import '../../services/google_calendar_service.dart';
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

    return Scaffold(
      appBar: AppBar(
        title: const Text('Agentic Journal'),
        actions: [
          // Tasks icon — visible when tasks exist.
          _TasksIconButton(),
          // Gallery icon — visible when photos exist.
          _GalleryIconButton(),
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
          return _buildGroupedSessionList(context, ref, sessions);
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, stack) =>
            Center(child: Text('Error loading sessions: $error')),
      ),
      // FAB to start a new journaling session.
      floatingActionButton: FloatingActionButton(
        onPressed: _isStarting ? null : () => _startNewSession(context),
        tooltip: 'New journal entry',
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

  /// Start a new journaling session and navigate to it.
  Future<void> _startNewSession(BuildContext context) async {
    setState(() => _isStarting = true);
    try {
      await ref.read(sessionNotifierProvider.notifier).startSession();
      if (context.mounted) {
        Navigator.of(context).pushNamed('/session');
      }
    } finally {
      if (mounted) {
        setState(() => _isStarting = false);
      }
    }
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
