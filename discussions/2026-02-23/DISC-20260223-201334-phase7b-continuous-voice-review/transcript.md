---
discussion_id: DISC-20260223-201334-phase7b-continuous-voice-review
started: 2026-02-23T20:22:40.333718+00:00
ended: 2026-02-23T20:23:51.565457+00:00
agents: [architecture-consultant, facilitator, qa-specialist, security-specialist, ux-evaluator]
total_turns: 5
---

# Discussion: DISC-20260223-201334-phase7b-continuous-voice-review

## Turn 1 — architecture-consultant (proposal)
*2026-02-23T20:22:40.333718+00:00 | confidence: 0.87*
*tags: review, architecture, blocking:2, advisory:5*

Confidence: 0.87. VERDICT: REVISE.

BLOCKING (2):
1. [Medium] ADR gap — ADR-0015 covers Phase 7A only. Phase 7B decisions (callback pattern for circular dep avoidance, ValueNotifier over StateNotifier, separate VoiceCommandClassifier, sentence-splitting TTS) are unrecorded. Create ADR-0016 or addendum.
2. [Medium] Unawaited future in _speakNonBlocking (line 783) — fire-and-forget TTS call has no .catchError(), producing unhandled async exceptions in release. Add .catchError() wrapper.

ADVISORY (5):
3. [Medium] Mutable callback fields (onSendMessage, etc.) allow invalid state between construction and wiring. Consider constructor injection or configure() guard.
4. [Low] ValueNotifier diverges from project's Riverpod pattern. Acceptable trade-off but should be documented in ADR.
5. [Low] VoiceCommandClassifier created inline rather than injected. Accept as constructor parameter with default.
6. [Info] Classifier parallel structure with IntentClassifier is appropriate domain separation.
7. [Low] Bare catch(e) in _startListeningRaw, _handleError, _speak. Use on Exception catch(e) per coding standards.

STRENGTHS: Clean dependency direction, well-documented state machine header, immutable state emission via copyWith, conservative command classification with false-positive guards, verbal confirmation for destructive actions, sentence-splitting TTS for perceived latency reduction, centralized voice recovery messages.

---

## Turn 2 — qa-specialist (proposal)
*2026-02-23T20:22:52.499784+00:00 | confidence: 0.87*
*tags: review, qa, high:3, medium:4, low:3*

Confidence: 0.87.

HIGH (3):
1. resumeLatestSession() (session_providers.dart:589) has zero test coverage. Needs tests for no-open-sessions, resume-most-recent, and guard-when-active.
2. onAssistantMessage() when phase is NOT processing is untested. Messages silently dropped during pause/error/idle. Add no-op test and push-to-talk path test.
3. Race condition: _executeEndSession() does not re-check state.phase after awaited _speak() calls. If stop() is called during TTS confirmation, session still ends. Add phase guard after each await.

MEDIUM (4):
4. Undo timer expiry path untested — need test for undo-after-expiry and dispose-cancels-timer.
5. _isAffirmative() never tested in isolation. Boundary cases: "yes please" (two words, fails ^...$), "absolutely" not in pattern. Expose @visibleForTesting.
6. Voice command classifier test assertion wrong — line 110 expects VoiceCommand.none for "I'm done with the dishes" but classifier returns endSession at confidence 0.5 (not none).
7. App lifecycle (didChangeAppLifecycleState) auto-save/pause/resume has no widget tests.

LOW (3):
8. Discard confirmation test assertion fragile — matches any text containing "sure" instead of exact VoiceRecoveryMessages.verbalDiscardConfirm.
9. _handleError double-failure (TTS also throws) untested — state transition to idle should be verified.
10. Silence timeout test uses real Future.delayed(1500ms) — should use fakeAsync for reliability.

EDGE CASES: Empty final STT result, rapid start/stop sequences, null onSendMessage in continuous mode, _pendingCommand null in confirmation handler, multiple AudioFocusEvent.loss, _ttsInitialized not reset after dispose.

STRENGTHS: High mock quality with autoComplete flag, confirmation flow well covered end-to-end, classifier tests thorough, SharedPreferences persistence tested correctly, good test isolation, splitIntoSentences exposed via @visibleForTesting.

---

## Turn 3 — ux-evaluator (proposal)
*2026-02-23T20:23:07.047605+00:00 | confidence: 0.87*
*tags: review, ux, high:3, medium:5, low:2*

Confidence: 0.87.

HIGH (3):
1. Error phase indicator never renders — _handleError sets isContinuousMode:false before UI can show error chip. Phase indicator only shown when isContinuousMode is true. Fix: show indicator when phase==error regardless of continuous mode.
2. Auto-save defaults to true without user consent — first-time voice users backgrounding app get session silently ended. Default should be false (opt-in) or show one-time acknowledgment.
3. Error recovery drops continuous mode permanently — _handleError sets isContinuousMode:false with no retry. Voice-first users (walking, driving) get stranded with no way back to continuous mode. Add one automatic retry for recoverable STT errors before falling back.

