// ===========================================================================
// file: lib/repositories/search_repository.dart
// purpose: Orchestrates local search across sessions and messages, deduplicates
//          results, and formats session context for Claude recall queries.
//
// This repository does NOT call Claude — it prepares data for the recall
// pipeline. ClaudeApiService.recall() handles the actual API call.
// SessionNotifier orchestrates the full flow (ADR-0013 §3).
//
// See: ADR-0013 (Search + Memory Recall Architecture)
// ===========================================================================

import 'dart:math';

import '../database/daos/message_dao.dart';
import '../database/daos/session_dao.dart';
import '../models/search_models.dart';

/// Orchestrates search across sessions and messages.
///
/// Combines results from SessionDao (summary/metadata matches) and
/// MessageDao (content matches), deduplicates sessions that match in
/// both places (summary match wins), and ranks by relevance.
class SearchRepository {
  final SessionDao _sessionDao;
  final MessageDao _messageDao;

  SearchRepository({
    required SessionDao sessionDao,
    required MessageDao messageDao,
  }) : _sessionDao = sessionDao,
       _messageDao = messageDao;

  /// Search across all sessions and messages.
  ///
  /// Returns deduplicated results ranked by relevance:
  ///   1. Summary/metadata matches first (more specific signal)
  ///   2. Message-only matches second
  ///   3. Within each group, sorted by date descending (newest first)
  ///
  /// A session matching both summary and messages appears once with
  /// [MatchSource.summary] (per spec dedup rule).
  ///
  /// Returns empty results for empty/whitespace-only queries.
  Future<SearchResults> searchEntries(
    String query, {
    SearchFilters filters = SearchFilters.empty,
  }) async {
    final trimmed = query.trim();
    if (trimmed.isEmpty) {
      return SearchResults(query: query);
    }

    // Run session and message search in parallel.
    final sessionsFuture = _sessionDao.searchSessions(
      trimmed,
      dateStart: filters.dateStart,
      dateEnd: filters.dateEnd,
      moodTags: filters.moodTags,
      people: filters.people,
      topicTags: filters.topicTags,
    );
    final messagesFuture = _messageDao.searchMessages(trimmed);

    final sessions = await sessionsFuture;
    final messages = await messagesFuture;

    // Build set of session IDs that matched via summary/metadata.
    final summaryMatchIds = <String>{for (final s in sessions) s.sessionId};

    // Fetch snippets for all summary matches in parallel.
    final summarySnippetFutures = sessions.map(
      (s) => _messageDao.getMessageSnippets(s.sessionId, trimmed),
    );
    final summarySnippets = await Future.wait(summarySnippetFutures);

    // Build results from summary matches (ranked higher).
    final results = <SearchResultItem>[];
    for (var i = 0; i < sessions.length; i++) {
      results.add(
        SearchResultItem(
          sessionId: sessions[i].sessionId,
          session: sessions[i],
          matchingSnippets: summarySnippets[i],
          matchSource: MatchSource.summary,
        ),
      );
    }

    // Find sessions that matched via messages but NOT via summary.
    final messageOnlySessionIds = <String>{};
    for (final message in messages) {
      if (!summaryMatchIds.contains(message.sessionId) &&
          !messageOnlySessionIds.contains(message.sessionId)) {
        messageOnlySessionIds.add(message.sessionId);
      }
    }

    // Fetch sessions and snippets for message-only matches in parallel.
    final messageOnlyIdList = messageOnlySessionIds.toList();
    final sessionFutures = messageOnlyIdList.map(
      (id) => _sessionDao.getSessionById(id),
    );
    final msgSnippetFutures = messageOnlyIdList.map(
      (id) => _messageDao.getMessageSnippets(id, trimmed),
    );
    final messageOnlySessions = await Future.wait(sessionFutures);
    final messageOnlySnippets = await Future.wait(msgSnippetFutures);

    // Add message-only matches (ranked lower), skipping missing sessions.
    for (var i = 0; i < messageOnlyIdList.length; i++) {
      final session = messageOnlySessions[i];
      if (session == null) continue;

      results.add(
        SearchResultItem(
          sessionId: messageOnlyIdList[i],
          session: session,
          matchingSnippets: messageOnlySnippets[i],
          matchSource: MatchSource.message,
        ),
      );
    }

    return SearchResults(items: results, query: query);
  }

  /// Format sessions as structured context maps for Claude recall.
  ///
  /// Returns a list of maps suitable for passing to
  /// [ClaudeApiService.recall()] as contextEntries. Each map contains:
  ///   - session_id: the session ID
  ///   - session_date: ISO 8601 date string
  ///   - summary: truncated to [maxSummaryLength] characters
  ///   - snippets: up to [maxSnippetsPerSession] message snippets,
  ///     each truncated to [maxSnippetLength] characters
  ///
  /// Enforces a hard cap of [maxSessions] (default 10) per ADR-0013 §5.
  Future<List<Map<String, dynamic>>> getSessionContext(
    List<String> sessionIds, {
    int maxSessions = 10,
    int maxSummaryLength = 500,
    int maxSnippetsPerSession = 5,
    int maxSnippetLength = 300,
  }) async {
    // Enforce session cap.
    final capped = sessionIds.take(maxSessions).toList();

    // Fetch all sessions and their messages in parallel.
    final sessionFutures = capped.map((id) => _sessionDao.getSessionById(id));
    final messageFutures = capped.map(
      (id) => _messageDao.getMessagesForSession(id),
    );
    final fetchedSessions = await Future.wait(sessionFutures);
    final fetchedMessages = await Future.wait(messageFutures);

    final contexts = <Map<String, dynamic>>[];
    for (var i = 0; i < capped.length; i++) {
      final session = fetchedSessions[i];
      if (session == null) continue;

      // Only USER messages are included in recall context — AI follow-up
      // questions are excluded to keep context signal-dense with the
      // journaler's own voice and thoughts.
      final userMessages = fetchedMessages[i]
          .where((m) => m.role == 'USER')
          .toList();

      // Take up to maxSnippetsPerSession user messages, truncated.
      final snippets = userMessages
          .take(maxSnippetsPerSession)
          .map((m) => _truncate(m.content, maxSnippetLength))
          .toList();

      contexts.add({
        'session_id': capped[i],
        'session_date': session.startTime.toIso8601String(),
        'summary': _truncate(session.summary ?? '', maxSummaryLength),
        'snippets': snippets,
      });
    }

    return contexts;
  }

  /// Truncate a string to the given maximum length.
  static String _truncate(String text, int maxLength) {
    if (text.length <= maxLength) return text;
    return '${text.substring(0, min(maxLength - 3, text.length))}...';
  }
}
