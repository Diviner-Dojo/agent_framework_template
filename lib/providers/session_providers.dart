// ===========================================================================
// file: lib/providers/session_providers.dart
// purpose: Riverpod providers that manage the active journaling session.
//
// This is the core state management layer of the app. The SessionNotifier
// orchestrates the entire conversation flow:
//   1. Start session → create DB record → get greeting → save greeting message
//   2. User sends message → save to DB → get follow-up → save follow-up
//   3. End session → generate summary → update session record
//
// State Ownership: SessionNotifier owns all mutable conversation state:
//   - activeSessionId (which session is in progress)
//   - followUpCount (how many follow-ups the agent has asked)
//   - usedQuestions (to prevent the agent from repeating itself)
//   - isWaitingForAgent (whether an async agent call is in progress)
//
// The AgentRepository is stateless — the notifier passes followUpCount
// and conversation history as parameters on each call. Data flows DOWN
// (provider → repository), never UP (repository never imports a provider).
//
// Phase 3 Change: All agent methods are now async (return Future<AgentResponse>).
// The notifier sets isWaitingForAgent=true before each agent call and clears it
// after, so the UI can show a loading indicator. Stale responses (arriving after
// session ended) are discarded by checking activeSessionId after await.
//
// Phase 5 Change: Intent classification + memory recall. Before calling
// getFollowUp(), sendMessage() classifies the user's message. High-confidence
// queries route to _handleRecallQuery() instead of the journaling follow-up.
// Ambiguous queries set pendingRecallQuery for inline confirmation (ADR-0013).
// ===========================================================================

import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/environment.dart';
import '../database/app_database.dart';
import '../database/daos/session_dao.dart';
import '../database/daos/message_dao.dart';
import '../repositories/agent_repository.dart';
import '../repositories/search_repository.dart';
import '../services/claude_api_service.dart';
import '../services/connectivity_service.dart';
import '../services/intent_classifier.dart';
import '../utils/uuid_generator.dart';
import '../utils/timestamp_utils.dart';
import 'auth_providers.dart';
import 'database_provider.dart';
import 'llm_providers.dart';
import 'search_providers.dart';
import 'sync_providers.dart';

/// Streams all sessions from the database for the session list screen.
///
/// This provider wraps SessionDao.watchAllSessions(), which automatically
/// re-emits whenever the journal_sessions table changes. The UI rebuilds
/// only when the data actually changes — no manual refresh needed.
final allSessionsProvider = StreamProvider<List<JournalSession>>((ref) {
  final sessionDao = ref.watch(sessionDaoProvider);
  return sessionDao.watchAllSessions();
});

/// Controls the page size for the landing page session list.
///
/// Incrementing this by 50 loads older entries. The paginated stream
/// re-emits whenever the table changes or the limit changes.
final sessionPageSizeProvider = StateProvider<int>((ref) => 50);

/// Streams sessions with a dynamic limit for the paginated landing page.
///
/// Watches [sessionPageSizeProvider] so that increasing the page size
/// automatically triggers a new stream with the larger limit.
final paginatedSessionsProvider = StreamProvider<List<JournalSession>>((ref) {
  final sessionDao = ref.watch(sessionDaoProvider);
  final pageSize = ref.watch(sessionPageSizeProvider);
  return sessionDao.watchSessionsPaginated(pageSize);
});

/// True when an empty session was closed (no USER messages).
///
/// The session is preserved in the database but closed immediately without
/// generating a summary. The UI watches this to show a SnackBar notification
/// and auto-pop back to the list. The UI resets it to false after displaying.
final wasAutoDiscardedProvider = StateProvider<bool>((ref) => false);

/// Holds the active session ID (null when no session is in progress).
///
/// When this has a value, the UI navigates to the journal session screen.
/// When null, the UI shows the session list.
///
/// This is a simple StateProvider because it's just a nullable String
/// that the SessionNotifier sets and clears.
final activeSessionIdProvider = StateProvider<String?>((ref) => null);

/// Streams messages for the active session.
///
/// Returns an empty stream when there's no active session.
/// Used by the journal session screen to display the chat messages.
final activeSessionMessagesProvider = StreamProvider<List<JournalMessage>>((
  ref,
) {
  final sessionId = ref.watch(activeSessionIdProvider);
  if (sessionId == null) return Stream.value([]);
  final messageDao = ref.watch(messageDaoProvider);
  return messageDao.watchMessagesForSession(sessionId);
});

