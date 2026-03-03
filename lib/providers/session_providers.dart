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
import 'dart:io';

import 'package:drift/drift.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/environment.dart';
import '../database/app_database.dart';
import '../database/daos/calendar_event_dao.dart';
import '../database/daos/message_dao.dart';
import '../database/daos/photo_dao.dart';
import '../database/daos/session_dao.dart';
import '../database/daos/task_dao.dart';
import '../services/event_extraction_service.dart';
import '../services/google_calendar_service.dart';
import '../services/google_tasks_service.dart';
import '../services/task_extraction_service.dart';
import '../services/photo_service.dart';
import '../services/video_service.dart';
import '../database/daos/video_dao.dart';
import '../repositories/agent_repository.dart';
import '../repositories/search_repository.dart';
import '../services/claude_api_service.dart';
import '../services/connectivity_service.dart';
import '../services/intent_classifier.dart';
import '../utils/uuid_generator.dart';
import '../utils/timestamp_utils.dart';
import 'package:flutter_timezone/flutter_timezone.dart';
import 'auth_providers.dart';
import 'calendar_providers.dart';
import 'database_provider.dart';
import 'task_providers.dart';
import 'llm_providers.dart';
import 'location_providers.dart';
import 'onboarding_providers.dart';
import 'personality_providers.dart';
import 'photo_providers.dart';
import 'search_providers.dart';
import 'sync_providers.dart';
import 'video_providers.dart';
import 'voice_providers.dart';

