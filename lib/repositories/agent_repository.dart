// ===========================================================================
// file: lib/repositories/agent_repository.dart
// purpose: Thin dispatcher that selects and delegates to ConversationLayers.
//
// Phase 8A refactored this from inline Layer A/B logic to a strategy
// pattern. The actual conversation logic now lives in:
//   - RuleBasedLayer (Layer A — offline, always available)
//   - ClaudeApiLayer (Layer B remote — Claude API via Edge Function)
//   - LocalLlmLayer (Layer B local — Phase 8B, on-device LLM)
//
// AgentRepository responsibilities:
//   - Layer selection: pick the best available layer at session start
//   - Session locking: once a session starts on a layer, it stays there
//   - Fallback: if the locked layer fails, fall back to RuleBasedLayer
//   - shouldEndSession(): layer-independent end-session detection
//   - Journal-only mode: bypass all layers for silent capture
//
// Design Decision: AgentRepository is INTENTIONALLY STATELESS except for
//   the session-locked layer reference (set/cleared by SessionNotifier).
//   All conversation state (follow-up count, message history, used questions)
//   is owned by SessionNotifier in the providers layer.
//
// See: ADR-0017 (Local LLM Layer Architecture)
// ===========================================================================

import '../layers/conversation_layer.dart' show ConversationLayer;
import '../layers/rule_based_layer.dart';
import '../layers/claude_api_layer.dart';
import '../models/agent_response.dart';
import '../services/claude_api_service.dart';
import '../services/connectivity_service.dart';

/// Conversation engine dispatcher with layer selection and fallback.
///
/// Selects the best available ConversationLayer and delegates all
/// conversation operations to it. Falls back to RuleBasedLayer on error.
class AgentRepository {
  final RuleBasedLayer _ruleBasedLayer;
  final ClaudeApiLayer? _claudeApiLayer;
  final ConnectivityService? _connectivityService;

  /// Local LLM layer — injected via constructor when model is loaded.
  ///
  /// Injected as a constructor parameter (not a mutable field) so that
  /// provider rebuilds correctly propagate the layer availability.
  /// Null when no local LLM model is loaded.
  final ConversationLayer? _localLlmLayer;

  /// The layer locked for the current session (null when no session active).
  ConversationLayer? _sessionLockedLayer;

  /// User preference: prefer Claude API when online.
  bool _preferClaude = false;

  /// Whether journal-only mode is active (bypass all layers).
  bool _journalOnlyMode = false;

  /// Whether journal-only mode is active.
  bool get journalOnlyMode => _journalOnlyMode;

  /// Set journal-only mode.
  void setJournalOnlyMode(bool enabled) {
    _journalOnlyMode = enabled;
  }

  /// Creates an AgentRepository.
  ///
  /// [claudeService] — optional Claude API client. When null, no remote layer.
  /// [connectivityService] — optional connectivity checker.
  /// [ruleBasedLayer] — injectable for testing. Defaults to standard instance.
  /// [claudeApiLayer] — injectable for testing. Built from claudeService if null.
  /// [localLlmLayer] — optional local LLM layer. Null when model not loaded.
  AgentRepository({
    ClaudeApiService? claudeService,
    ConnectivityService? connectivityService,
    RuleBasedLayer? ruleBasedLayer,
    ClaudeApiLayer? claudeApiLayer,
    ConversationLayer? localLlmLayer,
  }) : _ruleBasedLayer = ruleBasedLayer ?? RuleBasedLayer(),
       _claudeApiLayer =
           claudeApiLayer ??
           (claudeService != null
               ? ClaudeApiLayer(claudeService: claudeService)
               : null),
       _connectivityService = connectivityService,
       _localLlmLayer = localLlmLayer;

  // =========================================================================
  // Layer selection
  // =========================================================================

  /// Whether the Claude API layer is available (configured + online).
  bool get _isClaudeAvailable =>
      _claudeApiLayer != null && (_connectivityService?.isOnline ?? false);

  /// Select the best available layer based on preference and availability.
  ConversationLayer _selectLayer() {
    if (_preferClaude && _isClaudeAvailable) return _claudeApiLayer!;
    if (_localLlmLayer != null) return _localLlmLayer;
    if (_isClaudeAvailable) return _claudeApiLayer!;
    return _ruleBasedLayer;
  }

  /// The currently active layer (locked or freshly selected).
  ConversationLayer get _activeLayer => _sessionLockedLayer ?? _selectLayer();

  /// Set the "Prefer Claude" user preference.
  void setPreferClaude(bool prefer) {
    _preferClaude = prefer;
  }

  /// Lock the current best layer for a session.
  ///
  /// Called by SessionNotifier at session start. The locked layer persists
  /// for the session's duration to prevent mid-conversation quality changes.
  void lockLayerForSession() {
    _sessionLockedLayer = _selectLayer();
  }