MEDIUM (5):
4. Phase indicator lacks Semantics/liveRegion — screen reader users not notified of phase transitions. Wrap in Semantics(liveRegion: true).
5. Mic button GestureDetector+IconButton layering creates dual focusable elements for TalkBack. Use single Semantics wrapper.
6. Long-press discoverability — hidden gesture for continuous mode with no coach mark or snackbar hint for first use.
7. Undo window STT not listening — TTS says "say undo within 30 seconds" but STT is off. User must manually tap mic. Contradicts hands-free promise.
8. Processing phase has no visual feedback beyond 12sp "Thinking" chip — show last utterance in dimmed state during processing.

LOW (2):
9. Settings subtitle "Adds mic button; long-press for continuous mode" reads as dev note. Use natural language.
10. STT init spinner (5-8s) has no text label — user may think app is hanging. Add "Loading voice model..." text.

FLOW ASSESSMENT: Happy path well-structured. Back navigation guarded. Destructive actions have confirmation. Critical gap is undo window (Finding 7) being non-functional for hands-free use.

---

## Turn 4 — security-specialist (proposal)
*2026-02-23T20:23:19.214481+00:00 | confidence: 0.87*
*tags: review, security, medium:2, low:3*

Confidence: 0.87.

MEDIUM (2):
1. Unbounded confirmation timeout — _awaitingConfirmation has no timeout. Ambient audio (TV saying "yes") can trigger destructive discard after an indefinite window. Add 10-second bounded timeout, tighten _isAffirmative to exclude "go ahead"/"do it" from discard path.
2. "stop"/"finish"/"bye" too common for high-confidence end pattern — these single words appear in narrative speech ("I told him to stop"). Move to _moderateEndPattern (triggers verbal confirmation) instead of _strongEndPattern.

LOW (3):
3. Stale confirmation state on dispose — _awaitingConfirmation and _pendingCommand not reset in dispose(). If orchestrator reused via singleton provider, new session could inherit stale state. Add explicit resets in dispose() and at start of startContinuousMode()/startPushToTalk().
4. debugPrint usage correct — stripped in release builds. No session content logged.
5. Platform channel flags correct — VOICE_ASSIST intent system-only, one-shot clear pattern properly implemented.

TRUST BOUNDARIES:
- Microphone audio -> STT -> VoiceCommandClassifier: untrusted audio, no sender identity. Confirmation gate partially guards but is unbounded (Finding 1).
- Android Intent -> MainActivity -> Flutter: system-only VOICE_ASSIST, correct one-shot pattern.

STRENGTHS: Defensive design with verbal confirmation for destructive actions. Confidence-gated command execution. End-session undo window. TTS-only audible feedback (no ambient data leakage).

---

## Turn 5 — facilitator (synthesis)
*2026-02-23T20:23:51.565457+00:00 | confidence: 0.87*
*tags: synthesis, blocking:6, advisory:16*

VERDICT: APPROVE WITH CHANGES (6 blocking, 16 advisory)

Phase 7B implements a well-structured continuous voice mode state machine with clean dependency direction, immutable state emission, and defensive command classification. All 4 specialists converge on high confidence (0.87) that the architecture is sound but the implementation has specific correctness and safety gaps that must be addressed.

BLOCKING (6):
1. [arch-7, security] _speakNonBlocking unawaited future — unhandled async exception in release. Add .catchError() wrapper.
2. [qa-3] Race condition: _executeEndSession/_executeDiscard do not re-check state.phase after awaited _speak(). stop() during TTS confirmation still executes destructive action. Add phase guard after each await.
3. [security-1] Unbounded confirmation timeout — ambient audio can trigger destructive discard. Add 10-second timeout on _awaitingConfirmation.
4. [security-2] "stop"/"finish"/"bye" in _strongEndPattern — too common in narrative speech for high-confidence end command. Move to _moderateEndPattern.
5. [security-3] Stale confirmation state on dispose — _awaitingConfirmation/_pendingCommand not reset. Add resets in dispose() and start methods.
6. [qa-6] Classifier test assertion wrong — line 110 expects VoiceCommand.none for "I'm done with the dishes" but classifier returns endSession@0.5. Fix assertion.

ADVISORY (16):
- [arch-1] ADR gap for Phase 7B decisions (callback pattern, ValueNotifier, classifier separation)
- [arch-2] Mutable callback fields — consider configure() guard
- [arch-4] VoiceCommandClassifier should be injectable via constructor parameter
- [arch-6] Bare catch(e) — use on Exception catch(e)
- [qa-1] resumeLatestSession() untested
- [qa-2] onAssistantMessage when not processing untested
- [qa-4] Undo timer expiry untested
- [qa-5] _isAffirmative untested in isolation
- [qa-7] Lifecycle auto-save widget tests missing
- [ux-1] Error phase indicator never renders (isContinuousMode gate)
- [ux-2] Auto-save defaults to true without consent
- [ux-3] Error recovery drops continuous mode permanently
- [ux-4] Phase indicator lacks Semantics/liveRegion
- [ux-6] Long-press discoverability (coach mark)
- [ux-7] Undo window STT not listening (hands-free gap)
- [ux-8] Processing phase: show last utterance in dimmed state

EDUCATION GATE: Recommended — walkthrough of orchestrator state machine and voice command classifier at Bloom's Apply/Analyze level.

---