/// The state for an active journaling session.
///
/// This is an immutable data class that holds all the conversation state
/// that the SessionNotifier manages. Using an immutable state class
/// (instead of mutable fields) makes it easy to reason about state changes
/// and works well with Riverpod's rebuild system.
/// Sentinel object for copyWith — distinguishes "not provided" from "set to null".
///
/// Dart's nullable parameter syntax can't distinguish between "caller didn't pass
/// a value" and "caller passed null". For fields like activeSessionId where null
/// is a meaningful value (no active session), we use a sentinel object as the
/// default so copyWith(activeSessionId: null) correctly clears the field.
const _sentinel = Object();

class SessionState {
  final String? activeSessionId;
  final int followUpCount;
  final List<String> usedQuestions;
  final bool isSessionEnding;

  /// True while awaiting an async agent response (greeting, follow-up, summary).
  /// The UI uses this to show a typing/loading indicator and disable the send button.
  final bool isWaitingForAgent;

  /// True after endSession() finishes saving the closing message.
  /// The UI shows a "Done" button instead of auto-popping, so the user
  /// can read the summary at their own pace.
  final bool isClosingComplete;

  /// Tracks all messages as role/content pairs for Claude API context.
  /// Layer B (Claude) needs the full conversation history for contextual responses.
  /// Layer A ignores this — it only uses latestUserMessage and conversationHistory.
  final List<Map<String, String>> conversationMessages;

  /// Non-null when the intent classifier detected an ambiguous query
  /// (confidence between 0.5 and 0.8). The UI shows an inline confirmation
  /// prompt; the user can accept (→ recall) or dismiss (→ journal follow-up).
  /// Cleared after the user responds to the confirmation.
  final String? pendingRecallQuery;

  /// Search terms extracted by the intent classifier for the pending query.
  final List<String> pendingSearchTerms;

  const SessionState({
    this.activeSessionId,
    this.followUpCount = 0,
    this.usedQuestions = const [],
    this.isSessionEnding = false,
    this.isWaitingForAgent = false,
    this.isClosingComplete = false,
    this.conversationMessages = const [],
    this.pendingRecallQuery,
    this.pendingSearchTerms = const [],
  });

  /// Create a copy with updated fields.
  ///
  /// Uses sentinel pattern for activeSessionId so that
  /// copyWith(activeSessionId: null) correctly clears the session ID,
  /// while omitting the parameter preserves the current value.
  SessionState copyWith({
    Object? activeSessionId = _sentinel,
    int? followUpCount,
    List<String>? usedQuestions,
    bool? isSessionEnding,
    bool? isWaitingForAgent,
    bool? isClosingComplete,
    List<Map<String, String>>? conversationMessages,
    Object? pendingRecallQuery = _sentinel,
    List<String>? pendingSearchTerms,
  }) {
    return SessionState(
      activeSessionId: identical(activeSessionId, _sentinel)
          ? this.activeSessionId
          : activeSessionId as String?,
      followUpCount: followUpCount ?? this.followUpCount,
      usedQuestions: usedQuestions ?? this.usedQuestions,
      isSessionEnding: isSessionEnding ?? this.isSessionEnding,
      isWaitingForAgent: isWaitingForAgent ?? this.isWaitingForAgent,
      isClosingComplete: isClosingComplete ?? this.isClosingComplete,
      conversationMessages: conversationMessages ?? this.conversationMessages,
      pendingRecallQuery: identical(pendingRecallQuery, _sentinel)
          ? this.pendingRecallQuery
          : pendingRecallQuery as String?,
      pendingSearchTerms: pendingSearchTerms ?? this.pendingSearchTerms,
    );
  }
}

/// Manages the active conversation flow.
///
/// This is the main business logic orchestrator. The UI calls three methods:
///   - startSession() → begins a new journal entry
///   - sendMessage(text) → processes user input, gets agent response
///   - endSession() → wraps up the session with a summary
///
/// The notifier coordinates between the DAOs (database) and the
/// AgentRepository (conversation logic), keeping both stateless.
class SessionNotifier extends StateNotifier<SessionState> {
  final SessionDao _sessionDao;
  final MessageDao _messageDao;
  final AgentRepository _agent;
  final IntentClassifier _intentClassifier;
  final SearchRepository _searchRepository;
  final ClaudeApiService _claudeApiService;
  final ConnectivityService _connectivityService;
  final Ref _ref;