  /// Unlock the session-locked layer.
  ///
  /// Called by SessionNotifier at session end/dismiss/discard.
  void unlockLayer() {
    _sessionLockedLayer = null;
  }

  // =========================================================================
  // Public API — delegates to active layer with fallback
  // =========================================================================

  /// Get the opening greeting.
  ///
  /// In journal-only mode: returns a minimal "Session started." message.
  /// Otherwise: delegates to the active layer with fallback to rule-based.
  Future<AgentResponse> getGreeting({
    DateTime? lastSessionDate,
    DateTime? now,
    int sessionCount = 0,
  }) async {
    if (journalOnlyMode) {
      return const AgentResponse(
        content: 'Session started.',
        layer: AgentLayer.ruleBasedLocal,
      );
    }

    try {
      return await _activeLayer.getGreeting(
        lastSessionDate: lastSessionDate,
        now: now,
        sessionCount: sessionCount,
      );
    } on Exception {
      // Catches ClaudeApiException, LocalLlmException, and any layer
      // failure — falls back to rule-based per ADR-0017 §4.
      return _ruleBasedLayer.getGreeting(
        lastSessionDate: lastSessionDate,
        now: now,
        sessionCount: sessionCount,
      );
    }
  }

  /// Get a follow-up question based on the user's message.
  ///
  /// In journal-only mode: always returns null (no follow-ups).
  /// Checks shouldEndSession first (layer-independent).
  /// Otherwise: delegates to active layer with fallback.
  Future<AgentResponse?> getFollowUp({
    required String latestUserMessage,
    required List<String> conversationHistory,
    required int followUpCount,
    List<Map<String, String>>? allMessages,
  }) async {
    if (journalOnlyMode) return null;

    // Check if session should end (layer-independent).
    if (shouldEndSession(
      followUpCount: followUpCount,
      latestUserMessage: latestUserMessage,
    )) {
      return null;
    }

    try {
      return await _activeLayer.getFollowUp(
        latestUserMessage: latestUserMessage,
        conversationHistory: conversationHistory,
        followUpCount: followUpCount,
        allMessages: allMessages,
      );
    } on Exception {
      // Catches ClaudeApiException, LocalLlmException, and any layer
      // failure — falls back to rule-based per ADR-0017 §4.
      return _ruleBasedLayer.getFollowUp(
        latestUserMessage: latestUserMessage,
        conversationHistory: conversationHistory,
        followUpCount: followUpCount,
        allMessages: allMessages,
      );
    }
  }

  /// Generate a session summary and extract metadata.
  ///
  /// In journal-only mode: forces Layer A summary only, no metadata.
  /// Otherwise: delegates to active layer with fallback.
  Future<AgentResponse> generateSummary({
    required List<String> userMessages,
    List<Map<String, String>>? allMessages,
  }) async {
    if (journalOnlyMode) {
      return _ruleBasedLayer.generateSummary(userMessages: userMessages);
    }

    try {
      return await _activeLayer.generateSummary(
        userMessages: userMessages,
        allMessages: allMessages,
      );
    } on Exception {
      // Catches ClaudeApiException, LocalLlmException, and any layer
      // failure — falls back to rule-based per ADR-0017 §4.
      return _ruleBasedLayer.generateSummary(userMessages: userMessages);
    }
  }

  /// Get a greeting for a resumed session.
  Future<AgentResponse> getResumeGreeting() async {
    if (journalOnlyMode) {
      return const AgentResponse(
        content: 'Session resumed.',
        layer: AgentLayer.ruleBasedLocal,
      );
    }

    try {
      return await _activeLayer.getResumeGreeting();
    } on Exception {
      // Catches ClaudeApiException, LocalLlmException, and any layer
      // failure — falls back to rule-based per ADR-0017 §4.
      return _ruleBasedLayer.getResumeGreeting();
    }
  }

  // =========================================================================
  // End-session detection (layer-independent)
  // =========================================================================

  /// Done signals that indicate the user wants to end the session.
  static const List<String> _doneSignals = [
    'no',
    'nope',
    "that's it",
    'nothing',
    "i'm done",
    "that's all",
    'goodbye',
    'bye',
    'no thanks',
    'not really',
    'done',
    'all good',
    "that's everything",
  ];

  /// Determine if the session should end based on conversation state.
  ///
  /// This is synchronous and layer-independent — the same rules apply
  /// regardless of which layer is serving the conversation.
  bool shouldEndSession({
    required int followUpCount,
    required String latestUserMessage,
  }) {
    if (followUpCount > 3) return true;
    final trimmed = latestUserMessage.trim().toLowerCase().replaceAll(
      RegExp(r'[.!?,;:]+$'),
      '',
    );
    return _doneSignals.contains(trimmed);
  }
}
