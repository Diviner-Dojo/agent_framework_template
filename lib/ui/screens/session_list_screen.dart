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
import '../../providers/database_provider.dart';
import '../../providers/search_providers.dart';
import '../../providers/session_providers.dart';
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
