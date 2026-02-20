// ===========================================================================
// file: lib/ui/screens/session_list_screen.dart
// purpose: Home screen — displays a list of past journal sessions.
//
// This is the first screen the user sees when opening the app.
// It shows all past sessions sorted by date (newest first), with a
// floating action button to start a new session.
//
// Uses allSessionsProvider (a StreamProvider) for reactive updates —
// when a new session is created or an existing one is updated,
// the list automatically refreshes.
//
// The FAB shows a loading indicator while a session is being created
// to prevent multi-tap and provide visual feedback.
// ===========================================================================

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../database/app_database.dart';
import '../../providers/database_provider.dart';
import '../../providers/session_providers.dart';
import '../widgets/session_card.dart';

/// Home screen showing all past journal sessions.
class SessionListScreen extends ConsumerStatefulWidget {
  const SessionListScreen({super.key});

  @override
  ConsumerState<SessionListScreen> createState() => _SessionListScreenState();
}

class _SessionListScreenState extends ConsumerState<SessionListScreen> {
  bool _isStarting = false;

  @override
  Widget build(BuildContext context) {
    // Watch the stream of all sessions for reactive updates.
    final sessionsAsync = ref.watch(allSessionsProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Agentic Journal'),
        actions: [
          // Settings gear icon — opens the settings screen.
          IconButton(
            icon: const Icon(Icons.settings),
            tooltip: 'Settings',
            onPressed: () => Navigator.of(context).pushNamed('/settings'),
          ),
        ],
      ),
      body: sessionsAsync.when(
        // Data loaded — show the list or empty state.
        data: (sessions) {
          if (sessions.isEmpty) {
            return _buildEmptyState(context);
          }
          return _buildSessionList(context, ref, sessions);
        },
        // Loading — show a progress indicator.
        loading: () => const Center(child: CircularProgressIndicator()),
        // Error — show error message.
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

  /// Build the scrollable list of session cards.
  Widget _buildSessionList(
    BuildContext context,
    WidgetRef ref,
    List<JournalSession> sessions,
  ) {
    return ListView.builder(
      padding: const EdgeInsets.only(top: 8, bottom: 80),
      itemCount: sessions.length,
      itemBuilder: (context, index) {
        final session = sessions[index];
        // Get message count for each session.
        // Using a FutureProvider per session to avoid blocking the list.
        return _SessionCardWithCount(
          session: session,
          onTap: () {
            Navigator.of(
              context,
            ).pushNamed('/session/detail', arguments: session.sessionId);
          },
        );
      },
    );
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

/// A session card that asynchronously loads its message count.
///
/// This is a separate ConsumerStatefulWidget so each card can independently
/// load its message count without blocking the rest of the list.
class _SessionCardWithCount extends ConsumerStatefulWidget {
  final JournalSession session;
  final VoidCallback? onTap;

  const _SessionCardWithCount({required this.session, this.onTap});

  @override
  ConsumerState<_SessionCardWithCount> createState() =>
      _SessionCardWithCountState();
}

class _SessionCardWithCountState extends ConsumerState<_SessionCardWithCount> {
  int _messageCount = 0;

  @override
  void initState() {
    super.initState();
    _loadMessageCount();
  }

  Future<void> _loadMessageCount() async {
    final messageDao = ref.read(messageDaoProvider);
    final count = await messageDao.getMessageCount(widget.session.sessionId);
    if (mounted) {
      setState(() => _messageCount = count);
    }
  }

  @override
  Widget build(BuildContext context) {
    return SessionCard(
      session: widget.session,
      messageCount: _messageCount,
      onTap: widget.onTap,
    );
  }
}
