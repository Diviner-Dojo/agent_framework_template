// ===========================================================================
// file: lib/providers/search_providers.dart
// purpose: Riverpod providers for search and memory recall.
//
// All search/recall providers live here, following the sync_providers.dart
// precedent (per architecture-consultant). This keeps search concerns
// separate from session/auth providers.
//
// See: ADR-0013 (Search + Memory Recall Architecture)
// ===========================================================================

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/search_models.dart';
import '../repositories/search_repository.dart';
import '../services/intent_classifier.dart';
import 'database_provider.dart';
import 'session_providers.dart';

/// Provides the SearchRepository.
///
/// Depends on SessionDao and MessageDao for local search operations.
final searchRepositoryProvider = Provider<SearchRepository>((ref) {
  final sessionDao = ref.watch(sessionDaoProvider);
  final messageDao = ref.watch(messageDaoProvider);
  return SearchRepository(sessionDao: sessionDao, messageDao: messageDao);
});

/// Provides the IntentClassifier.
///
/// A simple stateless service — provider exists for testability
/// (can be overridden in tests with a mock classifier).
final intentClassifierProvider = Provider<IntentClassifier>((ref) {
  return IntentClassifier();
});

/// The current search query text.
///
/// Updated as the user types in the search bar (debounced at the UI layer).
final searchQueryProvider = StateProvider<String>((ref) => '');

/// The current active search filters.
///
/// Updated when the user selects filter chips on the search screen.
final searchFiltersProvider = StateProvider<SearchFilters>((ref) {
  return SearchFilters.empty;
});

/// Search results based on the current query and filters.
///
/// Automatically re-evaluates when searchQueryProvider or
/// searchFiltersProvider changes. Returns empty results for empty queries.
final searchResultsProvider = FutureProvider<SearchResults>((ref) async {
  final query = ref.watch(searchQueryProvider);
  final filters = ref.watch(searchFiltersProvider);

  if (query.trim().isEmpty && !filters.hasActiveFilters) {
    return SearchResults(query: query);
  }

  final searchRepo = ref.watch(searchRepositoryProvider);
  return searchRepo.searchEntries(query, filters: filters);
});

/// Memory recall for a specific question.
///
/// Takes a question string and returns a RecallResponse with the
/// synthesized answer and cited session IDs. Requires the Claude API
/// to be configured and online.
final recallAnswerProvider = FutureProvider.family<RecallResponse, String>((
  ref,
  question,
) async {
  final searchRepo = ref.watch(searchRepositoryProvider);
  final claudeService = ref.watch(claudeApiServiceProvider);

  // Search for relevant sessions using the question as query.
  final results = await searchRepo.searchEntries(question);
  if (results.isEmpty) {
    return RecallResponse(
      answer: "I couldn't find any entries matching that in your journal.",
    );
  }

  // Get formatted context for the top results.
  final sessionIds = results.items.map((r) => r.sessionId).toList();
  final context = await searchRepo.getSessionContext(sessionIds);

  // Call Claude for synthesis.
  return claudeService.recall(question: question, contextEntries: context);
});

/// All distinct mood tags across all sessions.
///
/// Used to populate the mood filter chips on the search screen.
final availableMoodTagsProvider = FutureProvider<List<String>>((ref) async {
  final sessionDao = ref.watch(sessionDaoProvider);
  return sessionDao.getDistinctMoodTags();
});

/// All distinct people mentioned across all sessions.
///
/// Used to populate the people filter chips on the search screen.
final availablePeopleProvider = FutureProvider<List<String>>((ref) async {
  final sessionDao = ref.watch(sessionDaoProvider);
  return sessionDao.getDistinctPeople();
});

/// All distinct topic tags across all sessions.
///
/// Used to populate the topic filter chips on the search screen.
final availableTopicTagsProvider = FutureProvider<List<String>>((ref) async {
  final sessionDao = ref.watch(sessionDaoProvider);
  return sessionDao.getDistinctTopicTags();
});

/// Total number of sessions in the database.
///
/// Used for progressive disclosure: search icon appears at 5+ sessions.
final sessionCountProvider = FutureProvider<int>((ref) async {
  final sessionDao = ref.watch(sessionDaoProvider);
  return sessionDao.countSessions();
});
