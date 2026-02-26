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

import 'package:flutter/foundation.dart';

import '../layers/conversation_layer.dart' show ConversationLayer;
import '../layers/rule_based_layer.dart';
import '../layers/claude_api_layer.dart';
import '../models/agent_response.dart';
import '../services/claude_api_service.dart';
import '../services/connectivity_service.dart';

/// Number of retry attempts for transient Claude API failures.
const _maxRetries = 1;

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
  /// Mutable so that async model loading (llmAutoLoadProvider) can update
  /// the layer without triggering a provider rebuild cascade that would
  /// destroy any active SessionNotifier state.
  /// Null when no local LLM model is loaded.
  ConversationLayer? _localLlmLayer;

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
    if (_localLlmLayer != null) return _localLlmLayer!;
    if (_isClaudeAvailable) return _claudeApiLayer!;
    return _ruleBasedLayer;
  }

  /// The currently active layer (locked or freshly selected).
  ConversationLayer get _activeLayer => _sessionLockedLayer ?? _selectLayer();

  /// Human-readable label for the currently active layer.
  ///
  /// Returns "Claude", "Local LLM", or "Offline" depending on which
  /// layer is active (locked or freshly selected).
  String get activeLayerLabel {
    final layer = _sessionLockedLayer ?? _selectLayer();
    if (layer is ClaudeApiLayer) return 'Claude';
    if (layer is RuleBasedLayer) return 'Offline';
    if (_localLlmLayer != null && layer == _localLlmLayer) return 'Local LLM';
    return 'Unknown';
  }

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

  /// Update the local LLM layer without rebuilding the provider chain.
  ///
  /// Called by [agentRepositoryProvider]'s listen callback when the LLM
  /// finishes loading asynchronously. Does not affect the session-locked
  /// layer (active sessions keep their locked layer per ADR-0017 §3).
  void updateLocalLlmLayer(ConversationLayer? layer) {
    _localLlmLayer = layer;
  }

  // =========================================================================
  // Public API — delegates to active layer with retry before fallback
  // =========================================================================

  /// Get the opening greeting.
  ///
  /// In journal-only mode: returns a minimal "Session started." message.
  /// Otherwise: delegates to the active layer. Retries transient failures
  /// before falling back to rule-based.
  ///
  /// [sessionSummaries] — recent session summaries for continuity (ADR-0023).
  /// [journalingMode] — optional mode string for guided sessions (ADR-0025).
  Future<AgentResponse> getGreeting({
    DateTime? lastSessionDate,
    DateTime? now,
    int sessionCount = 0,
    List<Map<String, String>>? sessionSummaries,
    String? journalingMode,
  }) async {
    if (journalOnlyMode) {
      return const AgentResponse(
        content: 'Session started.',
        layer: AgentLayer.ruleBasedLocal,
      );
    }

    return _withRetryAndFallback(
      label: 'getGreeting',
      action: () => _activeLayer.getGreeting(
        lastSessionDate: lastSessionDate,
        now: now,
        sessionCount: sessionCount,
        sessionSummaries: sessionSummaries,
        journalingMode: journalingMode,
      ),
      fallback: () => _ruleBasedLayer.getGreeting(
        lastSessionDate: lastSessionDate,
        now: now,
        sessionCount: sessionCount,
        journalingMode: journalingMode,
      ),
    );
  }

  /// Get a follow-up question based on the user's message.
  ///
  /// In journal-only mode: always returns null (no follow-ups).
  /// Checks shouldEndSession first (layer-independent).
  /// Otherwise: delegates to active layer with retry before fallback.
  ///
  /// [sessionSummaries] — recent session summaries for continuity (ADR-0023).
  /// [journalingMode] — optional mode string for guided sessions (ADR-0025).
  Future<AgentResponse?> getFollowUp({
    required String latestUserMessage,
    required List<String> conversationHistory,
    required int followUpCount,
    List<Map<String, String>>? allMessages,
    List<Map<String, String>>? sessionSummaries,
    String? journalingMode,
  }) async {
    if (journalOnlyMode) return null;

    // Check if session should end (layer-independent).
    if (shouldEndSession(
      followUpCount: followUpCount,
      latestUserMessage: latestUserMessage,
    )) {
      return null;
    }

    return _withRetryAndFallback(
      label: 'getFollowUp',
      action: () => _activeLayer.getFollowUp(
        latestUserMessage: latestUserMessage,
        conversationHistory: conversationHistory,
        followUpCount: followUpCount,
        allMessages: allMessages,
        sessionSummaries: sessionSummaries,
        journalingMode: journalingMode,
      ),
      fallback: () => _ruleBasedLayer.getFollowUp(
        latestUserMessage: latestUserMessage,
        conversationHistory: conversationHistory,
        followUpCount: followUpCount,
        allMessages: allMessages,
        journalingMode: journalingMode,
      ),
    );
  }

  /// Generate a session summary and extract metadata.
  ///
  /// In journal-only mode: forces Layer A summary only, no metadata.
  /// Otherwise: delegates to active layer with retry before fallback.
  Future<AgentResponse> generateSummary({
    required List<String> userMessages,
    List<Map<String, String>>? allMessages,
  }) async {
    if (journalOnlyMode) {
      return _ruleBasedLayer.generateSummary(userMessages: userMessages);
    }

    return _withRetryAndFallback(
      label: 'generateSummary',
      action: () => _activeLayer.generateSummary(
        userMessages: userMessages,
        allMessages: allMessages,
      ),
      fallback: () =>
          _ruleBasedLayer.generateSummary(userMessages: userMessages),
    );
  }

  /// Get a greeting for a resumed session.
  Future<AgentResponse> getResumeGreeting() async {
    if (journalOnlyMode) {
      return const AgentResponse(
        content: 'Session resumed.',
        layer: AgentLayer.ruleBasedLocal,
      );
    }

    return _withRetryAndFallback(
      label: 'getResumeGreeting',
      action: () => _activeLayer.getResumeGreeting(),
      fallback: () => _ruleBasedLayer.getResumeGreeting(),
    );
  }

  // =========================================================================
  // Retry logic
  // =========================================================================

  /// Execute [action] with retry for transient errors before falling back.
  ///
  /// Retries up to [_maxRetries] times on transient Claude API failures
  /// (timeouts, network errors). Only falls back to [fallback] when all
  /// retries are exhausted or the error is permanent (not configured).
  Future<T> _withRetryAndFallback<T>({
    required String label,
    required Future<T> Function() action,
    required Future<T> Function() fallback,
  }) async {
    Exception? lastError;

    for (var attempt = 0; attempt <= _maxRetries; attempt++) {
      try {
        return await action();
      } on ClaudeApiNotConfiguredException {
        // Permanent error — no retry, fall back immediately.
        return fallback();
      } on ClaudeApiTimeoutException catch (e) {
        lastError = e;
        if (kDebugMode) {
          debugPrint('AgentRepository.$label: timeout (attempt $attempt)');
        }
        // Retry on timeout.
      } on ClaudeApiNetworkException catch (e) {
        lastError = e;
        if (kDebugMode) {
          debugPrint(
            'AgentRepository.$label: network error (attempt $attempt)',
          );
        }
        // Retry on network errors.
      } on Exception catch (e) {
        lastError = e;
        if (kDebugMode) {
          debugPrint(
            'AgentRepository.$label: '
            '${_activeLayer.runtimeType} failed: $e',
          );
        }
        // Other errors (server 5xx, parse): retry once.
      }
    }

    if (kDebugMode) {
      debugPrint(
        'AgentRepository.$label: all retries exhausted, '
        'falling back to rule-based. Last error: $lastError',
      );
    }
    return fallback();
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
