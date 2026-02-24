// ===========================================================================
// file: lib/models/agent_response.dart
// purpose: Types for agent responses across Layer A (rule-based) and
//          Layer B (LLM-enhanced). The AgentLayer enum lets the app
//          track which layer served each interaction for analytics.
//
// These types are used by:
//   - AgentRepository (returns AgentResponse from all methods)
//   - ClaudeApiService (constructs AgentResponse from Edge Function JSON)
//   - SessionNotifier (reads metadata for session record updates)
//
// See: ADR-0006 (Three-Layer Agent Design)
// ===========================================================================

/// Which agent layer served a particular response.
///
/// Used for analytics/debugging — the UI doesn't show this to the user,
/// but it's valuable for tracking online/offline usage patterns and
/// verifying that the fallback chain works correctly.
enum AgentLayer {
  /// Layer A: Rule-based agent (offline, always available)
  ruleBasedLocal,

  /// Layer B remote: Claude API via Edge Function proxy (online)
  llmRemote,

  /// Layer B local: On-device LLM inference (Phase 8B)
  llmLocal,
}

/// Structured metadata extracted by Claude at the end of a session.
///
/// All fields are nullable because:
///   - Layer A (rule-based) doesn't produce this metadata
///   - Claude might fail to parse or return incomplete data
///   - The Edge Function might return a METADATA_PARSE_ERROR
///
/// These map directly to nullable fields in the drift JournalSessions table:
///   summary → JournalSession.summary
///   moodTags → JournalSession.moodTags (stored as JSON string)
///   people → JournalSession.people (stored as JSON string)
///   topicTags → JournalSession.topicTags (stored as JSON string)
class AgentMetadata {
  final String? summary;
  final List<String>? moodTags;
  final List<String>? people;
  final List<String>? topicTags;

  const AgentMetadata({
    this.summary,
    this.moodTags,
    this.people,
    this.topicTags,
  });

  /// Parse metadata from a JSON map (Edge Function response).
  ///
  /// Defensive parsing: every field uses safe type checking. If a field
  /// has the wrong type (e.g., mood_tags is a string instead of array),
  /// that field is silently set to null rather than throwing.
  factory AgentMetadata.fromJson(Map<String, dynamic> json) {
    return AgentMetadata(
      summary: json['summary'] is String ? json['summary'] as String : null,
      moodTags: _parseStringList(json['mood_tags']),
      people: _parseStringList(json['people']),
      topicTags: _parseStringList(json['topic_tags']),
    );
  }

  /// Safely parse a JSON value into a `List<String>`.
  ///
  /// Handles: `List<dynamic>` with string elements, null, wrong types.
  /// Returns null if the value is not a valid string list.
  static List<String>? _parseStringList(dynamic value) {
    if (value is! List) return null;
    try {
      return value.whereType<String>().toList();
    } catch (_) {
      return null;
    }
  }
}

/// The response from any agent method (greeting, follow-up, summary).
///
/// Every agent interaction returns this type, regardless of which layer
/// served it. This makes the caller (SessionNotifier) layer-agnostic —
/// it processes the response the same way whether it came from Claude
/// or the rule-based agent.
class AgentResponse {
  /// The text content of the response (greeting, follow-up, or summary).
  final String content;

  /// Which layer produced this response (for analytics/debugging).
  final AgentLayer layer;

  /// Optional structured metadata (only populated by Layer B on session end).
  final AgentMetadata? metadata;

  const AgentResponse({
    required this.content,
    required this.layer,
    this.metadata,
  });
}