  /// Confidence threshold for auto-routing to recall (no confirmation).
  static const _highConfidenceThreshold = 0.8;

  /// Confidence threshold for showing inline confirmation prompt.
  static const _ambiguousThreshold = 0.5;

  SessionNotifier({
    required SessionDao sessionDao,
    required MessageDao messageDao,
    required AgentRepository agent,
    required IntentClassifier intentClassifier,
    required SearchRepository searchRepository,
    required ClaudeApiService claudeApiService,
    required ConnectivityService connectivityService,
    required Ref ref,
  }) : _sessionDao = sessionDao,
       _messageDao = messageDao,
       _agent = agent,
       _intentClassifier = intentClassifier,
       _searchRepository = searchRepository,
       _claudeApiService = claudeApiService,
       _connectivityService = connectivityService,
       _ref = ref,
       super(const SessionState());

  /// Start a new journaling session.
  ///
  /// Creates a session record in the database, gets a time-appropriate
  /// greeting from the agent, and saves the greeting as the first message.
  ///
  /// The agent call is async (may hit Claude API when online). The notifier
  /// sets isWaitingForAgent=true immediately so the UI can show a loading
  /// indicator during the greeting fetch.
  ///
  /// Returns the session ID so the UI can navigate to the session screen.
  Future<String> startSession() async {
    // Guard: if a session is already active, return its ID instead of
    // creating a duplicate. Prevents orphaned sessions from rapid
    // assistant gestures or concurrent calls.
    if (state.activeSessionId != null) return state.activeSessionId!;

    final sessionId = generateUuid();
    final now = nowUtc();

    // Get the most recent session date for the gap check.
    final sessions = await _sessionDao.getAllSessionsByDate();
    final lastSessionDate = sessions.isNotEmpty
        ? sessions.first.startTime
        : null;

    // Create the session record in the database.
    // Using 'UTC' as timezone for Phase 1 — Phase 2 adds flutter_timezone.
    await _sessionDao.createSession(sessionId, now, 'UTC');

    // Lock the conversation layer for this session's duration (ADR-0017).
    _agent.lockLayerForSession();

    // Set loading state BEFORE the agent call (spec requirement: immediate flag).
    state = SessionState(activeSessionId: sessionId, isWaitingForAgent: true);
    _ref.read(activeSessionIdProvider.notifier).state = sessionId;

    // Get the greeting from the agent (async — may call Claude API).
    final greetingResponse = await _agent.getGreeting(
      lastSessionDate: lastSessionDate,
      now: now.toLocal(), // Agent uses local time for time-of-day greeting.
      sessionCount: sessions.length,
    );

    // Save the greeting as the first ASSISTANT message.
    await _messageDao.insertMessage(
      generateUuid(),
      sessionId,
      'ASSISTANT',
      greetingResponse.content,
      now,
    );

    // Track the greeting in conversation history for Claude context.
    state = state.copyWith(
      isWaitingForAgent: false,
      conversationMessages: [
        {'role': 'assistant', 'content': greetingResponse.content},
      ],
    );

    return sessionId;
  }

