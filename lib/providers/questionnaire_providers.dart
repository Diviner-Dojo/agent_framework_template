// ===========================================================================
// file: lib/providers/questionnaire_providers.dart
// purpose: Riverpod providers for the Pulse Check-In questionnaire flow.
//
// Architecture boundary (SPEC-20260302-ADHD Task 4):
//   CheckInNotifier owns all check-in state — items, current step, answers,
//   and score. SessionNotifier is NOT extended. Coordination happens via
//   sessionId, not shared mutable state. This matches the existing pattern
//   used for task_providers.dart and calendar_providers.dart.
//
// Voice mode:
//   CheckInNotifier.startVoiceCheckIn() drives question sequencing,
//   speaks via TTS, and handles all error branches. After each answer it
//   calls orchestratorProvider.acknowledgeNoResponse() so the voice loop
//   does not get stuck in processing.
//
// Text mode:
//   CheckInNotifier exposes currentItem and currentStepIndex for the
//   PulseCheckInWidget to render the active question.
//
// See: SPEC-20260302-ADHD Phase 1 Task 4, ADR-0032.
// ===========================================================================

import 'package:drift/drift.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../database/app_database.dart';
import '../database/daos/questionnaire_dao.dart';
import '../services/checkin_score_service.dart';
import '../services/numeric_parser_service.dart';
import '../services/questionnaire_defaults.dart';
import 'database_provider.dart';
import 'voice_providers.dart';

// ---------------------------------------------------------------------------
// DAO provider
// ---------------------------------------------------------------------------

/// Provides the [QuestionnaireDao] wired to the app database.
final questionnaireDaoProvider = Provider<QuestionnaireDao>((ref) {
  final db = ref.watch(databaseProvider);
  return QuestionnaireDao(db);
});

/// Provides [QuestionnaireDefaults] wired to [QuestionnaireDao].
final questionnaireDefaultsProvider = Provider<QuestionnaireDefaults>((ref) {
  final dao = ref.watch(questionnaireDaoProvider);
  return QuestionnaireDefaults(dao);
});

/// Provides [CheckInScoreService] (stateless — single instance).
final checkInScoreServiceProvider = Provider<CheckInScoreService>(
  (_) => const CheckInScoreService(),
);

// ---------------------------------------------------------------------------
// CheckInState
// ---------------------------------------------------------------------------

/// Immutable state for an active Pulse Check-In session.
class CheckInState {
  /// The questionnaire items loaded for this check-in.
  final List<QuestionnaireItem> items;

  /// The template used for this check-in (holds scaleMin/scaleMax).
  final QuestionnaireTemplate? template;

  /// Current item index (0-based). Equal to [items.length] when all items
  /// have been answered and the check-in is at the summary step.
  final int currentStepIndex;

  /// Collected answers, one per item. Null means the item was skipped.
  /// Length always equals [items.length] once initialized.
  final List<int?> answers;

  /// Whether the check-in flow is currently active.
  final bool isActive;

  /// Set to true after [saveCheckInResponse()] completes successfully.
  final bool isSaved;

  /// The computed composite score (0–100), set after save. Null if not yet
  /// computed or all items were skipped.
  final double? compositeScore;

  /// Non-null when the last parse attempt failed (for UI re-prompt).
  final String? lastParseError;

  const CheckInState({
    this.items = const [],
    this.template,
    this.currentStepIndex = 0,
    this.answers = const [],
    this.isActive = false,
    this.isSaved = false,
    this.compositeScore,
    this.lastParseError,
  });

  CheckInState copyWith({
    List<QuestionnaireItem>? items,
    QuestionnaireTemplate? template,
    int? currentStepIndex,
    List<int?>? answers,
    bool? isActive,
    bool? isSaved,
    double? Function()? compositeScore,
    String? Function()? lastParseError,
  }) {
    return CheckInState(
      items: items ?? this.items,
      template: template ?? this.template,
      currentStepIndex: currentStepIndex ?? this.currentStepIndex,
      answers: answers ?? this.answers,
      isActive: isActive ?? this.isActive,
      isSaved: isSaved ?? this.isSaved,
      compositeScore: compositeScore != null
          ? compositeScore()
          : this.compositeScore,
      lastParseError: lastParseError != null
          ? lastParseError()
          : this.lastParseError,
    );
  }

  /// Whether the check-in flow has reached the summary step.
  bool get isComplete => isActive && currentStepIndex >= items.length;

