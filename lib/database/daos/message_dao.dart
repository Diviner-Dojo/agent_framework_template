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
  Future<void> insertMessage(
    String messageId,
    String sessionId,
    String role,
    String content,
    DateTime timestamp, {
    String inputMethod = 'TEXT',
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
}