  /// Process a user message and get the agent's response.
  ///
  /// Saves the user message to the DB, then:
  ///   - If the user signaled "done", ends the session.
  ///   - Otherwise, gets a follow-up question from the agent (async).
  ///   - If the agent returns null (max follow-ups), ends the session.
  ///   - Otherwise, saves the follow-up as an ASSISTANT message.
  ///
  /// Stale response handling: If the user ends the session while a follow-up
  /// is being fetched (activeSessionId becomes null), the response is discarded.
  Future<void> sendMessage(String text, {String inputMethod = 'TEXT'}) async {
    final sessionId = state.activeSessionId;
    if (sessionId == null) return;

    final now = nowUtc();

    // Save the user's message to the database.
    await _messageDao.insertMessage(
      generateUuid(),
      sessionId,
      'USER',
      text,
      now,
      inputMethod: inputMethod,
    );

    // Track user message in conversation history for Claude context.
    final updatedMessages = [
      ...state.conversationMessages,
      {'role': 'user', 'content': text},
    ];
    state = state.copyWith(conversationMessages: updatedMessages);

    // Journal-only mode: save message silently, no follow-up or classification.
    if (_agent.journalOnlyMode) return;

    // Phase 5: Intent classification — detect recall queries before routing
    // to the normal journaling follow-up (ADR-0013 §3).
    final intentResult = _intentClassifier.classify(text);
    if (intentResult.type == IntentType.query &&
        intentResult.confidence >= _highConfidenceThreshold) {
      // High confidence: route directly to recall.
      await _handleRecallQuery(text, intentResult.searchTerms);
      return;
    }
    if (intentResult.type == IntentType.query &&
        intentResult.confidence >= _ambiguousThreshold) {
      // Ambiguous: save pending query for inline confirmation by the UI.
      state = state.copyWith(
        pendingRecallQuery: text,
        pendingSearchTerms: intentResult.searchTerms,
      );
      return;
    }

    // Check if the user wants to end the session.
    if (_agent.shouldEndSession(
      followUpCount: state.followUpCount,
      latestUserMessage: text,
    )) {
      await endSession();
      return;
    }

    // Set loading state before the async agent call.
    state = state.copyWith(isWaitingForAgent: true);

    // Get a follow-up question from the agent (async — may call Claude API).
    final followUpResponse = await _agent.getFollowUp(
      latestUserMessage: text,
      conversationHistory: state.usedQuestions,
      followUpCount: state.followUpCount,
      allMessages: state.conversationMessages,
    );

    // Stale response check: if the session ended while we were waiting,
    // discard the response. This happens when endSession() is called
    // concurrently (e.g., user presses back during agent wait).
    if (state.activeSessionId == null) return;

    state = state.copyWith(isWaitingForAgent: false);

    if (followUpResponse == null) {
      // Agent says conversation is done — insert bridging message so the
      // transition to closing doesn't feel abrupt.
      await _messageDao.insertMessage(
        generateUuid(),
        sessionId,
        'ASSISTANT',
        'Thanks for sharing today. Let me put together your summary...',
        nowUtc(),
      );
      await endSession();
      return;
    }

    final followUpText = followUpResponse.content;

    // Save the follow-up as an ASSISTANT message.
    await _messageDao.insertMessage(
      generateUuid(),
      sessionId,
      'ASSISTANT',
      followUpText,
      nowUtc(), // Slightly after user message timestamp.
    );

    // Update conversation state.
    state = state.copyWith(
      followUpCount: state.followUpCount + 1,
      usedQuestions: [...state.usedQuestions, followUpText],
      conversationMessages: [
        ...state.conversationMessages,
        {'role': 'assistant', 'content': followUpText},
      ],
    );
  }

  /// End the current session.
  ///
  /// Generates a summary (async — Claude extracts metadata when online),
  /// updates the session record with end time, summary, and metadata,
  /// then clears the active session state.
  ///
  /// When Claude is available (Layer B), the summary includes structured
  /// metadata: mood_tags, people, topic_tags. These are stored as JSON
  /// strings in the drift session table. When offline (Layer A), these
  /// fields remain null.
  Future<void> endSession() async {
    // Guard: if endSession is already in progress (e.g., back-press during
    // wrap-up), do not re-enter. Prevents duplicate closing messages.
    if (state.isSessionEnding) return;

    final sessionId = state.activeSessionId;
    if (sessionId == null) return;

    // Empty session guard: if the user hasn't sent any messages, close the
    // session quietly without generating a summary. The session is preserved
    // in the database (not deleted) so no data is ever lost without explicit
    // user action. The UI shows a brief "nothing recorded" notification.
    final userMessageCount = await _messageDao.getMessageCountByRole(
      sessionId,
      'USER',
    );
    if (userMessageCount == 0) {
      await _sessionDao.endSession(sessionId, nowUtc());
      _agent.unlockLayer();
      _ref.read(wasAutoDiscardedProvider.notifier).state = true;
      state = const SessionState();
      _ref.read(activeSessionIdProvider.notifier).state = null;
      return;
    }

    state = state.copyWith(isSessionEnding: true, isWaitingForAgent: true);

    // Get all user messages for summary generation.
    final messages = await _messageDao.getMessagesForSession(sessionId);
    final userMessages = messages
        .where((m) => m.role == 'USER')
        .map((m) => m.content)
        .toList();

    // Generate the summary (async — Claude generates summary + metadata when online).
    final summaryResponse = await _agent.generateSummary(
      userMessages: userMessages,
      allMessages: state.conversationMessages,
    );

    final summary = summaryResponse.content;

    // Save a closing ASSISTANT message.
    final closingMessage = summary.isNotEmpty
        ? "Here's what I captured: $summary"
        : "Thanks for journaling today!";
    await _messageDao.insertMessage(
      generateUuid(),
      sessionId,
      'ASSISTANT',
      closingMessage,
      nowUtc(),
    );

    // Extract metadata from the agent response (only populated by Layer B).
    // Convert List<String> to JSON strings for drift storage.
    final metadata = summaryResponse.metadata;
    final moodTagsJson = metadata?.moodTags != null
        ? jsonEncode(metadata!.moodTags)
        : null;
    final peopleJson = metadata?.people != null
        ? jsonEncode(metadata!.people)
        : null;
    final topicTagsJson = metadata?.topicTags != null
        ? jsonEncode(metadata!.topicTags)
        : null;

    // Use the Claude-generated summary if available, otherwise the local one.
    final storedSummary = metadata?.summary ?? summary;

    // Update the session record with end time, summary, and metadata.
    await _sessionDao.endSession(
      sessionId,
      nowUtc(),
      summary: storedSummary.isNotEmpty ? storedSummary : null,
      moodTags: moodTagsJson,
      people: peopleJson,
      topicTags: topicTagsJson,
    );

    // Unlock the conversation layer now that the session is ending.
    _agent.unlockLayer();

    // Signal that the closing summary is ready for the user to read.
    // Keep activeSessionId set so the message stream stays live.
    // The UI shows a "Done" button; dismissSession() clears state when tapped.
    state = state.copyWith(isWaitingForAgent: false, isClosingComplete: true);

    // Phase 4: Trigger non-blocking sync after session ends.
    // This runs in the background — sync failure doesn't affect the session flow.
    _triggerSyncAfterEnd(sessionId);
  }