  /// The currently active question, or null if at summary step.
  QuestionnaireItem? get currentItem =>
      currentStepIndex < items.length ? items[currentStepIndex] : null;

  /// Human-readable progress string (e.g., "3 of 6").
  String get progressLabel => '${currentStepIndex + 1} of ${items.length}';
}

// ---------------------------------------------------------------------------
// CheckInNotifier
// ---------------------------------------------------------------------------

/// Manages the Pulse Check-In flow state.
///
/// Drives both voice mode (TTS + STT feedback) and text mode (slider UI).
/// After the last question is answered, computes the composite score and
/// saves the response + answers atomically via [QuestionnaireDao].
class CheckInNotifier extends StateNotifier<CheckInState> {
  final QuestionnaireDao _dao;
  final QuestionnaireDefaults _defaults;
  final CheckInScoreService _scoreService;
  final Ref _ref;

  CheckInNotifier({
    required QuestionnaireDao dao,
    required QuestionnaireDefaults defaults,
    required CheckInScoreService scoreService,
    required Ref ref,
  }) : _dao = dao,
       _defaults = defaults,
       _scoreService = scoreService,
       _ref = ref,
       super(const CheckInState());

  // ---------------------------------------------------------------------------
  // Start / stop
  // ---------------------------------------------------------------------------

  /// Load the active template and start the check-in flow.
  ///
  /// Seeds the default template on first launch if needed.
  /// Sets [isActive] = true and resets all answer state.
  Future<void> startCheckIn() async {
    await _defaults.ensureDefaultTemplate();
    final template = await _dao.getActiveDefaultTemplate();
    if (template == null) {
      return; // should not happen after ensureDefaultTemplate
    }

    final items = await _dao.getActiveItemsForTemplate(template.id);
    if (items.isEmpty) return;

    state = CheckInState(
      items: items,
      template: template,
      currentStepIndex: 0,
      answers: List.filled(items.length, null),
      isActive: true,
    );
  }

  /// Cancel the check-in without saving. Resets to initial state.
  void cancelCheckIn() {
    state = const CheckInState();
  }

  // ---------------------------------------------------------------------------
  // Answer recording
  // ---------------------------------------------------------------------------

  /// Record the answer for the current item and advance to the next step.
  ///
  /// Pass null for a skipped item.
  /// When the last item is answered, automatically saves the response.
  Future<void> recordAnswer({
    required String sessionId,
    required int? value,
  }) async {
    if (!state.isActive) return;
    final idx = state.currentStepIndex;
    if (idx >= state.items.length) return;

    final updatedAnswers = List<int?>.from(state.answers);
    updatedAnswers[idx] = value;

    final nextStep = idx + 1;
    state = state.copyWith(
      answers: updatedAnswers,
      currentStepIndex: nextStep,
      lastParseError: () => null,
    );

    if (nextStep >= state.items.length) {
      await _saveResponse(sessionId);
    }
  }

  /// Re-prompt the current item (voice error branch — non-numeric or out-of-range).
  ///
  /// Sets [lastParseError] so the UI / voice layer can show the re-prompt.
  /// Does NOT advance the step index.
  void flagParseError(String errorMessage) {
    state = state.copyWith(lastParseError: () => errorMessage);
  }

  // ---------------------------------------------------------------------------
  // Voice mode helpers
  // ---------------------------------------------------------------------------

  /// Speak the current question via TTS and wait for the voice loop.
  ///
  /// After speaking, calls [orchestratorProvider.acknowledgeNoResponse()] so
  /// the orchestrator transitions from processing back to listening. The STT
  /// result is then delivered via the normal [sendMessage()] path, where
  /// [CheckInNotifier.handleVoiceAnswer()] parses the numeric response.
  Future<void> speakCurrentQuestion() async {
    final item = state.currentItem;
    if (item == null) return;

    final tts = _ref.read(textToSpeechServiceProvider);
    final template = state.template;
    final scaleMin = template?.scaleMin ?? 1;
    final scaleMax = template?.scaleMax ?? 10;

    final speech =
        '${item.questionText} — give me a number from $scaleMin to $scaleMax.';
    await tts.speak(speech);

    // Resume orchestrator so it transitions from processing back to listening.
    _acknowledgeOrchestrator();
  }