/// IANA timezone for the current device (e.g., 'America/Los_Angeles').
///
/// Uses [FlutterTimezone] to get the system timezone. Tests should override
/// this provider with a known IANA timezone string.
// coverage:ignore-start
final deviceTimezoneProvider = FutureProvider<String>((ref) async {
  try {
    return await FlutterTimezone.getLocalTimezone();
  } on Exception {
    return 'UTC';
  }
});
// coverage:ignore-end

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

  /// Non-null when a calendar event intent was detected and is pending
  /// user confirmation. Contains the raw user message. The UI shows an
  /// inline confirmation card with extracted event details.
  /// Follows the same pattern as [pendingRecallQuery] (ADR-0020 §7).
  final String? pendingCalendarEvent;

  /// Non-null when a reminder intent was detected and is pending user
  /// confirmation. Contains the raw user message.
  final String? pendingReminder;

  /// The extracted event details from [pendingCalendarEvent] or
  /// [pendingReminder]. Null when extraction hasn't run or failed.
  final ExtractedEvent? pendingExtractedEvent;

  /// True while the event extraction service is processing.
  final bool isExtracting;

  /// Error message if extraction failed.
  final String? extractionError;

  /// Non-null when a task intent was detected and is pending user
  /// confirmation. Contains the raw user message.
  final String? pendingTask;

  /// The extracted task details from [pendingTask].
  final ExtractedTask? pendingExtractedTask;

  /// True while the task extraction service is processing.
  final bool isExtractingTask;

  /// Error message if task extraction failed.
  final String? taskExtractionError;

  /// Recent session summaries for conversational continuity (ADR-0023).
  ///
  /// Each map has 'date' and 'summary' keys. Populated at session start
  /// and passed to the agent on greeting and follow-up calls.
  final List<Map<String, String>> sessionSummaries;

  /// The journaling mode for the active session (e.g., 'onboarding').
  ///
  /// Tracked in state so endSession() can check without a DB read-back.
  /// Immutable once the session starts (ADR-0025).
  final String? journalingMode;

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
    this.pendingCalendarEvent,
    this.pendingReminder,
    this.pendingExtractedEvent,
    this.isExtracting = false,
    this.extractionError,
    this.pendingTask,
    this.pendingExtractedTask,
    this.isExtractingTask = false,
    this.taskExtractionError,
    this.sessionSummaries = const [],
    this.journalingMode,
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
    Object? pendingCalendarEvent = _sentinel,
    Object? pendingReminder = _sentinel,
    Object? pendingExtractedEvent = _sentinel,
    bool? isExtracting,
    Object? extractionError = _sentinel,
    Object? pendingTask = _sentinel,
    Object? pendingExtractedTask = _sentinel,
    bool? isExtractingTask,
    Object? taskExtractionError = _sentinel,
    List<Map<String, String>>? sessionSummaries,
    Object? journalingMode = _sentinel,
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
      pendingCalendarEvent: identical(pendingCalendarEvent, _sentinel)
          ? this.pendingCalendarEvent
          : pendingCalendarEvent as String?,
      pendingReminder: identical(pendingReminder, _sentinel)
          ? this.pendingReminder
          : pendingReminder as String?,
      pendingExtractedEvent: identical(pendingExtractedEvent, _sentinel)
          ? this.pendingExtractedEvent
          : pendingExtractedEvent as ExtractedEvent?,
      isExtracting: isExtracting ?? this.isExtracting,
      extractionError: identical(extractionError, _sentinel)
          ? this.extractionError
          : extractionError as String?,
      pendingTask: identical(pendingTask, _sentinel)
          ? this.pendingTask
          : pendingTask as String?,
      pendingExtractedTask: identical(pendingExtractedTask, _sentinel)
          ? this.pendingExtractedTask
          : pendingExtractedTask as ExtractedTask?,
      isExtractingTask: isExtractingTask ?? this.isExtractingTask,
      taskExtractionError: identical(taskExtractionError, _sentinel)
          ? this.taskExtractionError
          : taskExtractionError as String?,
      sessionSummaries: sessionSummaries ?? this.sessionSummaries,
      journalingMode: identical(journalingMode, _sentinel)
          ? this.journalingMode
          : journalingMode as String?,
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
  /// [journalingMode] — optional mode string (e.g., 'onboarding', 'gratitude')
  /// to set on the session and pass to the agent for mode-specific greeting.
  ///
  /// Returns the session ID so the UI can navigate to the session screen.
  Future<String> startSession({String? journalingMode}) async {
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

    // Create the session record with the device's IANA timezone.
    final timezone = await _ref.read(deviceTimezoneProvider.future);
    await _sessionDao.createSession(sessionId, now, timezone);

    // Set journaling mode if provided (e.g., 'onboarding', 'gratitude').
    if (journalingMode != null) {
      await _sessionDao.updateJournalingMode(sessionId, journalingMode);
    }

    // Fire-and-forget location capture (Phase 10 — ADR-0019).
    // Must occur AFTER createSession so the session row exists for
    // updateSessionLocation. Read preference imperatively (not watched).
    // The unawaited future runs in the background — never blocks the greeting.
    final locationEnabled = _ref.read(locationEnabledProvider);
    if (locationEnabled) {
      _captureLocationAsync(sessionId);
    }

    // Fetch recent session summaries for conversational continuity (ADR-0023).
    final recentSessions = await _sessionDao.getRecentCompletedSessions(
      limit: 5,
    );
    final summaries = recentSessions
        .where((s) => s.summary != null && s.summary!.isNotEmpty)
        .map((s) {
          final date = s.startTime.toIso8601String().substring(0, 10);
          final summary = s.summary!.length > 200
              ? s.summary!.substring(0, 200)
              : s.summary!;
          return {'date': date, 'summary': summary};
        })
        .toList();

    // Lock the conversation layer for this session's duration (ADR-0017).
    _agent.lockLayerForSession();

    // Set loading state BEFORE the agent call (spec requirement: immediate flag).
    state = SessionState(
      activeSessionId: sessionId,
      isWaitingForAgent: true,
      sessionSummaries: summaries,
      journalingMode: journalingMode,
    );
    _ref.read(activeSessionIdProvider.notifier).state = sessionId;

    // Read voice mode imperatively (not watched) to pass to agent layers.
    final isVoiceMode = _ref.read(voiceModeEnabledProvider);

    // Get the greeting from the agent (async — may call Claude API).
    final greetingResponse = await _agent.getGreeting(
      lastSessionDate: lastSessionDate,
      now: now.toLocal(), // Agent uses local time for time-of-day greeting.
      sessionCount: sessions.length,
      sessionSummaries: summaries,
      journalingMode: journalingMode,
      isVoiceMode: isVoiceMode,
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

    // End-session signals work in ALL modes including journal-only.
    // This runs BEFORE intent classification intentionally: _doneSignals are
    // short exact-match words ("bye", "done", "goodbye") that the intent
    // classifier would route as IntentType.journal anyway — no collision risk.
    if (_agent.shouldEndSession(
      followUpCount: state.followUpCount,
      latestUserMessage: text,
    )) {
      await endSession();
      return;
    }

    // Phase 5+11: Intent classification — detect recall, calendar, task, and
    // reminder intents before routing to the journaling follow-up.
    // Runs in all modes so task/calendar intents work even in journal-only mode.
    // Uses the top-ranked intent from classifyMulti() (ADR-0013, ADR-0020).
    final intentResult = _intentClassifier.classify(text);
    final handled = await _routeByIntent(text, intentResult);
    if (handled) {
      // Handled intents don't generate AI responses — resume voice loop.
      await _resumeOrchestratorIfVoiceMode();
      return;
    }

    // Journal-only mode: message recorded, special intents handled above,
    // but no AI conversational follow-up. Resume voice loop immediately.
    if (_agent.journalOnlyMode) {
      await _resumeOrchestratorIfVoiceMode();
      return;
    }

    // Set loading state before the async agent call.
    state = state.copyWith(isWaitingForAgent: true);

    // Get a follow-up question from the agent (async — may call Claude API).
    final isVoiceMode = _ref.read(voiceModeEnabledProvider);
    final followUpResponse = await _agent.getFollowUp(
      latestUserMessage: text,
      conversationHistory: state.usedQuestions,
      followUpCount: state.followUpCount,
      allMessages: state.conversationMessages,
      sessionSummaries: state.sessionSummaries,
      isVoiceMode: isVoiceMode,
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

    // Empty session guard: if the user hasn't sent any messages, delete the
    // session entirely so it never appears in the journal list. The greeting
    // is AI-only content — there is nothing for the user to recover.
    final userMessageCount = await _messageDao.getMessageCountByRole(
      sessionId,
      'USER',
    );
    if (userMessageCount == 0) {
      // Mark onboarding complete before state is cleared (needs journalingMode).
      await _completeOnboardingIfNeeded();
      // Signal UI to show "nothing recorded" notification.
      _ref.read(wasAutoDiscardedProvider.notifier).state = true;
      // Delete session entirely — empty sessions (AI greeting only) must not
      // appear in the journal list (user never contributed content).
      await discardSession();
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

    // If this was an onboarding session, mark onboarding complete (ADR-0026).
    await _completeOnboardingIfNeeded();

    // Signal that the closing summary is ready for the user to read.
    // Keep activeSessionId set so the message stream stays live.
    // The UI shows a "Done" button; dismissSession() clears state when tapped.
    state = state.copyWith(isWaitingForAgent: false, isClosingComplete: true);

    // Phase 4: Trigger non-blocking sync after session ends.
    // This runs in the background — sync failure doesn't affect the session flow.
    _triggerSyncAfterEnd(sessionId);
  }

  /// Mark onboarding complete if the active session is an onboarding session.
  ///
  /// Uses in-memory state (not a DB read-back) to avoid a silent-null failure
  /// path if the DB write didn't commit. Called from both the normal and
  /// empty-session paths of endSession().
  Future<void> _completeOnboardingIfNeeded() async {
    if (state.journalingMode == 'onboarding') {
      await _ref.read(onboardingNotifierProvider.notifier).completeOnboarding();
    }
  }

  /// Trigger background sync for a completed session.
  ///
  /// Fire-and-forget location capture for a session (Phase 10 — ADR-0019).
  ///
  /// Called from [startSession] after the session row is created. Runs
  /// asynchronously — never blocks the greeting or session flow. If
  /// location capture fails for any reason (permission denied, timeout,
  /// service disabled), the session continues normally without location.
  ///
  /// Coordinates are reduced to 2 decimal places by [LocationService]
  /// before being passed to the DAO.
  void _captureLocationAsync(String sessionId) {
    Future<void>(() async {
      try {
        final locationService = _ref.read(locationServiceProvider);
        final result = await locationService.getLocation();
        if (result == null) return;

        // Verify session still exists (user may have discarded it).
        if (state.activeSessionId != sessionId) return;

        await _sessionDao.updateSessionLocation(
          sessionId,
          latitude: result.latitude,
          longitude: result.longitude,
          locationAccuracy: result.accuracy,
          locationName: result.locationName,
        );
      } on Exception catch (e) {
        if (kDebugMode) {
          debugPrint('Location capture failed for $sessionId: $e');
        }
      } on Error catch (e) {
        if (kDebugMode) {
          debugPrint('Location capture error for $sessionId: $e');
        }
      }
    });
  }

  /// Non-blocking: runs asynchronously without awaiting. If sync fails,
  /// the session's syncStatus stays PENDING/FAILED for later retry.
  void _triggerSyncAfterEnd(String sessionId) {
    final isAuthenticated = _ref.read(isAuthenticatedProvider);
    if (!isAuthenticated) {
      debugPrint('[Sync] Skipped sync for $sessionId: not authenticated');
      return;
    }

    final connectivityService = _ref.read(connectivityServiceProvider);
    if (!connectivityService.isOnline) {
      debugPrint('[Sync] Skipped sync for $sessionId: offline');
      return;
    }

    debugPrint('[Sync] Starting background sync for $sessionId');

    // Schedule as background microtask so the Future actually executes.
    Future<void>(() async {
      try {
        final syncRepo = _ref.read(syncRepositoryProvider);
        await syncRepo.syncSession(sessionId);
        debugPrint('[Sync] Completed sync for $sessionId');
      } on Exception catch (e) {
        debugPrint('[Sync] Background sync failed for $sessionId: $e');
      }
    });
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

    // Delete media files from disk first (file I/O cannot run in a
    // drift transaction). Best-effort: file cleanup failure must not
    // prevent the DB cascade from running.
    try {
      final photoService = _ref.read(photoServiceProvider);
      await photoService.deleteSessionPhotos(sessionId);
    } on Exception catch (e) {
      if (kDebugMode) {
        debugPrint('Photo file cleanup failed for $sessionId: $e');
      }
    } on Error catch (e) {
      if (kDebugMode) {
        debugPrint('Photo file cleanup failed for $sessionId: $e');
      }
    }
    try {
      final videoService = _ref.read(videoServiceProvider);
      await videoService.deleteSessionVideos(sessionId);
    } on Exception catch (e) {
      if (kDebugMode) {
        debugPrint('Video file cleanup failed for $sessionId: $e');
      }
    } on Error catch (e) {
      if (kDebugMode) {
        debugPrint('Video file cleanup failed for $sessionId: $e');
      }
    }
    final photoDao = _ref.read(photoDaoProvider);
    final videoDao = _ref.read(videoDaoProvider);
    await _sessionDao.deleteSessionCascade(
      _messageDao,
      sessionId,
      photoDao: photoDao,
      videoDao: videoDao,
    );
  }

  /// Complete a check-in session without AI summary generation.
  ///
  /// Used by [CheckInScreen] when the user finishes all slider questions.
  /// Since session content is stored in the checkin_responses table (not as
  /// chat messages), the normal [endSession] path would auto-discard the
  /// session (empty-session guard). This method writes [endTime] directly
  /// and resets state so the session appears in the journal list.
  Future<void> completeCheckInSession() async {
    final sessionId = state.activeSessionId;
    if (sessionId == null) return;

    await _sessionDao.endSession(sessionId, nowUtc());
    _agent.unlockLayer();
    state = const SessionState();
    _ref.read(activeSessionIdProvider.notifier).state = null;
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
  // Intent routing (ADR-0013, ADR-0020)
  // =========================================================================

  /// Route a classified intent to the appropriate handler.
  ///
  /// Returns true if the intent was handled (caller should not continue
  /// with the normal journaling follow-up). Returns false for journal
  /// intent or intents below the ambiguous threshold.
  Future<bool> _routeByIntent(String text, IntentResult intent) async {
    switch (intent.type) {
      case IntentType.query:
        if (intent.confidence >= _highConfidenceThreshold) {
          await _handleRecallQuery(text, intent.searchTerms);
          return true;
        }
        if (intent.confidence >= _ambiguousThreshold) {
          state = state.copyWith(
            pendingRecallQuery: text,
            pendingSearchTerms: intent.searchTerms,
          );
          return true;
        }
        return false;

      case IntentType.calendarEvent:
        if (intent.confidence >= _ambiguousThreshold) {
          _handleCalendarIntent(text);
          return true;
        }
        return false;

      case IntentType.reminder:
        if (intent.confidence >= _ambiguousThreshold) {
          _handleReminderIntent(text);
          return true;
        }
        return false;

      case IntentType.task:
        if (intent.confidence >= _ambiguousThreshold) {
          _handleTaskIntent(text);
          return true;
        }
        return false;

      case IntentType.dayQuery:
        if (intent.confidence >= _ambiguousThreshold) {
          await _handleDayQuery(text);
          return true;
        }
        return false;

      case IntentType.journal:
        return false;
    }
  }

  /// Maximum pending calendar events per session (ADR-0020 §7).
  static const _maxPendingEventsPerSession = 5;

  /// Handle a calendar event intent: set pending state and extract details.
  ///
  /// The UI shows an inline confirmation card with extracted event details.
  /// Extraction runs asynchronously — the card shows a loading state until
  /// the extraction result arrives.
  ///
  /// Enforces the 5-event pending cap per ADR-0020 §7.
  Future<void> _handleCalendarIntent(String text) async {
    final sessionId = state.activeSessionId;
    if (sessionId == null) return;

    // Enforce pending event cap (ADR-0020 §7).
    final calendarEventDao = _ref.read(calendarEventDaoProvider);
    final pendingCount = await calendarEventDao.countPendingForSession(
      sessionId,
    );
    if (pendingCount >= _maxPendingEventsPerSession) {
      return;
    }

    state = state.copyWith(
      pendingCalendarEvent: text,
      isExtracting: true,
      extractionError: null,
      pendingExtractedEvent: null,
    );
    await _extractEventDetails(text);
  }

  /// Handle a reminder intent: set pending state and extract details.
  ///
  /// Enforces the 5-event pending cap per ADR-0020 §7.
  Future<void> _handleReminderIntent(String text) async {
    final sessionId = state.activeSessionId;
    if (sessionId == null) return;

    // Enforce pending event cap (ADR-0020 §7).
    final calendarEventDao = _ref.read(calendarEventDaoProvider);
    final pendingCount = await calendarEventDao.countPendingForSession(
      sessionId,
    );
    if (pendingCount >= _maxPendingEventsPerSession) {
      return;
    }

    state = state.copyWith(
      pendingReminder: text,
      isExtracting: true,
      extractionError: null,
      pendingExtractedEvent: null,
    );
    await _extractEventDetails(text);
  }

  /// Run event extraction and update pending state with the result.
  Future<void> _extractEventDetails(String text) async {
    final extractionService = _ref.read(eventExtractionServiceProvider);
    final now = nowUtc();
    final timezone = await _ref.read(deviceTimezoneProvider.future);

    final result = await extractionService.extract(
      text,
      now,
      timezone: timezone,
    );

    // Check that we still have a pending event (user may have dismissed).
    if (state.pendingCalendarEvent == null && state.pendingReminder == null) {
      return;
    }

    switch (result) {
      case ExtractionSuccess(:final event):
        state = state.copyWith(
          pendingExtractedEvent: event,
          isExtracting: false,
        );
      case ExtractionFailure(:final error):
        state = state.copyWith(
          isExtracting: false,
          extractionError: error.reason,
        );
    }
  }

  // =========================================================================
  // Phase 13: Task handling
  // =========================================================================

  /// Handle a task intent: set pending state and extract details.
  Future<void> _handleTaskIntent(String text) async {
    state = state.copyWith(
      pendingTask: text,
      isExtractingTask: true,
      taskExtractionError: null,
      pendingExtractedTask: null,
    );
    await _extractTaskDetails(text);
  }

  /// Run task extraction and update pending state with the result.
  Future<void> _extractTaskDetails(String text) async {
    final extractionService = _ref.read(taskExtractionServiceProvider);
    final now = nowUtc();
    final timezone = await _ref.read(deviceTimezoneProvider.future);

    // Pass up to 3 prior messages as context so the LLM can resolve pronouns
    // like "it" or "that" by referencing the recent conversation.
    final allMessages = state.conversationMessages;
    final contextMessages = allMessages.length > 1
        ? allMessages.sublist(
            (allMessages.length - 4).clamp(0, allMessages.length - 1),
            allMessages.length - 1,
          )
        : null;

    final result = await extractionService.extract(
      text,
      now,
      timezone: timezone,
      context: contextMessages?.isEmpty == true ? null : contextMessages,
    );

    // Check that we still have a pending task (user may have dismissed).
    if (state.pendingTask == null) return;

    switch (result) {
      case TaskExtractionSuccess(:final task):
        state = state.copyWith(
          pendingExtractedTask: task,
          isExtractingTask: false,
        );
      case TaskExtractionFailure(:final reason):
        state = state.copyWith(
          isExtractingTask: false,
          taskExtractionError: reason,
        );
    }
  }

  /// Confirm the pending task: save to local DB and sync to Google Tasks.
  Future<void> confirmTask() async {
    if (state.isWaitingForAgent) return;

    final sessionId = state.activeSessionId;
    final rawMessage = state.pendingTask;
    final task = state.pendingExtractedTask;
    if (rawMessage == null || task == null) return;

    // Clear pending state immediately (optimistic UI).
    state = state.copyWith(
      pendingTask: null,
      pendingExtractedTask: null,
      taskExtractionError: null,
      isWaitingForAgent: true,
    );

    // Save the task to the local database.
    final taskDao = _ref.read(taskDaoProvider);
    final taskId = generateUuid();

    await taskDao.insertTask(
      TasksCompanion(
        taskId: Value(taskId),
        sessionId: Value.absentIfNull(sessionId),
        title: Value(task.title),
        notes: Value.absentIfNull(task.notes),
        dueDate: Value.absentIfNull(task.dueDate),
        rawUserMessage: Value(rawMessage),
        status: const Value(TaskStatus.active),
        syncStatus: const Value(TaskSyncStatus.pending),
        createdAt: Value(nowUtc()),
        updatedAt: Value(nowUtc()),
      ),
    );

    // Try to sync to Google Tasks.
    final isConnected = _ref.read(isGoogleConnectedProvider);
    if (isConnected) {
      await _createGoogleTask(taskId, task);
    }

    // Save an assistant confirmation message.
    final confirmMsg = isConnected
        ? "Added '${task.title}' to your tasks."
        : "Added '${task.title}' to your tasks.";
    if (sessionId != null) {
      await _messageDao.insertMessage(
        generateUuid(),
        sessionId,
        'ASSISTANT',
        confirmMsg,
        nowUtc(),
      );
    }

    // Invalidate task count provider so UI updates.
    _ref.invalidate(taskCountProvider);

    state = state.copyWith(
      isWaitingForAgent: false,
      conversationMessages: [
        ...state.conversationMessages,
        {'role': 'assistant', 'content': confirmMsg},
      ],
    );
  }

  /// Create a Google Task via the API.
  Future<void> _createGoogleTask(String taskId, ExtractedTask task) async {
    final taskDao = _ref.read(taskDaoProvider);

    try {
      final authService = _ref.read(googleAuthServiceProvider);
      final authClient = await authService.getAuthClient();
      if (authClient == null) {
        await taskDao.updateSyncStatus(taskId, TaskSyncStatus.failed);
        return;
      }

      final tasksService = GoogleTasksService.withClient(authClient);
      final result = await tasksService.createTask(
        title: task.title,
        notes: task.notes,
        dueDate: task.dueDate,
      );

      await taskDao.updateGoogleTaskId(
        taskId,
        result.googleTaskId,
        result.googleTaskListId,
      );
    } on GoogleTasksException catch (e) {
      if (kDebugMode) {
        debugPrint('Google Tasks API failed: $e');
      }
      await taskDao.updateSyncStatus(taskId, TaskSyncStatus.failed);
    } on Exception catch (e) {
      if (kDebugMode) {
        debugPrint('Google Tasks creation failed: $e');
      }
      await taskDao.updateSyncStatus(taskId, TaskSyncStatus.failed);
    }
  }

  /// Dismiss the pending task (user chose to continue journaling).
  void dismissTask() {
    state = state.copyWith(
      pendingTask: null,
      pendingExtractedTask: null,
      isExtractingTask: false,
      taskExtractionError: null,
    );
  }

  // =========================================================================
  // Phase 13: Day query handling
  // =========================================================================

  /// Handle a day query: read local tasks + Google Calendar, synthesize.
  Future<void> _handleDayQuery(String text) async {
    final sessionId = state.activeSessionId;
    if (sessionId == null) return;

    state = state.copyWith(isWaitingForAgent: true);

    try {
      final taskDao = _ref.read(taskDaoProvider);
      final lower = text.toLowerCase();
      final isTomorrow = lower.contains('tomorrow');

      // Get local tasks.
      final tasks = isTomorrow
          ? await taskDao.getTasksDueTomorrow()
          : await taskDao.getTasksDueToday();

      // Get calendar events if Google is connected.
      List<CalendarEventSummary>? calendarEvents;
      final isConnected = _ref.read(isGoogleConnectedProvider);
      if (isConnected) {
        try {
          final authService = _ref.read(googleAuthServiceProvider);
          final authClient = await authService.getAuthClient();
          if (authClient != null) {
            final timezone = await _ref.read(deviceTimezoneProvider.future);
            final calendarService = GoogleCalendarService.withClient(
              authClient,
              timezone: timezone,
            );

            final now = DateTime.now();
            final dayStart = isTomorrow
                ? DateTime(now.year, now.month, now.day + 1)
                : DateTime(now.year, now.month, now.day);
            final dayEnd = dayStart.add(const Duration(days: 1));

            calendarEvents = await calendarService.listEvents(
              timeMin: dayStart,
              timeMax: dayEnd,
            );
          }
        } on CalendarServiceException catch (e) {
          if (kDebugMode) {
            debugPrint('Day query calendar fetch failed: $e');
          }
        }
      }

      // Build summary.
      final dayLabel = isTomorrow ? 'tomorrow' : 'today';
      final buffer = StringBuffer();

      if ((calendarEvents == null || calendarEvents.isEmpty) && tasks.isEmpty) {
        buffer.write(
          "You don't have anything scheduled for $dayLabel. "
          'Looks like a clear day!',
        );
      } else {
        buffer.writeln("Here's what's on for $dayLabel:");
        buffer.writeln();

        if (calendarEvents != null && calendarEvents.isNotEmpty) {
          buffer.writeln('**Calendar:**');
          for (final event in calendarEvents) {
            if (event.isAllDay) {
              buffer.writeln('- ${event.title} (all day)');
            } else {
              final startLocal = event.startTime.toLocal();
              final hour = startLocal.hour > 12
                  ? startLocal.hour - 12
                  : startLocal.hour == 0
                  ? 12
                  : startLocal.hour;
              final minute = startLocal.minute.toString().padLeft(2, '0');
              final amPm = startLocal.hour >= 12 ? 'PM' : 'AM';
              buffer.writeln('- ${event.title} at $hour:$minute $amPm');
            }
          }
          buffer.writeln();
        }

        if (tasks.isNotEmpty) {
          buffer.writeln('**Tasks due $dayLabel:**');
          for (final task in tasks) {
            buffer.writeln('- ${task.title}');
          }
        }
      }

      final summary = buffer.toString().trim();

      // Stale response check.
      if (state.activeSessionId == null) return;

      await _messageDao.insertMessage(
        generateUuid(),
        sessionId,
        'ASSISTANT',
        summary,
        nowUtc(),
      );

      state = state.copyWith(
        isWaitingForAgent: false,
        conversationMessages: [
          ...state.conversationMessages,
          {'role': 'assistant', 'content': summary},
        ],
      );
    } on Exception catch (e) {
      if (kDebugMode) {
        debugPrint('Day query failed: $e');
      }
      state = state.copyWith(isWaitingForAgent: false);
    }
  }

  /// Confirm the pending calendar event: create it in Google Calendar
  /// and save to the local database.
  ///
  /// Called by the UI when the user taps "Add to Calendar" on the
  /// confirmation card. Requires Google connection.
  ///
  /// Guards against double invocation (TOCTOU race from double-tap or
  /// concurrent voice + UI confirmation) via isWaitingForAgent check.
  Future<void> confirmCalendarEvent() async {
    // Guard: prevent double invocation from concurrent UI + voice confirmation.
    if (state.isWaitingForAgent) return;

    final sessionId = state.activeSessionId;
    final rawMessage = state.pendingCalendarEvent ?? state.pendingReminder;
    final event = state.pendingExtractedEvent;
    if (sessionId == null || rawMessage == null || event == null) return;

    final isReminder = state.pendingReminder != null;

    // Clear pending state immediately (optimistic UI).
    state = state.copyWith(
      pendingCalendarEvent: null,
      pendingReminder: null,
      pendingExtractedEvent: null,
      extractionError: null,
      isWaitingForAgent: true,
    );

    // Save the event to the local database.
    final calendarEventDao = _ref.read(calendarEventDaoProvider);
    final eventId = generateUuid();

    await calendarEventDao.insertEvent(
      CalendarEventsCompanion(
        eventId: Value(eventId),
        sessionId: Value(sessionId),
        title: Value(event.title),
        startTime: Value(event.startTime),
        endTime: Value(event.endTime),
        rawUserMessage: Value(rawMessage),
        status: const Value(EventStatus.pendingCreate),
        syncStatus: const Value(EventSyncStatus.pending),
        createdAt: Value(nowUtc()),
        updatedAt: Value(nowUtc()),
      ),
    );

    // Try to create the event in Google Calendar.
    final isConnected = _ref.read(isGoogleConnectedProvider);
    if (isConnected) {
      await _createGoogleCalendarEvent(eventId, event, isReminder);
    }

    // Save an assistant confirmation message.
    final confirmMsg = isConnected
        ? "Added '${event.title}' to your calendar."
        : "Saved '${event.title}' — connect Google Calendar to sync it.";
    await _messageDao.insertMessage(
      generateUuid(),
      sessionId,
      'ASSISTANT',
      confirmMsg,
      nowUtc(),
    );

    state = state.copyWith(
      isWaitingForAgent: false,
      conversationMessages: [
        ...state.conversationMessages,
        {'role': 'assistant', 'content': confirmMsg},
      ],
    );
  }

  /// Create a Google Calendar event via the API.
  Future<void> _createGoogleCalendarEvent(
    String eventId,
    ExtractedEvent event,
    bool isReminder,
  ) async {
    final calendarEventDao = _ref.read(calendarEventDaoProvider);

    try {
      final authService = _ref.read(googleAuthServiceProvider);
      final authClient = await authService.getAuthClient();
      if (authClient == null) {
        await calendarEventDao.updateStatus(eventId, EventStatus.failed);
        return;
      }

      final timezone = await _ref.read(deviceTimezoneProvider.future);
      final calendarService = GoogleCalendarService.withClient(
        authClient,
        timezone: timezone,
      );
      final CalendarCreateResult result;

      if (isReminder) {
        result = await calendarService.createReminder(
          title: event.title,
          dateTime: event.startTime,
        );
      } else {
        result = await calendarService.createEvent(
          title: event.title,
          startTime: event.startTime,
          endTime: event.endTime,
        );
      }

      await calendarEventDao.updateGoogleEventId(eventId, result.googleEventId);
    } on CalendarServiceException catch (e) {
      if (kDebugMode) {
        debugPrint('Google Calendar API failed: $e');
      }
      await calendarEventDao.updateStatus(eventId, EventStatus.failed);
    } on Exception catch (e) {
      if (kDebugMode) {
        debugPrint('Google Calendar creation failed: $e');
      }
      await calendarEventDao.updateStatus(eventId, EventStatus.failed);
    }
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
    final isVoiceModeForFollowUp = _ref.read(voiceModeEnabledProvider);
    final followUpResponse = await _agent.getFollowUp(
      latestUserMessage: query,
      conversationHistory: state.usedQuestions,
      followUpCount: state.followUpCount,
      allMessages: state.conversationMessages,
      sessionSummaries: state.sessionSummaries,
      isVoiceMode: isVoiceModeForFollowUp,
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

  /// Defer a calendar event when Google is not connected during voice mode.
  ///
  /// Saves the extracted event to the local database with PENDING_CREATE
  /// status (no Google Calendar creation attempted). The user is reminded
  /// to connect Google Calendar after the session ends via a banner on
  /// the session list screen (ADR-0020 §8).
  Future<void> deferCalendarEvent() async {
    final sessionId = state.activeSessionId;
    final rawMessage = state.pendingCalendarEvent ?? state.pendingReminder;
    final event = state.pendingExtractedEvent;
    if (sessionId == null || rawMessage == null || event == null) return;

    // Save to local DB with PENDING_CREATE status.
    final calendarEventDao = _ref.read(calendarEventDaoProvider);
    final eventId = generateUuid();

    await calendarEventDao.insertEvent(
      CalendarEventsCompanion(
        eventId: Value(eventId),
        sessionId: Value(sessionId),
        title: Value(event.title),
        startTime: Value(event.startTime),
        endTime: Value(event.endTime),
        rawUserMessage: Value(rawMessage),
        status: const Value(EventStatus.pendingCreate),
        syncStatus: const Value(EventSyncStatus.pending),
        createdAt: Value(nowUtc()),
        updatedAt: Value(nowUtc()),
      ),
    );

    // Clear pending state — the event is saved, conversation continues.
    state = state.copyWith(
      pendingCalendarEvent: null,
      pendingReminder: null,
      pendingExtractedEvent: null,
      extractionError: null,
      isExtracting: false,
    );
  }

  /// Dismiss the pending calendar event (user chose to continue journaling).
  ///
  /// Clears the pending state and extraction data. The message was already
  /// saved to the DB in sendMessage(), so it's part of the journal entry.
  void dismissCalendarEvent() {
    final sessionId = state.activeSessionId;
    state = state.copyWith(
      pendingCalendarEvent: null,
      pendingExtractedEvent: null,
      isExtracting: false,
      extractionError: null,
    );

    // Update the event status in the DB if one was created.
    if (sessionId != null) {
      _cancelPendingEvents(sessionId);
    }
  }

  /// Dismiss the pending reminder (user chose to continue journaling).
  void dismissReminder() {
    final sessionId = state.activeSessionId;
    state = state.copyWith(
      pendingReminder: null,
      pendingExtractedEvent: null,
      isExtracting: false,
      extractionError: null,
    );

    if (sessionId != null) {
      _cancelPendingEvents(sessionId);
    }
  }

  // =========================================================================
  // Phase 12: Video Attachment (ADR-0021)
  // =========================================================================

  /// Attach a video to the current session.
  ///
  /// Processes the raw video file (metadata strip + thumbnail generation),
  /// creates a "[Video]" message with inputMethod=VIDEO, and links it via
  /// videoId. Returns true if the video was attached, false on failure.
  ///
  /// The caller (UI) is responsible for pausing STT before invoking this
  /// method and resuming after it returns (ADR-0021 §7).
  Future<bool> attachVideo(File rawFile, {int durationSeconds = 0}) async {
    final sessionId = state.activeSessionId;
    if (sessionId == null) return false;

    final videoService = _ref.read(videoServiceProvider);
    final videoDao = _ref.read(videoDaoProvider);
    final videoId = generateUuid();
    final now = nowUtc();

    // Process: strip metadata, generate thumbnail, save to canonical paths.
    final result = await videoService.processAndSave(
      rawFile,
      sessionId,
      videoId,
    );
    if (result == null) return false;

    // Use the caller-provided duration (from image_picker) or the
    // processAndSave result (currently 0).
    final actualDuration = durationSeconds > 0
        ? durationSeconds
        : result.durationSeconds;

    // Store absolute paths (matching photo pattern — see ADR-0018).
    // Using absolute paths avoids resolution issues in the UI layer
    // where File() needs the full path, not a relative one.

    // Insert video record into database.
    await videoDao.insertVideo(
      videoId: videoId,
      sessionId: sessionId,
      localPath: result.file.path,
      thumbnailPath: result.thumbnail.path,
      durationSeconds: actualDuration,
      timestamp: now,
      fileSizeBytes: result.fileSizeBytes,
      width: result.width,
      height: result.height,
    );

    // Create a "[Video]" message linked via videoId.
    final messageId = generateUuid();
    await _messageDao.insertMessage(
      messageId,
      sessionId,
      'USER',
      '[Video]',
      now,
      inputMethod: 'VIDEO',
      videoId: videoId,
    );

    // Track in conversation context.
    state = state.copyWith(
      conversationMessages: [
        ...state.conversationMessages,
        {'role': 'user', 'content': '[Video]'},
      ],
    );

    return true;
  }

  /// Cancel any PENDING_CREATE events for the session.
  Future<void> _cancelPendingEvents(String sessionId) async {
    final calendarEventDao = _ref.read(calendarEventDaoProvider);
    final pending = await calendarEventDao.getPendingEvents();
    for (final event in pending) {
      if (event.sessionId == sessionId) {
        await calendarEventDao.updateStatus(
          event.eventId,
          EventStatus.cancelled,
        );
      }
    }
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

  /// Signal the voice orchestrator that processing is complete without a
  /// response, so the listening loop resumes. No-op in text mode.
  Future<void> _resumeOrchestratorIfVoiceMode() async {
    if (!_ref.read(voiceModeEnabledProvider)) return;
    try {
      await _ref.read(voiceOrchestratorProvider).acknowledgeNoResponse();
    } on StateError {
      // Provider already disposed — ignore.
    }
  }
}

/// Deletes a completed session, its messages, photos, and videos from the
/// database.
///
/// Accepts DAOs and services directly so it can be called from both providers
/// (Ref) and widgets (WidgetRef). The session list auto-updates via drift's
/// stream because [allSessionsProvider] watches the table.
///
/// Media files on disk are deleted first (file I/O cannot run inside a drift
/// transaction), then the DB cascade runs: videos → photos → messages →
/// session.
Future<void> deleteSessionCascade(
  SessionDao sessionDao,
  MessageDao messageDao,
  String sessionId, {
  PhotoDao? photoDao,
  PhotoService? photoService,
  VideoDao? videoDao,
  VideoService? videoService,
}) async {
  // Delete media files from disk before the DB transaction.
  if (photoService != null) {
    await photoService.deleteSessionPhotos(sessionId);
  }
  if (videoService != null) {
    await videoService.deleteSessionVideos(sessionId);
  }
  await sessionDao.deleteSessionCascade(
    messageDao,
    sessionId,
    photoDao: photoDao,
    videoDao: videoDao,
  );
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
/// The localLlmLayer uses ref.listen (not ref.watch) so that async model
/// loading updates the layer WITHOUT rebuilding this provider — which would
/// cascade to sessionNotifierProvider and destroy any active session state.
final agentRepositoryProvider = Provider<AgentRepository>((ref) {
  final claudeService = ref.watch(claudeApiServiceProvider);
  final connectivityService = ref.watch(connectivityServiceProvider);
  final preferClaude = ref.watch(preferClaudeProvider);
  final journalOnlyMode = ref.watch(journalOnlyModeProvider);

  // Read the initial value (may be null if model not yet loaded).
  final localLlmLayer = ref.read(localLlmLayerProvider);

  // Read the initial personality config for custom instructions.
  // Uses ref.read (not ref.watch) to avoid rebuilding the provider chain
  // on personality changes — ref.listen below handles updates without
  // destroying the active session.
  final personality = ref.read(personalityConfigProvider);

  final repo = AgentRepository(
    claudeService: claudeService,
    connectivityService: connectivityService,
    localLlmLayer: localLlmLayer,
    customInstructions: personality.customPrompt,
  );
  repo.setPreferClaude(preferClaude);
  repo.setJournalOnlyMode(journalOnlyMode);

  // Listen for async LLM layer changes and update the mutable field
  // without triggering a provider rebuild cascade.
  ref.listen(localLlmLayerProvider, (_, next) {
    repo.updateLocalLlmLayer(next);
  });

  // Listen for personality config changes and update custom instructions
  // on the Claude API layer without rebuilding. Mirrors the localLlmLayer
  // listen pattern to avoid destroying active session state.
  ref.listen(personalityConfigProvider, (_, next) {
    repo.updateCustomInstructions(next.customPrompt);
  });

  return repo;
});

/// Human-readable label for the currently active conversation layer.
///
/// Returns "Claude", "Local LLM", or "Offline" based on the agent
/// repository's current layer selection.
final activeLayerLabelProvider = Provider<String>((ref) {
  final repo = ref.watch(agentRepositoryProvider);
  return repo.activeLayerLabel;
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