  /// Trigger background sync for a completed session.
  ///
  /// Non-blocking: runs asynchronously without awaiting. If sync fails,
  /// the session's syncStatus stays PENDING/FAILED for later retry.
  void _triggerSyncAfterEnd(String sessionId) {
    final isAuthenticated = _ref.read(isAuthenticatedProvider);
    if (!isAuthenticated) return;

    final connectivityService = _ref.read(connectivityServiceProvider);
    if (!connectivityService.isOnline) return;

    // Fire-and-forget: don't await, don't block the session flow.
    final syncRepo = _ref.read(syncRepositoryProvider);
    syncRepo.syncSession(sessionId);
  }

  /// Resume a past session for continued journaling (ADR-0014).
  ///
  /// Guards: cannot resume if another session is active.
  /// Loads existing messages into conversation context, gets a resume
  /// greeting, and makes the session active again.
  Future<String?> resumeSession(String sessionId) async {
    // Guard: cannot resume if a session is already active.
    if (state.activeSessionId != null) return null;

    // Resume the session in the database.
    final updated = await _sessionDao.resumeSession(sessionId);
    if (updated == 0) return null;

    // Load existing messages into conversation context.
    final messages = await _messageDao.getMessagesForSession(sessionId);
    final conversationMessages = messages.map((m) {
      final role = m.role == 'USER' ? 'user' : 'assistant';
      return {'role': role, 'content': m.content};
    }).toList();

    // Count follow-ups by USER messages. Each user message corresponds to
    // one follow-up round. Using USER count avoids miscounting closing and
    // bridging ASSISTANT messages (greeting, summary, bridging) as follow-ups.
    final followUpCount = messages.where((m) => m.role == 'USER').length;

    // Lock the conversation layer for this resumed session (ADR-0017).
    _agent.lockLayerForSession();

    // Set state before getting greeting.
    state = SessionState(
      activeSessionId: sessionId,
      isWaitingForAgent: true,
      followUpCount: followUpCount,
      conversationMessages: conversationMessages,
    );
    _ref.read(activeSessionIdProvider.notifier).state = sessionId;

    // Get resume greeting.
    final greetingResponse = await _agent.getResumeGreeting();

    // Save the resume greeting as an ASSISTANT message.
    await _messageDao.insertMessage(
      generateUuid(),
      sessionId,
      'ASSISTANT',
      greetingResponse.content,
      nowUtc(),
    );

    // Update state.
    state = state.copyWith(
      isWaitingForAgent: false,
      conversationMessages: [
        ...state.conversationMessages,
        {'role': 'assistant', 'content': greetingResponse.content},
      ],
    );

    return sessionId;
  }

