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
// ===========================================================================

import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/environment.dart';
import '../database/app_database.dart';
import '../database/daos/session_dao.dart';
import '../database/daos/message_dao.dart';
import '../repositories/agent_repository.dart';
import '../services/claude_api_service.dart';
import '../services/connectivity_service.dart';
import '../utils/uuid_generator.dart';
import '../utils/timestamp_utils.dart';
import 'database_provider.dart';

/// Streams all sessions from the database for the session list screen.
///
/// This provider wraps SessionDao.watchAllSessions(), which automatically
/// re-emits whenever the journal_sessions table changes. The UI rebuilds
/// only when the data actually changes — no manual refresh needed.
final allSessionsProvider = StreamProvider<List<JournalSession>>((ref) {
  final sessionDao = ref.watch(sessionDaoProvider);
  return sessionDao.watchAllSessions();
});

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

  /// Tracks all messages as role/content pairs for Claude API context.
  /// Layer B (Claude) needs the full conversation history for contextual responses.
  /// Layer A ignores this — it only uses latestUserMessage and conversationHistory.
  final List<Map<String, String>> conversationMessages;

  const SessionState({
    this.activeSessionId,
    this.followUpCount = 0,
    this.usedQuestions = const [],
    this.isSessionEnding = false,
    this.isWaitingForAgent = false,
    this.conversationMessages = const [],
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
    List<Map<String, String>>? conversationMessages,
  }) {
    return SessionState(
      activeSessionId: identical(activeSessionId, _sentinel)
          ? this.activeSessionId
          : activeSessionId as String?,
      followUpCount: followUpCount ?? this.followUpCount,
      usedQuestions: usedQuestions ?? this.usedQuestions,
      isSessionEnding: isSessionEnding ?? this.isSessionEnding,
      isWaitingForAgent: isWaitingForAgent ?? this.isWaitingForAgent,
      conversationMessages: conversationMessages ?? this.conversationMessages,
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
  final Ref _ref;

  SessionNotifier({
    required SessionDao sessionDao,
    required MessageDao messageDao,
    required AgentRepository agent,
    required Ref ref,
  }) : _sessionDao = sessionDao,
       _messageDao = messageDao,
       _agent = agent,
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
  Future<void> sendMessage(String text) async {
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
    );

    // Track user message in conversation history for Claude context.
    final updatedMessages = [
      ...state.conversationMessages,
      {'role': 'user', 'content': text},
    ];
    state = state.copyWith(conversationMessages: updatedMessages);

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
      // Agent says conversation is done.
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

    // Clear the active session state.
    state = const SessionState();
    _ref.read(activeSessionIdProvider.notifier).state = null;
  }
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
  return ClaudeApiService(environment: environment);
});

/// Provider for the AgentRepository.
///
/// Injects ClaudeApiService and ConnectivityService for Layer B support.
/// When either service is unavailable, the repository falls back to Layer A.
final agentRepositoryProvider = Provider<AgentRepository>((ref) {
  final claudeService = ref.watch(claudeApiServiceProvider);
  final connectivityService = ref.watch(connectivityServiceProvider);
  return AgentRepository(
    claudeService: claudeService,
    connectivityService: connectivityService,
  );
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
        ref: ref,
      );
    });
