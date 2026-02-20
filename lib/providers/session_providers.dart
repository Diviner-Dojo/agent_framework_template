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
//
// The AgentRepository is stateless — the notifier passes followUpCount
// and conversation history as parameters on each call. Data flows DOWN
// (provider → repository), never UP (repository never imports a provider).
// ===========================================================================

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../database/app_database.dart';
import '../database/daos/session_dao.dart';
import '../database/daos/message_dao.dart';
import '../repositories/agent_repository.dart';
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
class SessionState {
  final String? activeSessionId;
  final int followUpCount;
  final List<String> usedQuestions;
  final bool isSessionEnding;

  const SessionState({
    this.activeSessionId,
    this.followUpCount = 0,
    this.usedQuestions = const [],
    this.isSessionEnding = false,
  });

  SessionState copyWith({
    String? activeSessionId,
    int? followUpCount,
    List<String>? usedQuestions,
    bool? isSessionEnding,
  }) {
    return SessionState(
      activeSessionId: activeSessionId ?? this.activeSessionId,
      followUpCount: followUpCount ?? this.followUpCount,
      usedQuestions: usedQuestions ?? this.usedQuestions,
      isSessionEnding: isSessionEnding ?? this.isSessionEnding,
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

    // Get the greeting from the agent.
    final greeting = _agent.getGreeting(
      lastSessionDate: lastSessionDate,
      now: now.toLocal(), // Agent uses local time for time-of-day greeting.
    );

    // Save the greeting as the first ASSISTANT message.
    await _messageDao.insertMessage(
      generateUuid(),
      sessionId,
      'ASSISTANT',
      greeting,
      now,
    );

    // Update state — this triggers UI rebuilds.
    state = SessionState(activeSessionId: sessionId);

    // Also update the global active session ID provider.
    _ref.read(activeSessionIdProvider.notifier).state = sessionId;

    return sessionId;
  }

  /// Process a user message and get the agent's response.
  ///
  /// Saves the user message to the DB, then:
  ///   - If the user signaled "done", ends the session.
  ///   - Otherwise, gets a follow-up question from the agent.
  ///   - If the agent returns null (max follow-ups), ends the session.
  ///   - Otherwise, saves the follow-up as an ASSISTANT message.
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

    // Check if the user wants to end the session.
    if (_agent.shouldEndSession(
      followUpCount: state.followUpCount,
      latestUserMessage: text,
    )) {
      await endSession();
      return;
    }

    // Get a follow-up question from the agent.
    final followUp = _agent.getFollowUp(
      latestUserMessage: text,
      conversationHistory: state.usedQuestions,
      followUpCount: state.followUpCount,
    );

    if (followUp == null) {
      // Agent says conversation is done.
      await endSession();
      return;
    }

    // Save the follow-up as an ASSISTANT message.
    await _messageDao.insertMessage(
      generateUuid(),
      sessionId,
      'ASSISTANT',
      followUp,
      nowUtc(), // Slightly after user message timestamp.
    );

    // Update conversation state.
    state = state.copyWith(
      followUpCount: state.followUpCount + 1,
      usedQuestions: [...state.usedQuestions, followUp],
    );
  }

  /// End the current session.
  ///
  /// Generates a local summary from all user messages, updates the
  /// session record with the end time and summary, then clears the
  /// active session state.
  Future<void> endSession() async {
    // Guard: if endSession is already in progress (e.g., back-press during
    // wrap-up), do not re-enter. Prevents duplicate closing messages.
    if (state.isSessionEnding) return;

    final sessionId = state.activeSessionId;
    if (sessionId == null) return;

    state = state.copyWith(isSessionEnding: true);

    // Get all user messages for summary generation.
    final messages = await _messageDao.getMessagesForSession(sessionId);
    final userMessages = messages
        .where((m) => m.role == 'USER')
        .map((m) => m.content)
        .toList();

    // Generate the summary.
    final summary = _agent.generateLocalSummary(userMessages);

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

    // Update the session record with end time and summary.
    await _sessionDao.endSession(
      sessionId,
      nowUtc(),
      summary: summary.isNotEmpty ? summary : null,
    );

    // Clear the active session state.
    state = const SessionState();
    _ref.read(activeSessionIdProvider.notifier).state = null;
  }
}

/// Provider for the AgentRepository.
///
/// Stateless, so it's a simple Provider (not a StateProvider).
final agentRepositoryProvider = Provider<AgentRepository>((ref) {
  return AgentRepository();
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