  /// Handle a raw voice response for the current check-in item.
  ///
  /// Parses [rawText] as a number within the active scale. On success, records
  /// the answer and advances. On parse failure, flags the error and re-prompts
  /// once. On second failure, treats as skip.
  Future<void> handleVoiceAnswer({
    required String sessionId,
    required String rawText,
  }) async {
    final template = state.template;
    if (template == null || !state.isActive) return;

    // Use a temporary parser (stateless) to extract the number.
    // NumericParserService is a const constructor — allocate inline.
    final parser = _ref.read(_numericParserProvider);
    final value = parser.parse(
      rawText,
      scaleMin: template.scaleMin,
      scaleMax: template.scaleMax,
    );

    // Explicit skip phrases → null immediately, no re-prompt.
    final isExplicitSkip = _isExplicitSkip(rawText);
    if (isExplicitSkip) {
      await _speakAcknowledgement('No problem, moving on.');
      await recordAnswer(sessionId: sessionId, value: null);
      return;
    }

    if (value == null) {
      if (state.lastParseError == null) {
        // First failure — re-prompt with range.
        final scaleMin = template.scaleMin;
        final scaleMax = template.scaleMax;
        final reprompt =
            'Just a number from $scaleMin to $scaleMax — how would you rate it?';
        flagParseError(reprompt);
        await _speakAcknowledgement(reprompt);
        _acknowledgeOrchestrator();
        return;
      } else {
        // Second failure — treat as skip.
        await _speakAcknowledgement('No problem, moving on.');
        await recordAnswer(sessionId: sessionId, value: null);
        return;
      }
    }

    // Valid answer.
    await _speakAcknowledgement('Got it, $value.');
    await recordAnswer(sessionId: sessionId, value: value);
  }

  // ---------------------------------------------------------------------------
  // Internal helpers
  // ---------------------------------------------------------------------------

  Future<void> _saveResponse(String sessionId) async {
    final template = state.template;
    if (template == null) return;

    final score = _scoreService.computeScore(
      items: state.items,
      values: state.answers,
      scaleMin: template.scaleMin,
      scaleMax: template.scaleMax,
    );

    // If all items skipped → no save (per spec edge case).
    final hasAnyAnswer = state.answers.any((v) => v != null);
    if (!hasAnyAnswer) {
      state = state.copyWith(isActive: false, compositeScore: () => null);
      return;
    }

    final answerCompanions = <CheckInAnswersCompanion>[];
    for (var i = 0; i < state.items.length; i++) {
      answerCompanions.add(
        CheckInAnswersCompanion(
          // responseId is set by the DAO in the transaction.
          itemId: Value(state.items[i].id),
          value: Value(state.answers[i]),
        ),
      );
    }

    await _dao.saveCheckInResponse(
      response: CheckInResponsesCompanion(
        sessionId: Value(sessionId),
        templateId: Value(template.id),
        completedAt: Value(DateTime.now().toUtc()),
        compositeScore: Value(score),
        syncStatus: const Value('PENDING'),
      ),
      answers: answerCompanions,
    );

    state = state.copyWith(isSaved: true, compositeScore: () => score);
  }

  Future<void> _speakAcknowledgement(String text) async {
    try {
      final tts = _ref.read(textToSpeechServiceProvider);
      await tts.speak(text);
    } catch (_) {
      // TTS failure is non-fatal — continue the flow.
    }
  }

  void _acknowledgeOrchestrator() {
    try {
      final orchestrator = _ref.read(voiceOrchestratorProvider);
      orchestrator.acknowledgeNoResponse();
    } catch (_) {
      // Orchestrator may not be active in text mode — ignore.
    }
  }