  /// Resume the most recent open session, or return null if none exists.
  ///
  /// Used by voice commands like "continue my journal" or "add to today's
  /// entry." Finds the most recent session with no endTime and resumes it.
  Future<String?> resumeLatestSession() async {
    final sessions = await _sessionDao.getAllSessionsByDate();
    final openSession = sessions.cast<JournalSession?>().firstWhere(
      (s) => s!.endTime == null,
      orElse: () => null,
    );
    if (openSession == null) return null;
    return resumeSession(openSession.sessionId);
  }

  /// Discard the active session without saving a summary.
  ///
  /// Clears state immediately, then deletes messages and session from the DB
  /// in a single transaction to prevent orphaned data.
  /// Used when the user explicitly discards or when the empty session guard
  /// triggers auto-discard (ADR-0014).
  Future<void> discardSession() async {
    final sessionId = state.activeSessionId;
    if (sessionId == null) return;

    // Unlock the conversation layer.
    _agent.unlockLayer();

    // Clear state immediately so the UI doesn't wait for DB operations.
    state = const SessionState();
    _ref.read(activeSessionIdProvider.notifier).state = null;

    // Transactional cascade delete: messages first, then session.
    await _sessionDao.deleteSessionCascade(_messageDao, sessionId);
  }

  /// Dismiss the completed session and clear all state.
  ///
  /// Called by the UI after the user has read the closing summary and tapped
  /// "Done". This is the only path that clears activeSessionId after a
  /// session ends.
  void dismissSession() {
    _agent.unlockLayer();
    state = const SessionState();
    _ref.read(activeSessionIdProvider.notifier).state = null;
  }

  // =========================================================================
  // Phase 5: Memory Recall (ADR-0013)
  // =========================================================================

  /// Confirm the pending recall query (user accepted inline prompt).
  ///
  /// Called by the UI when the user taps "Search my journal" on the
  /// ambiguous intent confirmation widget.
  Future<void> confirmRecallQuery() async {
    final query = state.pendingRecallQuery;
    final terms = state.pendingSearchTerms;
    if (query == null) return;

    // Clear the pending state before handling.
    state = state.copyWith(
      pendingRecallQuery: null,
      pendingSearchTerms: const [],
    );
    await _handleRecallQuery(query, terms);
  }

  /// Dismiss the pending recall query (user chose to continue journaling).
  ///
  /// Routes the original message through the normal follow-up path.
  Future<void> dismissRecallQuery() async {
    final query = state.pendingRecallQuery;
    if (query == null) return;

    // Clear the pending state.
    state = state.copyWith(
      pendingRecallQuery: null,
      pendingSearchTerms: const [],
    );

    // Route through normal journaling follow-up.
    final sessionId = state.activeSessionId;
    if (sessionId == null) return;

    // Check end-session signal first.
    if (_agent.shouldEndSession(
      followUpCount: state.followUpCount,
      latestUserMessage: query,
    )) {
      await endSession();
      return;
    }

    state = state.copyWith(isWaitingForAgent: true);
    final followUpResponse = await _agent.getFollowUp(
      latestUserMessage: query,
      conversationHistory: state.usedQuestions,
      followUpCount: state.followUpCount,
      allMessages: state.conversationMessages,
    );

    // Stale response check: session may have ended during the async call.
    if (state.activeSessionId == null) return;
    state = state.copyWith(isWaitingForAgent: false);

    if (followUpResponse == null) {
      await _messageDao.insertMessage(
        generateUuid(),
        sessionId,
        'ASSISTANT',
        'Thanks for sharing today. Let me put together your summary...',
        nowUtc(),
      );
      await endSession();
      return;
    }

    final followUpText = followUpResponse.content;
    await _messageDao.insertMessage(
      generateUuid(),
      sessionId,
      'ASSISTANT',
      followUpText,
      nowUtc(),
    );

    state = state.copyWith(
      followUpCount: state.followUpCount + 1,
      usedQuestions: [...state.usedQuestions, followUpText],
      conversationMessages: [
        ...state.conversationMessages,
        {'role': 'assistant', 'content': followUpText},
      ],
    );
  }

