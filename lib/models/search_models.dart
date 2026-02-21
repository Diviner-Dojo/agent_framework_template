// ===========================================================================
// file: lib/models/search_models.dart
// purpose: Data models for the search + memory recall feature.
//
// These are separate from AgentResponse (ADR-0013 §4) because search
// results and recall answers have different semantics than conversational
// agent turns. AgentResponse models a conversation turn (content, layer,
// metadata); RecallResponse models a search-grounded answer with citations.
//
// See: ADR-0013 (Search + Memory Recall Architecture)
// ===========================================================================

import '../database/app_database.dart';

/// Filter criteria for search queries.
///
/// All fields are optional — an empty [SearchFilters] applies no filters.
/// Filters combine with AND logic (all specified criteria must match).
class SearchFilters {
  final DateTime? dateStart;
  final DateTime? dateEnd;
  final List<String>? moodTags;
  final List<String>? people;
  final List<String>? topicTags;

  const SearchFilters({
    this.dateStart,
    this.dateEnd,
    this.moodTags,
    this.people,
    this.topicTags,
  });

  /// Whether any filter is active.
  bool get hasActiveFilters =>
      dateStart != null ||
      dateEnd != null ||
      (moodTags != null && moodTags!.isNotEmpty) ||
      (people != null && people!.isNotEmpty) ||
      (topicTags != null && topicTags!.isNotEmpty);

  /// Create a copy with no filters applied.
  static const empty = SearchFilters();
}

/// How a search result was matched.
enum MatchSource {
  /// Matched in the session summary or metadata tags.
  summary,

  /// Matched in message content only (not summary).
  message,
}

/// A single search result item.
///
/// Represents one session that matched the search query, along with
/// context about how it matched and preview snippets.
class SearchResultItem {
  /// The ID of the matching session.
  final String sessionId;

  /// The full session record.
  final JournalSession session;

  /// Content snippets from matching messages (up to ~100 chars for search
  /// previews, or up to 300 chars for recall context — configurable).
  final List<String> matchingSnippets;

  /// Whether the match came from summary/metadata or message content.
  final MatchSource matchSource;

  const SearchResultItem({
    required this.sessionId,
    required this.session,
    this.matchingSnippets = const [],
    required this.matchSource,
  });
}

/// The result of a search query.
///
/// Contains the matched items and the original query for display purposes.
class SearchResults {
  /// The matched sessions, ranked by relevance.
  final List<SearchResultItem> items;

  /// The search query that produced these results.
  final String query;

  const SearchResults({this.items = const [], this.query = ''});

  /// Whether the search returned any results.
  bool get isEmpty => items.isEmpty;

  /// The number of matching sessions.
  int get count => items.length;
}

/// Response from Claude's memory recall synthesis.
///
/// Separate from [AgentResponse] (ADR-0013 §4) — recall is a grounded
/// answer with citations, not a conversational turn. The answer text
/// should only reference information from the cited sessions.
class RecallResponse {
  /// Claude's synthesized answer based on retrieved journal context.
  final String answer;

  /// Session IDs cited in the answer.
  ///
  /// These must be validated against the local DB before display —
  /// Claude may return IDs that don't exist locally (hallucination guard).
  final List<String> citedSessionIds;

  const RecallResponse({required this.answer, this.citedSessionIds = const []});
}