  bool _isExplicitSkip(String text) {
    final lower = text.toLowerCase().trim();
    return lower == 'skip' ||
        lower == 'pass' ||
        lower == "i don't know" ||
        lower == 'not sure' ||
        lower == 'n/a';
  }
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

/// Counts all completed check-in responses (for progressive disclosure of
/// the history icon in the home screen AppBar).
///
/// Emits 0 while loading or if no check-ins exist.
final checkInCountProvider = StreamProvider<int>((ref) {
  final dao = ref.watch(questionnaireDaoProvider);
  return dao.watchAllResponses().map((r) => r.length);
});

/// Streams the active system-default questionnaire template.
///
/// Used by the settings screen scale toggle. Emits null before the
/// default template is seeded (first launch). Updates in real-time.
final activeDefaultTemplateProvider = StreamProvider<QuestionnaireTemplate?>((
  ref,
) {
  final dao = ref.watch(questionnaireDaoProvider);
  return dao.watchDefaultTemplate();
});

/// Watches items for the active default template (for settings screen).
///
/// Emits an empty list when no default template exists yet. Updates in
/// real-time as items are toggled or reordered.
final activeCheckInItemsProvider = StreamProvider<List<QuestionnaireItem>>((
  ref,
) async* {
  final dao = ref.watch(questionnaireDaoProvider);
  final template = await dao.getActiveDefaultTemplate();
  if (template == null) {
    yield [];
    return;
  }
  yield* dao.watchItemsForTemplate(template.id);
});

/// Provides the [CheckInNotifier] for the active check-in session.
final checkInProvider = StateNotifierProvider<CheckInNotifier, CheckInState>((
  ref,
) {
  return CheckInNotifier(
    dao: ref.watch(questionnaireDaoProvider),
    defaults: ref.watch(questionnaireDefaultsProvider),
    scoreService: ref.watch(checkInScoreServiceProvider),
    ref: ref,
  );
});

// Internal parser provider — delegates to NumericParserService for full
// voice input coverage (STT homophones, decimal rejection, compound word
// forms, and numbers 11–100). No circular import: numeric_parser_service.dart
// has no dependency on providers.
final _numericParserProvider = Provider((_) => const NumericParserService());

/// App-level state tracking whether the Quick Check-In banner has been
/// dismissed in the current session.
///
/// Stored as a Riverpod [StateProvider] (not widget-local state) so that
/// dismissal persists across navigation events (e.g., Back → SessionList).
/// Resets on app restart, which is acceptable — the banner is a feature
/// discovery CTA, not a persistent notification.
///
/// ADHD UX: the banner is shown universally (not conditioned on gap duration)
/// to avoid implicit gap-shaming. See REV-20260303-142206 B1/B2.
final quickCheckInBannerDismissedProvider = StateProvider<bool>((ref) => false);

// ---------------------------------------------------------------------------
// Check-In History
// ---------------------------------------------------------------------------

/// One annotated check-in entry for the history dashboard.
///
/// Pairs a [CheckInResponseWithAnswers] with the resolved question text
/// for each answer and the template's scale bounds, so the UI can display
/// labels and answer bars without extra DAO calls.
class CheckInHistoryEntry {
  /// The response row with its raw answer values.
  final CheckInResponseWithAnswers responseWithAnswers;

  /// Map of item id → question text, resolved from the template's item rows.
  final Map<int, String> itemText;

  /// Scale bounds from the template used for this response.
  final int scaleMin;
  final int scaleMax;

  const CheckInHistoryEntry({
    required this.responseWithAnswers,
    required this.itemText,
    this.scaleMin = 1,
    this.scaleMax = 10,
  });

  CheckInResponse get response => responseWithAnswers.response;
  List<CheckInAnswer> get answers => responseWithAnswers.answers;
}

/// Streams all check-in responses with resolved question labels and scale bounds.
///
/// Builds a per-template item-text and template cache to avoid repeated DAO
/// round-trips when multiple responses share the same template.
final checkInHistoryProvider = StreamProvider<List<CheckInHistoryEntry>>((
  ref,
) async* {
  final dao = ref.watch(questionnaireDaoProvider);
  await for (final responses in dao.watchAllResponsesWithAnswers()) {
    // Resolve question text and scale bounds per template (cached per emission).
    final itemTextCache = <int, Map<int, String>>{};
    final templateCache = <int, QuestionnaireTemplate?>{};
    for (final rwa in responses) {
      final templateId = rwa.response.templateId;
      if (!itemTextCache.containsKey(templateId)) {
        // Use getAllItemsForTemplate (not getActiveItemsForTemplate) so that
        // deactivated items still show their question text in the history view.
        final items = await dao.getAllItemsForTemplate(templateId);
        itemTextCache[templateId] = {
          for (final it in items) it.id: it.questionText,
        };
      }
      if (!templateCache.containsKey(templateId)) {
        templateCache[templateId] = await dao.getTemplateById(templateId);
      }
    }
    yield responses.map((rwa) {
      final template = templateCache[rwa.response.templateId];
      return CheckInHistoryEntry(
        responseWithAnswers: rwa,
        itemText: itemTextCache[rwa.response.templateId] ?? {},
        scaleMin: template?.scaleMin ?? 1,
        scaleMax: template?.scaleMax ?? 10,
      );
    }).toList();
  }
});