  /// Handle a recall query: search local data and synthesize an answer.
  ///
  /// Flow (ADR-0013 §3):
  ///   1. Search for matching sessions using search terms
  ///   2. If no matches: save "couldn't find" message
  ///   3. If matches and online: format context, call Claude synthesis
  ///   4. If matches but offline: save raw session list as fallback
  ///   5. Validate cited session IDs against local DB before saving
  Future<void> _handleRecallQuery(
    String question,
    List<String> searchTerms,
  ) async {
    final sessionId = state.activeSessionId;
    if (sessionId == null) return;

    state = state.copyWith(isWaitingForAgent: true);

    // Search local data using the extracted search terms.
    // Hoisted above try so catch can reuse results on Claude API failure.
    final searchQuery = searchTerms.isNotEmpty
        ? searchTerms.join(' ')
        : question;
    final results = await _searchRepository.searchEntries(searchQuery);

    try {
      // Stale check: session may have ended during search.
      if (state.activeSessionId == null) return;

      if (results.isEmpty) {
        // Check total session count for context-appropriate response.
        final totalCount = await _sessionDao.countSessions();
        final String noMatchMsg;
        if (totalCount == 0) {
          noMatchMsg =
              "You don't have any journal entries yet. Once you "
              "start journaling, I'll be able to help you recall your entries.";
        } else if (totalCount < 5) {
          noMatchMsg =
              "I only have $totalCount ${totalCount == 1 ? 'entry' : 'entries'} "
              "so far. As your journal grows, I'll be able to help you "
              'recall more.';
        } else {
          noMatchMsg =
              "I couldn't find any entries matching that in your journal.";
        }

        await _saveRecallMessage(sessionId, noMatchMsg);
        return;
      }

      // Format context for Claude.
      final sessionIds = results.items.map((r) => r.sessionId).toList();

      // If offline: return raw session list without synthesis.
      if (!_connectivityService.isOnline || !_claudeApiService.isConfigured) {
        final chips = results.items
            .take(5)
            .map((item) {
              final date = formatShortDate(item.session.startTime);
              final summary = item.session.summary ?? 'Untitled session';
              return '$date — $summary';
            })
            .join('\n');

        final offlineMsg =
            'Your journal has ${results.count} entries about that:\n\n$chips';
        await _saveRecallMessage(
          sessionId,
          offlineMsg,
          citedSessionIds: sessionIds.take(5).toList(),
          isOffline: true,
        );
        return;
      }

      // Online: get formatted context and call Claude for synthesis.
      final context = await _searchRepository.getSessionContext(sessionIds);
      final recallResponse = await _claudeApiService.recall(
        question: question,
        contextEntries: context,
      );

      // Stale check after async call.
      if (state.activeSessionId == null) return;

      // Validate cited session IDs against local DB (hallucination guard).
      final validatedIds = <String>[];
      for (final citedId in recallResponse.citedSessionIds) {
        final exists = await _sessionDao.getSessionById(citedId);
        if (exists != null) {
          validatedIds.add(citedId);
        }
      }

      await _saveRecallMessage(
        sessionId,
        recallResponse.answer,
        citedSessionIds: validatedIds,
      );
    } on ClaudeApiException catch (e) {
      // Claude API failed — fall back to showing the results we already have.
      if (kDebugMode) {
        debugPrint('Recall Claude API failed: $e');
      }
      // Reuse the results from the search above (already in scope).
      if (results.isEmpty) {
        await _saveRecallMessage(
          sessionId,
          "I couldn't find any entries matching that in your journal.",
        );
      } else {
        final chips = results.items
            .take(5)
            .map((item) {
              final date = formatShortDate(item.session.startTime);
              final summary = item.session.summary ?? 'Untitled session';
              return '$date — $summary';
            })
            .join('\n');
        await _saveRecallMessage(
          sessionId,
          'I found ${results.count} related entries but '
          "couldn't generate a summary right now:\n\n$chips",
          citedSessionIds: results.items
              .take(5)
              .map((r) => r.sessionId)
              .toList(),
          isOffline: true,
        );
      }
    } finally {
      if (mounted) {
        state = state.copyWith(isWaitingForAgent: false);
      }
    }
  }

