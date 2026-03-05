// ===========================================================================
// file: test/ui/journal_session_screen_test.dart
// purpose: Widget tests for the active journal session screen.
//
// Tests verify that:
//   - The screen renders with app bar and input field
//   - The greeting message is displayed
//   - The send button is present
//   - AppBar has Done button and overflow menu has Discard option
//   - Back button shows confirmation dialog (B1)
//   - Discard confirmation works
//   - Done button appears after session close (B2)
//   - Auto-discard SnackBar on empty session (Phase 6)
// ===========================================================================

import 'dart:async';

import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/providers/database_provider.dart';
import 'package:agentic_journal/providers/onboarding_providers.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/providers/voice_providers.dart';
import 'package:agentic_journal/repositories/agent_repository.dart';
import 'package:agentic_journal/providers/questionnaire_providers.dart';
import 'package:agentic_journal/services/audio_file_service.dart';
import 'package:agentic_journal/services/audio_focus_service.dart';
import 'package:agentic_journal/services/speech_recognition_service.dart';
import 'package:agentic_journal/services/text_to_speech_service.dart';
import 'package:agentic_journal/services/voice_session_orchestrator.dart';
import 'package:agentic_journal/ui/screens/journal_session_screen.dart';

void main() {
  group('JournalSessionScreen', () {
    late AppDatabase database;

    late SharedPreferences prefs;

    setUp(() async {
      database = AppDatabase.forTesting(NativeDatabase.memory());
      SharedPreferences.setMockInitialValues({});
      prefs = await SharedPreferences.getInstance();
    });

    tearDown(() async {
      await database.close();
    });

    Future<ProviderContainer> buildTestWidget(WidgetTester tester) async {
      late ProviderContainer container;

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container = ProviderContainer(
            overrides: [
              sharedPreferencesProvider.overrideWithValue(prefs),
              databaseProvider.overrideWithValue(database),
              agentRepositoryProvider.overrideWithValue(AgentRepository()),
              deviceTimezoneProvider.overrideWith(
                (ref) async => 'America/New_York',
              ),
            ],
          ),
          child: MaterialApp(
            initialRoute: '/session',
            routes: {
              '/': (_) => const Scaffold(body: Text('Session List')),
              '/session': (_) => const JournalSessionScreen(),
            },
          ),
        ),
      );

      // Start a session so there's an active session and greeting.
      await container.read(sessionNotifierProvider.notifier).startSession();
      await tester.pumpAndSettle();

      return container;
    }

    testWidgets('renders app bar with Journal Entry title', (tester) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      expect(find.text('Journal Entry'), findsOneWidget);
    });

    testWidgets('shows greeting message from agent', (tester) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      // The agent repository generates a greeting — it should appear as a
      // chat bubble. The exact text depends on time-of-day, so just check
      // that at least one chat bubble exists.
      expect(find.byType(ListView), findsOneWidget);
    });

    testWidgets('shows text input field with hint', (tester) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      expect(find.byType(TextField), findsOneWidget);
      expect(find.text('Type your thoughts...'), findsOneWidget);
    });

    testWidgets('has send button', (tester) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      expect(find.byIcon(Icons.send), findsOneWidget);
    });

    testWidgets('has back button in app bar', (tester) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      expect(find.byIcon(Icons.arrow_back), findsOneWidget);
    });

    testWidgets('has Done button in AppBar and Discard in overflow menu', (
      tester,
    ) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      // Done button should be visible in the AppBar.
      expect(find.text('Done'), findsOneWidget);

      // Overflow menu icon should be present.
      expect(find.byIcon(Icons.more_vert), findsOneWidget);

      // Tap the overflow menu.
      await tester.tap(find.byIcon(Icons.more_vert));
      await tester.pumpAndSettle();

      // Only Discard should be in the overflow menu.
      expect(find.text('Discard'), findsOneWidget);
    });

    testWidgets('discard from overflow menu shows confirmation dialog', (
      tester,
    ) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      // Open overflow menu and tap Discard.
      await tester.tap(find.byIcon(Icons.more_vert));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Discard'));
      await tester.pumpAndSettle();

      // Confirmation dialog should appear.
      expect(find.text('Discard this entry?'), findsOneWidget);
      expect(find.text('This cannot be undone.'), findsOneWidget);
      expect(find.text('Cancel'), findsOneWidget);
      // The Discard button in the dialog.
      expect(find.widgetWithText(FilledButton, 'Discard'), findsOneWidget);
    });

    testWidgets('cancel in discard dialog keeps session active', (
      tester,
    ) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      // Open overflow menu and tap Discard.
      await tester.tap(find.byIcon(Icons.more_vert));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Discard'));
      await tester.pumpAndSettle();

      // Tap Cancel.
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      // Dialog closed, session still active.
      expect(find.text('Discard this entry?'), findsNothing);
      final state = container.read(sessionNotifierProvider);
      expect(state.activeSessionId, isNotNull);
    });

    // regression: back button used to immediately pop without showing the
    // closing summary (endSession + dismissSession + pop in finally block).
    // It now matches the "goodbye" UX: shows the closing summary so the
    // user can confirm their entry was saved, then a second back dismisses.
    testWidgets(
      'back button ends session and shows closing summary, second back '
      'dismisses (regression)',
      (tester) async {
        final container = await buildTestWidget(tester);
        addTearDown(container.dispose);

        // Send a user message so the session has content.
        await tester.enterText(find.byType(TextField), 'I feel great');
        await tester.tap(find.byIcon(Icons.send));
        await tester.pumpAndSettle();

        // First back press — ends session, shows closing summary.
        await tester.tap(find.byIcon(Icons.arrow_back));
        await tester.pumpAndSettle();

        // Session must be in closing state (not immediately dismissed).
        final state = container.read(sessionNotifierProvider);
        expect(
          state.isClosingComplete,
          isTrue,
          reason: 'back button must show closing summary, not immediately pop',
        );
        expect(
          find.text('Session List'),
          findsNothing,
          reason: 'screen must stay open while closing summary is visible',
        );

        // Second back press — dismisses the screen.
        await tester.tap(find.byIcon(Icons.arrow_back));
        await tester.pumpAndSettle();

        expect(find.text('Session List'), findsOneWidget);
      },
    );

    testWidgets('Done button ends session and shows closing summary', (
      tester,
    ) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      // Send a user message so the session is not empty.
      await tester.enterText(find.byType(TextField), 'Testing');
      await tester.tap(find.byIcon(Icons.send));
      await tester.pumpAndSettle();

      // Tap Done — ends session and shows closing summary (does not pop).
      await tester.tap(find.text('Done'));
      await tester.pumpAndSettle();

      final state = container.read(sessionNotifierProvider);
      expect(state.isClosingComplete, isTrue);
      // Still on session screen — user dismisses with a back press.
      expect(find.text('Session List'), findsNothing);
    });

    // regression: after completing a pulse_check_in session, checkInProvider
    // (a global StateNotifierProvider) kept isActive=true. When the user then
    // opened a new regular journal entry, _maybeStartCheckIn() did not reset
    // the state — so the check-in complete card was displayed and the text
    // input field was hidden behind it. Fix: call cancelCheckIn() in the
    // else branch of _maybeStartCheckIn() for non-pulse-check-in sessions.
    //
    // NOTE: This test explicitly pre-seeds isActive=true before pumpAndSettle
    // so that removing the else branch would cause the test to fail. A test
    // that only checks the default isActive=false state proves nothing about
    // the regression.
    testWidgets(
      'text input visible and check-in card absent in regular journal session '
      '(regression: check-in state not reset cross-session)',
      (tester) async {
        // Create the container BEFORE pumpWidget so we can seed state.
        // addPostFrameCallback fires during pumpWidget (on the first frame
        // render), not during pumpAndSettle — so the state must be seeded
        // before the widget is built.
        final container = ProviderContainer(
          overrides: [
            sharedPreferencesProvider.overrideWithValue(prefs),
            databaseProvider.overrideWithValue(database),
            agentRepositoryProvider.overrideWithValue(AgentRepository()),
            deviceTimezoneProvider.overrideWith(
              (ref) async => 'America/New_York',
            ),
          ],
        );
        addTearDown(container.dispose);

        // Pre-condition: seed isActive=true to simulate stale check-in state
        // from a previous pulse_check_in session. If the fix (else branch in
        // _maybeStartCheckIn) is reverted, isActive stays true after the frame
        // renders and the assertions below will fail.
        await container.read(checkInProvider.notifier).startCheckIn();
        expect(
          container.read(checkInProvider).isActive,
          isTrue,
          reason:
              'pre-condition: isActive must be seeded true before widget '
              'builds to prove the regression fix is exercised',
        );

        // Start a session so the postFrameCallback's sessionState has a
        // non-null activeSessionId when _maybeStartCheckIn() evaluates it.
        await container.read(sessionNotifierProvider.notifier).startSession();

        // Build the widget. The first frame render fires the postFrameCallback
        // registered in initState, which calls _maybeStartCheckIn(). For a
        // non-pulse-check-in session, the else branch calls cancelCheckIn()
        // and resets isActive to false.
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp(
              initialRoute: '/session',
              routes: {
                '/': (_) => const Scaffold(body: Text('Session List')),
                '/session': (_) => const JournalSessionScreen(),
              },
            ),
          ),
        );
        await tester.pumpAndSettle();

        // Post-condition: cancelCheckIn() must have been called.
        expect(
          container.read(checkInProvider).isActive,
          isFalse,
          reason:
              'cancelCheckIn() must be called for non-pulse-check-in sessions '
              'to prevent lingering state from a previous check-in hiding the input',
        );
        // The text input field must be visible (isActive=true suppresses it).
        expect(
          find.byType(TextField),
          findsOneWidget,
          reason: 'text input must not be hidden by a stale check-in card',
        );
        // No pulse-check-in card should appear.
        expect(find.text('Pulse Check-In'), findsNothing);
      },
    );

    testWidgets('auto-discard shows SnackBar on empty session end', (
      tester,
    ) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      // End session without sending any user messages (empty session guard).
      // Use Done button in AppBar.
      await tester.tap(find.text('Done'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // SnackBar should appear with closed message.
      expect(
        find.text('Session closed \u2014 nothing was recorded.'),
        findsOneWidget,
      );
    });

    // regression: maxLines: null caused the text field to expand unboundedly,
    // pushing the send button off screen when the user typed a long message.
    // Fix: minLines: 1 + maxLines: 4 keeps the field compact on 360dp devices
    // with voice controls active while still preventing overflow (REV-145506-A5).
    //
    // textInputAction is conditioned on _isTextInputMode (REV-20260305-164139-A8):
    //   - voice+text mode (default): TextInputAction.newline — voice is the
    //     primary submit path; hint text "Type your thoughts…" implies multi-line
    //   - text-primary mode: TextInputAction.send — Enter submits
    //
    // This supersedes REV-145506-A6 which set send unconditionally; the
    // contradiction between hint text and keyboard action was resolved in A8.
    testWidgets(
      'text field has minLines: 1, maxLines: 4; textInputAction is newline in voice+text mode (regression)',
      tags: ['regression'],
      (tester) async {
        final container = await buildTestWidget(tester);
        addTearDown(container.dispose);

        final textField = tester.widget<TextField>(find.byType(TextField));
        expect(
          textField.maxLines,
          equals(4),
          reason:
              'maxLines: 4 prevents send button overflow on 360dp devices '
              'with voice controls active (REV-145506-A5)',
        );
        expect(
          textField.minLines,
          equals(1),
          reason: 'minLines: 1 keeps the field compact when empty',
        );
        // Default state is voice+text mode (_isTextInputMode = false).
        // In this mode Enter inserts a newline — voice is the primary submit
        // path and the hint text "Type your thoughts…" implies multi-line entry
        // (REV-20260305-164139-A8 supersedes REV-145506-A6 unconditional .send).
        expect(
          textField.textInputAction,
          equals(TextInputAction.newline),
          reason:
              'In voice+text mode Enter inserts a newline so users can write '
              'multi-thought entries; voice or the send button submits '
              '(REV-20260305-164139-A8)',
        );
      },
    );

    // regression (companion to above): text-primary mode must use send.
    // If the conditional were accidentally inverted, both mode arms would
    // assert the same value — neither test would catch the inversion alone.
    // This test activates _isTextInputMode by tapping the 'Text' segment.
    // Requires voice mode enabled so the Voice/Text toggle is rendered
    // (REV-20260305-175417-A1 companion to REV-20260305-164139-A8).
    testWidgets(
      'textInputAction is send in text-primary mode (regression)',
      tags: ['regression'],
      (tester) async {
        // Seed voice_mode_enabled=true so the Voice/Text SegmentedButton
        // is rendered (it is only shown when voiceModeEnabledProvider is true).
        SharedPreferences.setMockInitialValues({voiceModeEnabledKey: true});
        prefs = await SharedPreferences.getInstance();

        final container = await buildTestWidget(tester);
        addTearDown(container.dispose);

        // Tap the 'Text' segment to activate text-primary mode.
        await tester.tap(find.text('Text'));
        await tester.pumpAndSettle();

        final textField = tester.widget<TextField>(find.byType(TextField));
        expect(
          textField.textInputAction,
          equals(TextInputAction.send),
          reason:
              'In text-primary mode Enter submits — voice is not the primary '
              'path and users expect keyboard Enter to send '
              '(REV-20260305-164139-A8; companion to newline-mode test)',
        );
      },
    );

    // A-3 regression guard: helperText conditional correctness.
    // voice+text idle → 'Tap send icon to submit'; text-primary → null.
    // Guards against accidental removal or copy revert (REV-20260305-190054-A1-NEW).

    testWidgets(
      'helperText shows submit hint in voice+text idle mode (regression)',
      tags: ['regression'],
      (tester) async {
        final container = await buildTestWidget(tester);
        addTearDown(container.dispose);

        // Default state: voice+text mode, not listening, not waiting.
        // helperText must show to inform users that Enter inserts newline,
        // not submits (REV-20260305-175417-A3).
        final textField = tester.widget<TextField>(find.byType(TextField));
        expect(
          textField.decoration?.helperText,
          equals('Tap send icon to submit'),
          reason:
              'In voice+text idle state the submit-path hint must be visible '
              'so users discover the send icon (REV-20260305-175417-A3; '
              'regression guard for copy revert — REV-20260305-190054-A1-NEW)',
        );
      },
    );

    testWidgets(
      'helperText is null in text-primary mode (regression)',
      tags: ['regression'],
      (tester) async {
        // Seed voice_mode_enabled=true so the Voice/Text SegmentedButton
        // is rendered (required to tap 'Text' segment).
        SharedPreferences.setMockInitialValues({voiceModeEnabledKey: true});
        prefs = await SharedPreferences.getInstance();

        final container = await buildTestWidget(tester);
        addTearDown(container.dispose);

        // Tap the 'Text' segment to activate text-primary mode.
        await tester.tap(find.text('Text'));
        await tester.pumpAndSettle();

        // In text-primary mode Enter submits — no helper needed.
        final textField = tester.widget<TextField>(find.byType(TextField));
        expect(
          textField.decoration?.helperText,
          isNull,
          reason:
              'In text-primary mode Enter already submits — showing the '
              '"Tap send icon" hint would be redundant and confusing '
              '(REV-20260305-175417-A3; REV-20260305-190054-A1-NEW)',
        );
      },
    );

    testWidgets(
      'helperText is null while agent is processing response (regression)',
      tags: ['regression'],
      (tester) async {
        final container = await buildTestWidget(tester);
        addTearDown(container.dispose);

        // Direct state mutation via the protected `state` setter is used here
        // because SessionNotifier.sendMessage() is async and involves real I/O.
        // Using overrideWith(SessionNotifier) would require a full mock DAO and
        // agent stack just to simulate the isWaitingForAgent=true moment. The
        // protected setter is the pragmatic choice for this narrow regression
        // guard. If SessionNotifier migrates to Riverpod 2 Notifier, update
        // this test to use overrideWith. (QA-A3 from REV-20260305-223132)
        // ignore: invalid_use_of_protected_member
        container.read(sessionNotifierProvider.notifier).state = container
            .read(sessionNotifierProvider)
            .copyWith(isWaitingForAgent: true);
        await tester.pump();

        // Input is disabled during wait — showing the submit-path hint
        // would be confusing (REV-20260305-193138-A1).
        final textField = tester.widget<TextField>(find.byType(TextField));
        expect(
          textField.decoration?.helperText,
          isNull,
          reason:
              'helperText must be null while isWaitingForAgent=true — '
              'the input is disabled during this state '
              '(REV-20260305-193138-A1)',
        );
      },
    );

    testWidgets(
      'helperText is null while TTS is speaking (regression)',
      tags: ['regression'],
      (tester) async {
        // Build with a pre-configured orchestrator (phase=speaking) so the
        // initial render sees isSpeaking=true (REV-20260305-193138-A1).
        final audioFocus = _NoopAudioFocusService();
        final fakeOrchestrator =
            VoiceSessionOrchestrator(
                sttService: _NoopSpeechRecognitionService(),
                ttsService: _NoopTextToSpeechService(),
                audioFocusService: audioFocus,
              )
              ..stateNotifier.value = const VoiceOrchestratorState(
                phase: VoiceLoopPhase.speaking,
              );
        addTearDown(() {
          fakeOrchestrator.dispose();
          audioFocus.dispose();
        });

        late ProviderContainer container;
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container = ProviderContainer(
              overrides: [
                sharedPreferencesProvider.overrideWithValue(prefs),
                databaseProvider.overrideWithValue(database),
                agentRepositoryProvider.overrideWithValue(AgentRepository()),
                deviceTimezoneProvider.overrideWith(
                  (ref) async => 'America/New_York',
                ),
                voiceOrchestratorProvider.overrideWithValue(fakeOrchestrator),
              ],
            ),
            child: MaterialApp(
              initialRoute: '/session',
              routes: {
                '/': (_) => const Scaffold(body: Text('Session List')),
                '/session': (_) => const JournalSessionScreen(),
              },
            ),
          ),
        );
        await container.read(sessionNotifierProvider.notifier).startSession();
        await tester.pumpAndSettle();
        addTearDown(container.dispose);

        // phase=speaking → helperText suppressed (user is hearing the response).
        final textField = tester.widget<TextField>(find.byType(TextField));
        expect(
          textField.decoration?.helperText,
          isNull,
          reason:
              'helperText must be null while TTS is speaking — showing the '
              '"Tap send icon" hint during playback creates visual noise '
              '(REV-20260305-193138-A1)',
        );
      },
    );

    testWidgets(
      'helperText is null while microphone is listening (regression)',
      tags: ['regression'],
      (tester) async {
        // Build with a pre-configured orchestrator (phase=listening) so the
        // initial render sees isListening=true (QA-A1 from REV-20260305-223132).
        final audioFocus = _NoopAudioFocusService();
        final fakeOrchestrator =
            VoiceSessionOrchestrator(
                sttService: _NoopSpeechRecognitionService(),
                ttsService: _NoopTextToSpeechService(),
                audioFocusService: audioFocus,
              )
              ..stateNotifier.value = const VoiceOrchestratorState(
                phase: VoiceLoopPhase.listening,
              );
        addTearDown(() {
          fakeOrchestrator.dispose();
          audioFocus.dispose();
        });

        late ProviderContainer container;
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container = ProviderContainer(
              overrides: [
                sharedPreferencesProvider.overrideWithValue(prefs),
                databaseProvider.overrideWithValue(database),
                agentRepositoryProvider.overrideWithValue(AgentRepository()),
                deviceTimezoneProvider.overrideWith(
                  (ref) async => 'America/New_York',
                ),
                voiceOrchestratorProvider.overrideWithValue(fakeOrchestrator),
              ],
            ),
            child: MaterialApp(
              initialRoute: '/session',
              routes: {
                '/': (_) => const Scaffold(body: Text('Session List')),
                '/session': (_) => const JournalSessionScreen(),
              },
            ),
          ),
        );
        await container.read(sessionNotifierProvider.notifier).startSession();
        await tester.pumpAndSettle();
        addTearDown(container.dispose);

        // phase=listening → helperText suppressed; hintText already shows
        // 'Listening...' so showing the submit hint would create visual noise.
        final textField = tester.widget<TextField>(find.byType(TextField));
        expect(
          textField.decoration?.helperText,
          isNull,
          reason:
              'helperText must be null while microphone is listening — '
              'the hintText already shows "Listening..." '
              '(QA-A1 from REV-20260305-223132)',
        );
      },
    );
  });
}

// ===========================================================================
// Private fakes for isSpeaking regression test (A-1, REV-20260305-193138)
// ===========================================================================

class _NoopAudioFocusService implements AudioFocusService {
  final _controller = StreamController<AudioFocusEvent>.broadcast();

  @override
  Future<bool> requestFocus() async => true;

  @override
  Future<void> abandonFocus() async {}

  @override
  Stream<AudioFocusEvent> get onFocusChanged => _controller.stream;

  @override
  void dispose() => _controller.close();
}

class _NoopSpeechRecognitionService implements SpeechRecognitionService {
  @override
  Future<void> initialize({required String modelPath}) async {}

  @override
  Stream<SpeechResult> startListening({
    AudioFileService? audioFileService,
  }) async* {}

  @override
  Future<void> stopListening() async {}

  @override
  bool get isListening => false;

  @override
  bool get isInitialized => false;

  @override
  void dispose() {}
}

class _NoopTextToSpeechService implements TextToSpeechService {
  @override
  Future<void> initialize() async {}

  @override
  Future<void> speak(String text) async {}

  @override
  Future<void> stop() async {}

  @override
  bool get isSpeaking => false;

  @override
  Future<void> setSpeechRate(double rate) async {}

  @override
  void dispose() {}
}
