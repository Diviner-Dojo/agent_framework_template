// ===========================================================================
// file: lib/database/daos/message_dao.dart
// purpose: Data Access Object for journal messages. Provides CRUD operations
//          on the journal_messages table using drift's type-safe query API.
//
// Pattern: Constructor injection (see ADR-0007).
//   Same rationale as SessionDao — inject AppDatabase for easy testing.
//   Do NOT refactor to @DriftAccessor mixin.
// ===========================================================================

import 'package:drift/drift.dart';

import '../app_database.dart';
import '../search_query_utils.dart';

/// Provides all database operations for individual messages within sessions.
///
/// Messages are the conversation transcript — each row is one message
/// from either the USER, the ASSISTANT, or the SYSTEM.
///
/// Messages always belong to a session (foreign key: session_id).
/// They are ordered by timestamp within a session.
class MessageDao {
  final AppDatabase _db;

  /// Create a MessageDao backed by the given database instance.
  MessageDao(this._db);

  /// Insert a single message into a session.
  ///
  /// [messageId] is a client-generated UUID.
  /// [sessionId] must reference an existing session (FK constraint).
  /// [role] is one of: 'USER', 'ASSISTANT', 'SYSTEM'.
  /// [content] is the actual text of the message.
  /// [timestamp] should be UTC.
  /// [inputMethod] defaults to 'TEXT' (Phase 2 adds 'VOICE').
  /// [entitiesJson] optional JSON metadata (used for recall metadata in Phase 5).
  Future<void> insertMessage(
    String messageId,
    String sessionId,
    String role,
    String content,
    DateTime timestamp, {
    String inputMethod = 'TEXT',
    String? entitiesJson,
  }) async {
    await _db
        .into(_db.journalMessages)
        .insert(
          JournalMessagesCompanion.insert(
            messageId: messageId,
            sessionId: sessionId,
            role: role,
            content: content,
            timestamp: timestamp,
            inputMethod: Value(inputMethod),
            entitiesJson: Value(entitiesJson),
          ),
        );
  }

  /// Get all messages for a session, ordered by timestamp ascending.
  ///
  /// This reconstructs the conversation in chronological order.
  /// Returns a one-time snapshot. For reactive updates, use
  /// [watchMessagesForSession] instead.
  Future<List<JournalMessage>> getMessagesForSession(String sessionId) async {
    return (_db.select(_db.journalMessages)
          ..where((m) => m.sessionId.equals(sessionId))
          ..orderBy([
            (m) =>
                OrderingTerm(expression: m.timestamp, mode: OrderingMode.asc),
          ]))
        .get();
  }

  /// Watch messages for a session as a reactive stream.
  ///
  /// Used by the active journal session screen to auto-update
  /// the chat view when new messages are inserted (e.g., after
  /// the agent generates a follow-up question).
  Stream<List<JournalMessage>> watchMessagesForSession(String sessionId) {
    return (_db.select(_db.journalMessages)
          ..where((m) => m.sessionId.equals(sessionId))
          ..orderBy([
            (m) =>
                OrderingTerm(expression: m.timestamp, mode: OrderingMode.asc),
          ]))
        .watch();
  }

  /// Get the number of messages in a session.
  ///
  /// Used for display on session cards (e.g., "12 messages")
  /// and for the agent to track conversation length.
  Future<int> getMessageCount(String sessionId) async {
    // Use countAll() with a filter for type-safe counting.
    // This generates: SELECT COUNT(*) FROM journal_messages WHERE session_id = ?
    final count = _db.journalMessages.messageId.count();
    final query = _db.selectOnly(_db.journalMessages)
      ..addColumns([count])
      ..where(_db.journalMessages.sessionId.equals(sessionId));
    final result = await query.getSingle();
    return result.read(count)!;
  }

  // =========================================================================
  // Search methods (Phase 5)
  // =========================================================================

  /// Search messages by keyword across content column.
  ///
  /// Uses case-insensitive LIKE queries (not FTS5) — see ADR-0013.
  /// LIKE wildcards (%, _) in [query] are escaped before interpolation.
  /// Optionally scoped to a single session via [sessionId].
  ///
  /// Returns messages ordered by timestamp descending (newest first).
  Future<List<JournalMessage>> searchMessages(
    String query, {
    String? sessionId,
  }) async {
    final escaped = escapeLikeWildcards(query);
    final pattern = '%$escaped%';

    final select = _db.select(_db.journalMessages)
      ..where((m) {
        Expression<bool> condition = LikeWithEscape(m.content, pattern);
        if (sessionId != null) {
          condition = condition & m.sessionId.equals(sessionId);
        }
        return condition;
      })
      ..orderBy([
        (m) => OrderingTerm(expression: m.timestamp, mode: OrderingMode.desc),
      ]);

    return select.get();
  }

  /// Get content snippets from messages in a session matching a keyword.
  ///
  /// Returns content fragments (80-120 chars) centered on the matching
  /// keyword for search result previews. Returns at most [maxSnippets]
  /// snippets per session (default 2).
  Future<List<String>> getMessageSnippets(
    String sessionId,
    String query, {
    int maxSnippets = 2,
  }) async {
    final messages = await searchMessages(query, sessionId: sessionId);
    final snippets = <String>[];
    final lowerQuery = query.toLowerCase();

    for (final message in messages) {
      if (snippets.length >= maxSnippets) break;

      final content = message.content;
      final lowerContent = content.toLowerCase();
      final matchIndex = lowerContent.indexOf(lowerQuery);
      if (matchIndex < 0) continue;

      snippets.add(_extractSnippet(content, matchIndex, query.length));
    }

    return snippets;
  }

  // =========================================================================
  // Private helpers
  // =========================================================================

  /// Extract a snippet centered on a match position.
  ///
  /// Produces an 80-120 character fragment with ellipsis indicators
  /// when the snippet doesn't start/end at the content boundary.
  static String _extractSnippet(
    String content,
    int matchIndex,
    int matchLength,
  ) {
    const targetLength = 100;
    const halfWindow = targetLength ~/ 2;

    // Calculate snippet boundaries.
    var start = matchIndex - halfWindow;
    var end = matchIndex + matchLength + halfWindow;

    // Clamp to content boundaries.
    if (start < 0) {
      end += -start; // Extend end to compensate.
      start = 0;
    }
    if (end > content.length) {
      start -= (end - content.length); // Extend start to compensate.
      end = content.length;
    }
    start = start.clamp(0, content.length);
    end = end.clamp(0, content.length);

    // Build snippet with ellipsis.
    final prefix = start > 0 ? '...' : '';
    final suffix = end < content.length ? '...' : '';
    return '$prefix${content.substring(start, end)}$suffix';
  }
}