  /// Save a recall response as an ASSISTANT message with recall metadata.
  ///
  /// The message content stores the recall answer. Cited session IDs and
  /// the isOffline flag are stored as JSON in the entitiesJson column
  /// for the UI to render citation chips and offline styling.
  Future<void> _saveRecallMessage(
    String sessionId,
    String content, {
    List<String> citedSessionIds = const [],
    bool isOffline = false,
  }) async {
    // Build recall metadata JSON stored in the entitiesJson column.
    final recallMetadata = jsonEncode({
      'type': 'recall',
      'cited_sessions': citedSessionIds,
      'is_offline': isOffline,
    });

    await _messageDao.insertMessage(
      generateUuid(),
      sessionId,
      'ASSISTANT',
      content,
      nowUtc(),
      entitiesJson: recallMetadata,
    );

    // Track in conversation messages so Claude has recall context.
    state = state.copyWith(
      conversationMessages: [
        ...state.conversationMessages,
        {'role': 'assistant', 'content': content},
      ],
    );
  }
}

/// Deletes a completed session and its messages from the database.
///
/// Accepts [SessionDao] and [MessageDao] directly so it can be called from
/// both providers (Ref) and widgets (WidgetRef). The session list auto-updates
/// via drift's stream because [allSessionsProvider] watches the table.
/// Uses a transaction to prevent orphaned data on partial failure.
Future<void> deleteSessionCascade(
  SessionDao sessionDao,
  MessageDao messageDao,
  String sessionId,
) async {
  await sessionDao.deleteSessionCascade(messageDao, sessionId);
}

/// Provides the compile-time environment configuration.
///
/// Uses --dart-define values baked in at build time. When the values are
/// missing (no --dart-define), Environment.isConfigured returns false and
/// the app uses Layer A (rule-based) exclusively.
final environmentProvider = Provider<Environment>((ref) {
  return const Environment();
});

/// Provides the connectivity monitoring service.
///
/// This is a singleton that monitors network state. It must be initialized
/// once at app startup via connectivityService.initialize().
/// The provider calls dispose() on cleanup.
final connectivityServiceProvider = Provider<ConnectivityService>((ref) {
  final service = ConnectivityService();
  ref.onDispose(() => service.dispose());
  return service;
});

/// Provides the Claude API client.
///
/// Depends on Environment for the Edge Function URL and anon key.
/// When Environment.isConfigured is false, the service self-disables
/// (isConfigured returns false) and AgentRepository uses Layer A only.
final claudeApiServiceProvider = Provider<ClaudeApiService>((ref) {
  final environment = ref.watch(environmentProvider);
  final supabaseService = ref.watch(supabaseServiceProvider);
  return ClaudeApiService(
    environment: environment,
    accessTokenProvider: () => supabaseService.accessToken,
  );
});

/// Provider for the AgentRepository.
///
/// Injects ClaudeApiService, ConnectivityService, and LocalLlmLayer for
/// Layer B support (both remote and local). Reads user preferences
/// (preferClaude, journalOnlyMode) and applies them.
/// When services are unavailable, the repository falls back to Layer A.
///
/// The localLlmLayer is injected via constructor (not mutable field) so
/// that provider rebuilds correctly propagate layer availability (ADR-0017).
final agentRepositoryProvider = Provider<AgentRepository>((ref) {
  final claudeService = ref.watch(claudeApiServiceProvider);
  final connectivityService = ref.watch(connectivityServiceProvider);
  final preferClaude = ref.watch(preferClaudeProvider);
  final journalOnlyMode = ref.watch(journalOnlyModeProvider);
  final localLlmLayer = ref.watch(localLlmLayerProvider);

  final repo = AgentRepository(
    claudeService: claudeService,
    connectivityService: connectivityService,
    localLlmLayer: localLlmLayer,
  );
  repo.setPreferClaude(preferClaude);
  repo.setJournalOnlyMode(journalOnlyMode);
  return repo;
});

/// Provider for the SessionNotifier.
///
/// This is a StateNotifierProvider because SessionNotifier manages
/// mutable state (the active session, follow-up count, etc.).
///
/// The UI watches this provider to react to session state changes.
final sessionNotifierProvider =
    StateNotifierProvider<SessionNotifier, SessionState>((ref) {
      return SessionNotifier(
        sessionDao: ref.watch(sessionDaoProvider),
        messageDao: ref.watch(messageDaoProvider),
        agent: ref.watch(agentRepositoryProvider),
        intentClassifier: ref.watch(intentClassifierProvider),
        searchRepository: ref.watch(searchRepositoryProvider),
        claudeApiService: ref.watch(claudeApiServiceProvider),
        connectivityService: ref.watch(connectivityServiceProvider),
        ref: ref,
      );
    });
